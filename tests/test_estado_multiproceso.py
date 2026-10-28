# -*- coding: utf-8 -*-
"""Dos procesos reales escribiendo el mismo estado.json.

El test de hilos de test_estado.py no alcanza: el portal y la consola local
son procesos separados. Acá se usa multiprocessing con start method "spawn",
que es el modo de Windows, y se verifica que el FileLock + os.replace no
pierdan ninguna actualización.
"""
import json
import multiprocessing
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import estado  # noqa: E402


def _agregar_pendientes(ruta_estado, ruta_log, prefijo, cantidad):
    import estado

    estado.ARCHIVO = ruta_estado
    estado.ARCHIVO_LOG = ruta_log
    for i in range(cantidad):
        estado.agregar_pendiente({
            "id": f"{prefijo}{i}",
            "caratula": f"CASO {prefijo}{i}",
        })


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    yield tmp_path


def test_dos_procesos_no_pierden_pendientes(_archivos_temporales):
    ctx = multiprocessing.get_context("spawn")
    procesos = [
        ctx.Process(
            target=_agregar_pendientes,
            args=(estado.ARCHIVO, estado.ARCHIVO_LOG, prefijo, 20),
        )
        for prefijo in ("a", "b")
    ]

    for proceso in procesos:
        proceso.start()
    for proceso in procesos:
        proceso.join(30)
        assert not proceso.is_alive()
        assert proceso.exitcode == 0

    with open(estado.ARCHIVO, encoding="utf-8") as f:
        data = json.load(f)

    ids = {p["id"] for p in data["pendientes"]}
    assert len(ids) == 40
    assert ids == {f"{prefijo}{i}" for prefijo in ("a", "b") for i in range(20)}

    with open(estado.ARCHIVO_LOG, encoding="utf-8") as f:
        assert len([l for l in f if l.strip()]) == 40
