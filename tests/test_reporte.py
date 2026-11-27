# -*- coding: utf-8 -*-
"""Reporte exportable de cédulas (CSV para archivar o enviar al estudio)."""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from fastapi.testclient import TestClient

import estado
import servidor


@pytest.fixture
def cliente():
    return TestClient(servidor.app, base_url="http://localhost:8000")


@pytest.fixture
def con_cedulas(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log.jsonl"))
    estado.guardar({"cedulas": [
        {
            "id": "c-uno",
            "caratula": "PEREZ, JUAN",
            "cuij": "PRUEBA-0001",
            "estado": "firmada",
            "identidad_cadena": "Santiago",
            "fecha_generada": "2026-11-01T10:00",
            "ruta_firmada": "uploads/c-uno/firmado.pdf",
        },
        {
            "id": "c-dos",
            "caratula": "GOMEZ, ANA",
            "cuij": "PRUEBA-0002",
            "estado": "generada",
            "identidad_cadena": "Jr",
            "fecha_generada": "2026-11-02T11:00",
        },
    ]})
    return tmp_path


def test_reporte_csv_descarga(cliente, con_cedulas):
    r = cliente.get("/api/reporte.csv")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "reporte-" in r.headers["content-disposition"]


def test_reporte_csv_tiene_las_columnas(cliente, con_cedulas):
    r = cliente.get("/api/reporte.csv")
    primera = r.text.splitlines()[0].lstrip("\ufeff")
    for col in ("id", "caratula", "cuij", "estado", "identidad", "fecha_generada", "tiene_firmado"):
        assert col in primera


def test_reporte_csv_marca_las_firmadas(cliente, con_cedulas):
    r = cliente.get("/api/reporte.csv")
    lineas = r.text.splitlines()
    assert any("PEREZ, JUAN" in l and "si" in l for l in lineas)
    assert any("GOMEZ, ANA" in l and "no" in l for l in lineas)


def test_reporte_csv_sin_cedulas(cliente, tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "vacio.json"))
    estado.guardar({"cedulas": []})
    r = cliente.get("/api/reporte.csv")
    assert r.status_code == 200
    assert len(r.text.strip().splitlines()) == 1
