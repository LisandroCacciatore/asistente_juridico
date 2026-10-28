# -*- coding: utf-8 -*-
"""Dos procesos reales escribiendo el mismo estado.json.

El test de hilos de test_estado.py no alcanza: el portal y la consola local
son procesos separados. Acá se lanzan dos procesos de Python y se verifica
que el FileLock + os.replace no pierdan ninguna actualización.
"""
import json
import os
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import estado  # noqa: E402


TRABAJADOR = r"""
import os
import sys

sys.path.insert(0, os.getcwd())
import estado

estado.ARCHIVO = sys.argv[1]
estado.ARCHIVO_LOG = sys.argv[2]
prefijo = sys.argv[3]
cantidad = int(sys.argv[4])

for i in range(cantidad):
    estado.agregar_pendiente({
        "id": f"{prefijo}{i}",
        "caratula": f"CASO {prefijo}{i}",
    })
"""


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    yield tmp_path


def test_dos_procesos_no_pierden_pendientes(_archivos_temporales):
    procesos = []
    for prefijo in ("a", "b"):
        procesos.append(subprocess.Popen(
            [sys.executable, "-c", TRABAJADOR,
             estado.ARCHIVO, estado.ARCHIVO_LOG, prefijo, "20"],
            cwd=RAIZ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ))

    for proceso in procesos:
        salida, error = proceso.communicate(timeout=30)
        assert proceso.returncode == 0, (salida, error)

    with open(estado.ARCHIVO, encoding="utf-8") as f:
        data = json.load(f)

    ids = {p["id"] for p in data["pendientes"]}
    assert len(ids) == 40
    assert ids == {f"{prefijo}{i}" for prefijo in ("a", "b") for i in range(20)}

    with open(estado.ARCHIVO_LOG, encoding="utf-8") as f:
        assert len([l for l in f if l.strip()]) == 40
