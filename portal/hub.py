# -*- coding: utf-8 -*-
# ============================================================
#  PORTAL/HUB.PY — Lectura del estado real del estudio
# ------------------------------------------------------------
#  El portal NO tiene estado propio: lee `estado.json` y
#  `log_acciones.jsonl`, que son la única fuente de verdad
#  (módulo `estado.py` de la raíz del repo).
#
#  Este módulo NO usa `estado.cargar()` ni `estado.leer_log()`
#  porque esos caminos toman un `FileLock` que CREA
#  `<archivo>.lock` en la carpeta del estado (estado.py:95). El
#  portal solo lee: si el archivo falta, está bloqueado o tiene
#  JSON corrupto, devuelve vacío, avisa por el log del servidor
#  y no escribe ni crea nada.
#
#  Tampoco devuelve las cédulas crudas: `estado.json` trae rutas
#  locales (ruta_pdf, ruta_firmada) y textos largos que el portal
#  no necesita ver. Cada cédula sale con una lista FIJA de campos.
# ============================================================

import json
import logging
import os
import time

from . import db

#: Campos de una cédula que el portal puede mostrar.
CAMPOS_CEDULA = (
    "id",
    "caratula",
    "cuij",
    "estado",
    "identidad_cadena",
    "tipo",
    "fecha_generada",
    "fecha_firmada",
)

#: Campos de un pendiente (los textos largos no salen del hub).
CAMPOS_PENDIENTE = ("id", "caratula", "cuij", "tipo_sugerido", "fecha_decreto")

#: Campos de una entrada del log. `usuario` y `maquina` son el usuario de
#: Windows y el nombre de la PC: solo salen para un administrador.
CAMPOS_ACTIVIDAD = (
    "fecha_hora",
    "accion",
    "id",
    "caratula",
    "cuij",
    "operador",
    "identidad",
    "detalle",
)
CAMPOS_ACTIVIDAD_ORIGEN = ("usuario", "maquina")

#: El `detalle` de una entrada puede traer rutas locales: se recorta.
TOPE_DETALLE_ACTIVIDAD = 200

#: Techo de `?limite=` en los listados (el hub relee el archivo en cada pedido).
LIMITE_MAXIMO = 200
LIMITE_POR_DEFECTO = 50

_REINTENTOS_LECTURA = 3


def _avisar(mensaje):
    logging.getLogger("portal.hub").warning(mensaje)


def _modulo_estado():
    """El módulo `estado` de la raíz del repo (fuente de las rutas)."""
    import estado

    return estado


def rutas(ruta_estado=None, ruta_log=None):
    """Rutas efectivas del estado y del log (permite inyectarlas en tests)."""
    modulo = _modulo_estado()
    return (
        ruta_estado or getattr(modulo, "ARCHIVO", "estado.json"),
        ruta_log or getattr(modulo, "ARCHIVO_LOG", "log_acciones.jsonl"),
    )


def _leer_json(ruta):
    """Contenido del estado, o None si no se puede leer. Nunca escribe."""
    if not ruta or not os.path.isfile(ruta):
        _avisar(f"No está {ruta or 'estado.json'}: el portal muestra el estado vacío.")
        return None
    for intento in range(1, _REINTENTOS_LECTURA + 1):
        try:
            with open(ruta, encoding="utf-8") as archivo:
                datos = json.load(archivo)
            break
        except PermissionError:
            # Windows: otro proceso lo tiene abierto justo mientras lo reemplaza.
            if intento == _REINTENTOS_LECTURA:
                _avisar(f"No pude leer {ruta}: sigue bloqueado por otro proceso.")
                return None
            time.sleep(0.05)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _avisar(f"{ruta} no es un JSON válido ({e}): se muestra vacío.")
            return None
        except OSError as e:
            _avisar(f"No pude leer {ruta} ({e}): se muestra vacío.")
            return None
    if not isinstance(datos, dict):
        _avisar(f"{ruta} no tiene el formato esperado: se muestra vacío.")
        return None
    return datos


def _campos(datos, campos):
    """Solo los campos de la lista, como texto ('' si falta)."""
    limpio = {}
    for campo in campos:
        valor = (datos or {}).get(campo, "")
        limpio[campo] = "" if valor is None else str(valor)
    return limpio


def cedula_publica(cedula):
    """Una cédula con la lista fija de campos (sin rutas ni textos)."""
    return _campos(cedula, CAMPOS_CEDULA)


def pendiente_publico(pendiente):
    """Un pendiente con la lista fija de campos (sin textos del decreto)."""
    return _campos(pendiente, CAMPOS_PENDIENTE)


def estado(ruta_estado=None, ruta_log=None):
    """Cédulas y pendientes del estado real, ya recortados a campos públicos."""
    datos = _leer_json(rutas(ruta_estado, ruta_log)[0]) or {}
    cedulas = [
        cedula_publica(c) for c in datos.get("cedulas", []) if isinstance(c, dict)
    ]
    pendientes = [
        pendiente_publico(p) for p in datos.get("pendientes", []) if isinstance(p, dict)
    ]
    return {"cedulas": cedulas, "pendientes": pendientes}


def cedulas(ruta_estado=None, ruta_log=None):
    """Las cédulas, las más nuevas primero.

    `estado.json` no garantiza orden. Las que no tienen `fecha_generada`
    quedan al final, conservando el orden del archivo.
    """
    lista = estado(ruta_estado, ruta_log)["cedulas"]
    return ordenar_por_fecha(lista)


def ordenar_por_fecha(lista):
    """Ordena cédulas por `fecha_generada` descendente (sin fecha, al final)."""
    return sorted(lista, key=lambda c: c.get("fecha_generada") or "", reverse=True)


def ids_con_pdf(ruta_estado=None, ruta_log=None):
    """Ids de cédulas cuyo PDF firmado existe DENTRO de PORTAL_UPLOADS.

    Una sola lectura del archivo para todo el panel. Devuelve solo ids: el hub
    no expone `ruta_firmada` ni ninguna otra ruta.

    Se usa la misma validación de ruta que el endpoint de descarga
    (`db.dentro_de_uploads`): si acá alcanzara con que el archivo exista, el
    panel mostraría "Descargar firmado" para un PDF guardado fuera de la
    carpeta y el enlace respondería 404.

    Costo: un `os.path.isfile` por cédula en cada render. Con el volumen del
    estudio (decenas a algunos cientos de cédulas) es despreciable; si algún
    día crece, conviene cachear el set por versión del estado.
    """
    datos = _leer_json(rutas(ruta_estado, ruta_log)[0]) or {}
    salida = set()
    for cedula in datos.get("cedulas", []):
        if not isinstance(cedula, dict):
            continue
        ruta = str(cedula.get("ruta_firmada") or "")
        if ruta and db.dentro_de_uploads(ruta) and os.path.isfile(ruta):
            salida.add(str(cedula.get("id") or ""))
    return salida


def buscar_cedula(id_cedula, ruta_estado=None, ruta_log=None):
    """La cédula con ese id, o None."""
    buscado = str(id_cedula or "").strip()
    for cedula in cedulas(ruta_estado, ruta_log):
        if cedula.get("id") == buscado:
            return cedula
    return None


def actividad(ruta_log=None, incluir_origen=False):
    """Entradas del log, más nuevas primero, recortadas a campos fijos.

    `incluir_origen=True` agrega `usuario` y `maquina` (usuario de Windows y
    nombre de la PC): solo para un administrador. El `detalle` se recorta a
    200 caracteres porque puede traer rutas locales.

    El filtro por identidad lo aplica el servidor (en Python, con
    `permisos.normalizar`) y el límite va DESPUÉS de filtrar.
    """
    ruta = rutas(ruta_log=ruta_log)[1]
    if not ruta or not os.path.isfile(ruta):
        _avisar(f"No está {ruta or 'log_acciones.jsonl'}: no hay actividad.")
        return []
    crudas = []
    try:
        with open(ruta, encoding="utf-8") as archivo:
            for numero, linea in enumerate(archivo, 1):
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    crudas.append(json.loads(linea))
                except json.JSONDecodeError:
                    # Una escritura concurrente puede dejar la última línea a
                    # medio escribir: se ignora esa línea, no todo el archivo.
                    _avisar(f"Línea {numero} de {ruta} no es JSON válido: se ignora.")
    except OSError as e:
        _avisar(f"No pude leer {ruta} ({e}): no hay actividad.")
        return []
    campos = CAMPOS_ACTIVIDAD + (
        CAMPOS_ACTIVIDAD_ORIGEN if incluir_origen else ()
    )
    salida = []
    for entrada in reversed(crudas):
        if not isinstance(entrada, dict):
            continue
        limpia = _campos(entrada, campos)
        limpia["detalle"] = limpia["detalle"][:TOPE_DETALLE_ACTIVIDAD]
        salida.append(limpia)
    return salida
