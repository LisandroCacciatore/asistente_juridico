# -*- coding: utf-8 -*-
"""Escritura atómica y log con operador/identidad explícitos.

La consola local y el portal son dos procesos distintos. `estado.py` tiene
que sobrevivir a que los dos escriban a la vez y a que uno muera a mitad de
una escritura.
"""
import json
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import estado  # noqa: E402


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    yield tmp_path


def test_guardar_no_deja_temporales(_archivos_temporales):
    estado.guardar({"cedulas": [{"id": "c1"}], "pendientes": []})

    with open(estado.ARCHIVO, encoding="utf-8") as f:
        assert json.load(f)["cedulas"][0]["id"] == "c1"
    assert list(_archivos_temporales.glob("*.tmp")) == []


def test_si_falla_la_serializacion_no_pisa_el_original(_archivos_temporales, monkeypatch):
    original = {"cedulas": [{"id": "c1"}], "pendientes": []}
    estado.guardar(original)

    def falla(*args, **kwargs):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(estado.json, "dump", falla)
    with pytest.raises(RuntimeError):
        estado.guardar({"cedulas": [], "pendientes": []})

    with open(estado.ARCHIVO, encoding="utf-8") as f:
        assert json.load(f) == original
    assert list(_archivos_temporales.glob("*.tmp")) == []


def test_registrar_log_acepta_operador_e_identidad_explicitos(_archivos_temporales):
    entrada = estado.registrar_log(
        "pdf_subido",
        "c1",
        detalle="sha256=abc",
        operador="Jr",
        identidad="Santiago",
        usuario="win-jr",
        maquina="PC-JR",
    )

    assert entrada["operador"] == "Jr"
    assert entrada["identidad"] == "Santiago"
    assert entrada["usuario"] == "win-jr"
    assert entrada["maquina"] == "PC-JR"

    log = estado.leer_log()
    assert log[0]["operador"] == "Jr"
    assert log[0]["identidad"] == "Santiago"
    assert log[0]["detalle"] == "sha256=abc"
