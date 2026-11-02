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
# ============================================================

import json
import os

ARCHIVOS_JSON_VACIO = ["estado.json", "cedulas_procesadas.json", "estado_expedientes.json"]


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _escribir(ruta, contenido):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)


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
            # Conservar los pendientes: son decretos ya detectados que
            # esperan clasificación humana. Lo único que se vacía son las
            # cédulas generadas.
            actual = _leer(ruta)
            contenido = {
                "cedulas": [],
                "pendientes": actual.get("pendientes", []),
            }
        else:
            contenido = {}
        _escribir(ruta, contenido)
        resultados.append((nombre, "vaciado"))
    return resultados


def main():
    for nombre, resultado in resetear():
        if resultado == "vaciado":
            print(f"  ✓ {nombre} vaciado")
        else:
            print(f"  - {nombre} no existía, no hace falta nada")
    print("\nListo. Los registros quedaron limpios (los pendientes se conservaron).")


if __name__ == "__main__":
    main()
