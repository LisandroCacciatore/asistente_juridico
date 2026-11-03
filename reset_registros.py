# -*- coding: utf-8 -*-
# ============================================================
#  RESET_REGISTROS.PY — Vacía los registros de trabajo, sin perder
#  lo que todavía no se clasificó.
# ------------------------------------------------------------
#  estado.json guarda dos cosas distintas:
#    - "cedulas"    : cédulas ya generadas (se pueden regenerar).
#    - "pendientes" : decretos detectados que todavía esperan que una
#                     persona elija el tipo de cédula. Eso NO se
#                     regenera solo: si se vacía, se pierde el trabajo
#                     de detección y hay que volver a correr el monitor.
#
#  Por eso el reset vacía las cédulas y CONSERVA los pendientes. Los
#  otros dos registros (cedulas_procesadas.json y estado_expedientes.json)
#  son de control del monitor y sí se vacían completos.
#
#  estado.json se toca con estado._mutar cuando es el archivo real: así
#  toma el RLock y el FileLock y escribe con os.replace. Un reset con la
#  consola o el portal abiertos no puede pisarlos.
# ============================================================

import json
import os

import estado

ARCHIVOS_JSON_VACIO = ["estado.json", "cedulas_procesadas.json", "estado_expedientes.json"]


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)


def _misma_ruta(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _vaciar_estado(ruta):
    """Vacía las cédulas y conserva los pendientes.

    Si `ruta` es el estado.json real, usa estado._mutar: lock de hilo y de
    archivo, y escritura atómica. Para una carpeta de prueba (otra ruta),
    escribe directo, que es lo que necesitan los tests.
    """
    if _misma_ruta(ruta, estado.ARCHIVO):
        def mod(data):
            data["cedulas"] = []
            data.setdefault("pendientes", [])
        estado._mutar(mod)
        return

    actual = _leer(ruta)
    _escribir(ruta, {
        "cedulas": [],
        "pendientes": actual.get("pendientes", []),
    })


def resetear(directorio=None):
    """Vacía los registros de `directorio` (por defecto, esta carpeta).

    Devuelve una lista de (nombre, resultado) con resultado "vaciado" o
    "no existia". No crea archivos que no estaban: si un registro no existe,
    no hace falta nada.
    """
    directorio = directorio or os.path.dirname(os.path.abspath(__file__))
    resultados = []
    for nombre in ARCHIVOS_JSON_VACIO:
        ruta = os.path.join(directorio, nombre)
        if not os.path.isfile(ruta):
            resultados.append((nombre, "no existia"))
            continue
        if nombre == "estado.json":
            _vaciar_estado(ruta)
        else:
            # Los dos registros del monitor son dicts: {} es su vacío real
            # (monitor_playwright.cargar_registro/cargar_estado devuelven {}).
            _escribir(ruta, {})
        resultados.append((nombre, "vaciado"))
    return resultados


def _confirmar():
    print("  ⚠ Cerrá la consola, el portal y el monitor antes de correr esto:")
    print("    los tres escriben estos archivos.")
    try:
        respuesta = input("  ¿Vaciar los registros? Los pendientes se conservan. [s/N]: ")
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelado.")
        return False
    return respuesta.strip().lower() in ("s", "si", "sí", "y", "yes")


def main():
    if not _confirmar():
        print("  No se tocó nada.")
        return
    for nombre, resultado in resetear():
        if resultado == "vaciado":
            print(f"  ✓ {nombre} vaciado")
        else:
            print(f"  - {nombre} no existía, no hace falta nada")
    print("\nListo. Los registros quedaron limpios (los pendientes se conservaron).")


if __name__ == "__main__":
    main()
