# -*- coding: utf-8 -*-
# ============================================================
#  ESTADO.PY — Registro de cédulas (estado.json) + log de acciones
# ------------------------------------------------------------
#  Es el puente entre la skill (que genera las cédulas) y el
#  dashboard (que las muestra y dispara firma/subida).
#
#  Los PDF son TRANSITORIOS: viven mientras dura el trámite (generar →
#  firmar → subir) y se borran solos al quedar presentados. Lo que
#  queda para siempre es el LOG DE ACCIONES (log_acciones.jsonl):
#  un registro con fecha y hora de cada paso, que sobrevive aunque
#  el archivo ya no exista.
#
#  Concurrencia (Fase 0): toda secuencia cargar → modificar → guardar
#  corre bajo un mismo lock (RLock), para que dos trabajos en paralelo
#  (ej: firma en lote + subida a Meta) no se pisen actualizaciones.
# ============================================================

import os
import json
import threading
import datetime

ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado.json")
ARCHIVO_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_acciones.jsonl")
# RLock: las operaciones compuestas (cargar → modificar → guardar) vuelven
# a entrar al lock desde cargar()/guardar() sin deadlock.
_lock = threading.RLock()


def _leer_disco():
    """Lee el JSON sin lock (solo para uso interno de cargar())."""
    if not os.path.isfile(ARCHIVO):
        return {"cedulas": [], "pendientes": []}
    with open(ARCHIVO, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("cedulas", [])
    data.setdefault("pendientes", [])
    return data


def cargar():
    """Devuelve el estado completo. Lectura bajo lock: aunque sea de solo
    lectura, evita leer a mitad de una escritura de otro hilo."""
    with _lock:
        return _leer_disco()


def guardar(data):
    with _lock:
        with open(ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _mutar(modificador):
    """Aplica modificador(data) en una operación atómica y persiste.

    Es la ÚNICA vía para cambiar el estado: el lock cubre la secuencia
    completa cargar → modificar → guardar, así dos hilos no pierden
    actualizaciones (cada uno lee el resultado del anterior).
    """
    with _lock:
        data = _leer_disco()
        modificador(data)
        guardar(data)
        return data


def _ahora():
    return datetime.datetime.now().isoformat(timespec="seconds")


# --- Log de acciones (append-only, sobrevive a los archivos) ------
def registrar_log(accion, id_cedula, caratula="", cuij="", detalle=""):
    """
    Agrega una línea al log de acciones. No se pisa nunca — cada llamada
    suma una entrada nueva. `accion` típicas: "generada", "firmada",
    "presentada", "eliminado_pdf", "error_eliminar_pdf".
    """
    entrada = {
        "fecha_hora": _ahora(),
        "accion": accion,
        "id": id_cedula,
        "caratula": caratula,
        "cuij": cuij,
        "detalle": detalle,
    }
    with _lock:
        with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    return entrada


def leer_log(limite=None):
    """Devuelve las entradas del log, más recientes primero."""
    if not os.path.isfile(ARCHIVO_LOG):
        return []
    with open(ARCHIVO_LOG, encoding="utf-8") as f:
        lineas = [json.loads(l) for l in f if l.strip()]
    lineas.reverse()
    return lineas[:limite] if limite else lineas


def _actualizar(id_cedula, **campos):
    def mod(data):
        for c in data["cedulas"]:
            if c.get("id") == id_cedula:
                c.update(campos)
    return _mutar(mod)


# --- Pendientes de clasificar (el decreto ya se detectó, falta que ---
# --- el abogado elija el tipo de cédula antes de generar el PDF) -----
def agregar_pendiente(pendiente):
    """
    pendiente: dict con los mismos campos que espera generar_cedula.generar()
    (caratula, cuij, radicado, ciudad, fecha_decreto, texto_decreto,
    novedad, destinatarios, y los extras de audiencia si los hay) MÁS
    "tipo_sugerido" (lo que las reglas hubieran elegido solas, para
    preseleccionar en el dashboard). Todavía NO tiene "tipo" definitivo
    ni se generó ningún PDF.
    """
    def mod(data):
        data["pendientes"] = [p for p in data["pendientes"] if p.get("id") != pendiente["id"]]
        data["pendientes"].append(pendiente)
    _mutar(mod)
    registrar_log("pendiente_detectado", pendiente["id"], pendiente.get("caratula", ""), pendiente.get("cuij", ""))


def obtener_pendiente(id_pendiente):
    data = cargar()
    for p in data.get("pendientes", []):
        if p.get("id") == id_pendiente:
            return p
    return None


def eliminar_pendiente(id_pendiente):
    def mod(data):
        data["pendientes"] = [p for p in data.get("pendientes", []) if p.get("id") != id_pendiente]
    _mutar(mod)


def marcar_atencion(id_cedula, motivo, etiqueta="Solicita Revisión"):
    """
    Marca la cédula como 'atencion' — el mismo estado que ya usa el
    dashboard para Bus Federal y decretos ambiguos (se muestra en la
    sección "Requieren atención" con el motivo, sin necesitar ningún
    cambio de pantalla nuevo).
    """
    cedula = obtener_cedula(id_cedula) or {}
    _actualizar(id_cedula, estado="atencion", reason=f"{etiqueta}: {motivo}")
    registrar_log("atencion", id_cedula, cedula.get("caratula", ""), cedula.get("cuij", ""), motivo)


def marcar_firmada(id_cedula, ruta_firmada):
    cedula = obtener_cedula(id_cedula) or {}
    _actualizar(id_cedula, estado="firmada", ruta_firmada=ruta_firmada, fecha_firmada=_ahora())
    registrar_log("firmada", id_cedula, cedula.get("caratula", ""), cedula.get("cuij", ""), ruta_firmada or "")


def marcar_presentada(id_cedula):
    """
    Marca la cédula como presentada Y borra los PDF locales (original y
    firmado) — ya cumplieron su función. El registro de que existieron
    y qué pasó con ellos queda en el log de acciones, no en el disco.
    """
    cedula = obtener_cedula(id_cedula) or {}
    _actualizar(id_cedula, estado="presentada", fecha_presentada=_ahora())
    registrar_log("presentada", id_cedula, cedula.get("caratula", ""), cedula.get("cuij", ""))

    for campo in ("ruta_pdf", "ruta_firmada"):
        ruta = cedula.get(campo)
        if ruta and os.path.isfile(ruta):
            try:
                os.remove(ruta)
                registrar_log("eliminado_pdf", id_cedula, cedula.get("caratula", ""),
                              cedula.get("cuij", ""), f"{campo}: {ruta}")
            except Exception as e:
                registrar_log("error_eliminar_pdf", id_cedula, cedula.get("caratula", ""),
                              cedula.get("cuij", ""), f"{campo}: {ruta} -> {e}")


def reiniciar_estado(id_cedula):
    _actualizar(id_cedula, estado="generada", ruta_firmada=None)


def obtener_cedula(id_cedula):
    data = cargar()
    for c in data.get("cedulas", []):
        if c.get("id") == id_cedula:
            return c
    return None


def eliminar_cedula(id_cedula):
    def mod(data):
        data["cedulas"] = [c for c in data.get("cedulas", []) if c.get("id") != id_cedula]
    return _mutar(mod)


def editar_cedula(id_cedula, nuevos_datos):
    return _actualizar(id_cedula, **nuevos_datos)


# --- Función que llamaría la skill al generar una cédula ----------
def registrar_cedula(cedula):
    """
    cedula: dict con al menos id, caratula, cuij, ruta_pdf, estado='generada'.
    Si ya existe (mismo id) la reemplaza; si no, la agrega.
    """
    cedula.setdefault("fecha_generada", _ahora())
    def mod(data):
        data["cedulas"] = [c for c in data["cedulas"] if c.get("id") != cedula["id"]]
        data["cedulas"].append(cedula)
    _mutar(mod)
    registrar_log("generada", cedula["id"], cedula.get("caratula", ""), cedula.get("cuij", ""))
