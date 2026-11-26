# -*- coding: utf-8 -*-
"""Épica 3 de la Fase B: cola de trabajos que sobrevive a un reinicio.

Hoy `servidor.JOBS` es un diccionario en memoria: si el asistente se reinicia, se
pierde el trabajo y la pausa. Esta cola guarda cada trabajo en disco y define las
transiciones válidas.

Estados:

    pedido → en_cola → corriendo → esperando_humano → listo
                            ↓              ↓
                          error         dudoso

Reglas que implementa:

- Un trabajo **en cola** sobrevive al reinicio y se ejecuta.
- Uno **corriendo** o **esperando_humano** al reiniciar pasa a **dudoso**: no se
  reintenta solo, porque pudo haber tocado SISFE. Lo resuelve una persona.
- Un trabajo que supera su tiempo límite pasa a **error** con el motivo.

Esta pieza no está integrada todavía en `servidor._lanzar`: la integración toca
el camino crítico del dashboard y se hace como paso siguiente de la épica.
"""
import json
import os
import tempfile
import threading
import time
import uuid

ESTADOS = ("pedido", "en_cola", "corriendo", "esperando_humano", "listo", "error", "dudoso")

# Transiciones permitidas. Cualquier otra es un error del programa, no del usuario.
TRANSICIONES = {
    "pedido": {"en_cola", "error"},
    "en_cola": {"corriendo", "error"},
    "corriendo": {"esperando_humano", "listo", "error", "dudoso"},
    "esperando_humano": {"corriendo", "listo", "error", "dudoso"},
    "listo": set(),
    "error": set(),
    "dudoso": {"corriendo", "error", "listo"},
}

# Los que no sobreviven como estaban: al reiniciar quedan dudosos.
INCIERTOS = {"corriendo", "esperando_humano"}

_LOCK = threading.Lock()


class TransicionInvalida(Exception):
    pass


class Cola:
    def __init__(self, ruta, ttl_segundos=3600):
        self.ruta = ruta
        self.ttl = ttl_segundos
        self._asegurar()

    # --- persistencia -------------------------------------------------
    def _asegurar(self):
        carpeta = os.path.dirname(os.path.abspath(self.ruta))
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        if not os.path.isfile(self.ruta):
            self._escribir({"trabajos": {}})

    def _leer(self):
        with open(self.ruta, encoding="utf-8") as f:
            datos = json.load(f)
        datos.setdefault("trabajos", {})
        return datos

    def _escribir(self, datos):
        carpeta = os.path.dirname(os.path.abspath(self.ruta)) or "."
        fd, temporal = tempfile.mkstemp(dir=carpeta, suffix=".tmp")
        os.close(fd)
        with open(temporal, "w", encoding="utf-8", newline="\n") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, self.ruta)

    # --- API ----------------------------------------------------------
    def crear(self, tipo, id_cedula="", identidad="", datos=None):
        with _LOCK:
            contenido = self._leer()
            id_trabajo = uuid.uuid4().hex[:12]
            contenido["trabajos"][id_trabajo] = {
                "id": id_trabajo,
                "tipo": tipo,
                "id_cedula": id_cedula,
                "identidad": identidad,
                "datos": datos or {},
                "estado": "pedido",
                "motivo": "",
                "creado": time.time(),
                "actualizado": time.time(),
            }
            self._escribir(contenido)
            return contenido["trabajos"][id_trabajo]

    def obtener(self, id_trabajo):
        return self._leer()["trabajos"].get(id_trabajo)

    def listar(self, estado=None):
        trabajos = list(self._leer()["trabajos"].values())
        if estado:
            trabajos = [t for t in trabajos if t["estado"] == estado]
        return sorted(trabajos, key=lambda t: t["creado"])

    def pasar(self, id_trabajo, nuevo, motivo=""):
        if nuevo not in ESTADOS:
            raise TransicionInvalida(f"Estado desconocido: {nuevo}")
        with _LOCK:
            contenido = self._leer()
            trabajo = contenido["trabajos"].get(id_trabajo)
            if not trabajo:
                raise KeyError(f"No existe el trabajo {id_trabajo}")
            actual = trabajo["estado"]
            if nuevo not in TRANSICIONES.get(actual, set()):
                raise TransicionInvalida(f"No se puede pasar de {actual} a {nuevo}")
            trabajo["estado"] = nuevo
            trabajo["motivo"] = motivo or trabajo.get("motivo", "")
            trabajo["actualizado"] = time.time()
            self._escribir(contenido)
            return trabajo

    def encolar(self, id_trabajo):
        return self.pasar(id_trabajo, "en_cola")

    def siguiente(self):
        """Toma el trabajo en cola más viejo y lo pasa a corriendo."""
        en_cola = self.listar("en_cola")
        if not en_cola:
            return None
        return self.pasar(en_cola[0]["id"], "corriendo")

    def recuperar(self):
        """Al arrancar: los inciertos pasan a dudoso y se informan."""
        dudosos = []
        for trabajo in self.lista_incierta():
            dudosos.append(
                self.pasar(
                    trabajo["id"], "dudoso",
                    motivo="el asistente se reinició mientras corría: revisar en SISFE antes de reintentar",
                )
            )
        return dudosos

    def lista_incierta(self):
        return [t for t in self.listar() if t["estado"] in INCIERTOS]

    def vencidos(self, ahora=None):
        """Pasa a error los trabajos que superaron su tiempo límite."""
        ahora = ahora or time.time()
        vencidos = []
        for trabajo in self.listar():
            if trabajo["estado"] in ("listo", "error", "dudoso"):
                continue
            if ahora - trabajo["creado"] > self.ttl:
                vencidos.append(
                    self.pasar(trabajo["id"], "error", motivo="tiempo límite superado")
                )
        return vencidos
