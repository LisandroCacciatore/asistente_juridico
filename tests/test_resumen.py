# -*- coding: utf-8 -*-
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import pytest
from fastapi.testclient import TestClient
import estado
import servidor


@pytest.fixture
def cliente():
    return TestClient(servidor.app)


CEDULAS = {"cedulas": [
    {"id": "c1", "caratula": "ALFA, UNO", "cuij": "111", "estado": "firmada",
     "identidad_cadena": "Santiago", "ruta_firmada": "a.pdf"},
    {"id": "c2", "caratula": "BETA, DOS", "cuij": "222", "estado": "generada",
     "identidad_cadena": "Jr"},
]}


def test_resumen_texto_sin_datos_de_clientes(cliente, tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "e.json"))
    estado.guardar(CEDULAS)
    r = cliente.get("/api/resumen")
    assert r.status_code == 200
    assert "Total: 2" in r.text
    assert "firmada: 1" in r.text
    assert "ALFA" not in r.text
    assert "111" not in r.text


def test_resumen_json(cliente, tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "e.json"))
    estado.guardar(CEDULAS)
    d = cliente.get("/api/resumen?formato=json").json()
    assert d["total"] == 2
    assert d["por_estado"]["firmada"] == 1
    assert d["por_identidad"]["Jr"] == 1


def test_cors_no_expone_a_origen_ajeno(cliente):
    r = cliente.get("/api/resumen", headers={"Origin": "https://evil.example"})
    claves = {k.lower() for k in r.headers}
    assert "access-control-allow-origin" not in claves


def test_cors_permite_el_origen_propio(cliente):
    r = cliente.get("/api/resumen", headers={"Origin": "http://localhost:8000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8000"
