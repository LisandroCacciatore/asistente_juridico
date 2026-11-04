# -*- coding: utf-8 -*-
"""El hub de lectura: estado.json y log_acciones.jsonl, sin escribir nada."""
import json
import os

import pytest

from portal import hub


@pytest.fixture
def rutas(tmp_path):
    return str(tmp_path / "estado.json"), str(tmp_path / "log_acciones.jsonl")


def _escribir(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False)


def test_estado_faltante_devuelve_vacio_y_avisa(rutas, caplog):
    ruta_estado, ruta_log = rutas
    with caplog.at_level("WARNING", logger="portal.hub"):
        datos = hub.estado(ruta_estado, ruta_log)
    assert datos == {"cedulas": [], "pendientes": []}
    assert "No está" in caplog.text
    # Solo lectura: no creó el archivo ni un .lock al lado.
    assert not os.path.exists(ruta_estado)
    assert not os.path.exists(ruta_estado + ".lock")


def test_estado_corrupto_devuelve_vacio_y_no_rompe(rutas, caplog):
    ruta_estado, ruta_log = rutas
    with open(ruta_estado, "w", encoding="utf-8") as archivo:
        archivo.write("{ esto no es json")
    with caplog.at_level("WARNING", logger="portal.hub"):
        datos = hub.estado(ruta_estado, ruta_log)
    assert datos == {"cedulas": [], "pendientes": []}
    assert "no es un JSON válido" in caplog.text


def test_cedula_sale_con_campos_fijos_y_sin_rutas(rutas):
    ruta_estado, ruta_log = rutas
    _escribir(ruta_estado, {"cedulas": [{
        "id": "c1", "caratula": "Perez", "cuij": "CUIJ-1", "estado": "generada",
        "identidad_cadena": "Santiago", "tipo": "cedula",
        "fecha_generada": "2026-11-01T10:00:00", "fecha_firmada": "",
        "ruta_pdf": "C:/privado/cedula.pdf",
        "ruta_firmada": "C:/privado/firmada.pdf",
        "texto_decreto": "texto larguisimo", "detalle": "x",
    }]})
    cedula = hub.cedulas(ruta_estado, ruta_log)[0]
    assert set(cedula) == set(hub.CAMPOS_CEDULA)
    assert "ruta_pdf" not in cedula
    assert "ruta_firmada" not in cedula
    assert "texto_decreto" not in cedula
    assert cedula["identidad_cadena"] == "Santiago"


def test_pendiente_sale_sin_textos(rutas):
    ruta_estado, ruta_log = rutas
    _escribir(ruta_estado, {"pendientes": [{
        "id": "p1", "caratula": "Perez", "cuij": "CUIJ-1",
        "tipo_sugerido": "cedula", "fecha_decreto": "2026-10-01",
        "texto_decreto": "texto", "destinatarios": ["a"], "novedad": "x",
    }]})
    pendiente = hub.estado(ruta_estado, ruta_log)["pendientes"][0]
    assert set(pendiente) == set(hub.CAMPOS_PENDIENTE)
    assert "texto_decreto" not in pendiente
    assert "destinatarios" not in pendiente


def test_cedulas_mas_nuevas_primero(rutas):
    ruta_estado, ruta_log = rutas
    _escribir(ruta_estado, {"cedulas": [
        {"id": "vieja", "fecha_generada": "2026-01-01T00:00:00"},
        {"id": "nueva", "fecha_generada": "2026-11-01T00:00:00"},
        {"id": "sin_fecha"},
    ]})
    assert [c["id"] for c in hub.cedulas(ruta_estado, ruta_log)] == [
        "nueva", "vieja", "sin_fecha"
    ]


def test_buscar_cedula(rutas):
    ruta_estado, ruta_log = rutas
    _escribir(ruta_estado, {"cedulas": [{"id": "c1"}, {"id": "c2"}]})
    assert hub.buscar_cedula("c2", ruta_estado, ruta_log)["id"] == "c2"
    assert hub.buscar_cedula("no-existe", ruta_estado, ruta_log) is None


def test_actividad_ignora_lineas_rotas(rutas, caplog):
    ruta_estado, ruta_log = rutas
    with open(ruta_log, "w", encoding="utf-8") as archivo:
        archivo.write(json.dumps({"accion": "generada", "identidad": "Santiago"}) + "\n")
        archivo.write('{"accion": "firmada", "ident')  # escritura a medias
        archivo.write("\n")
        archivo.write(json.dumps({"accion": "presentada", "identidad": "Jr"}) + "\n")
    with caplog.at_level("WARNING", logger="portal.hub"):
        entradas = hub.actividad(ruta_log=ruta_log)
    assert [e["accion"] for e in entradas] == ["presentada", "generada"]
    assert "no es JSON válido" in caplog.text


def test_actividad_faltante_devuelve_vacio(rutas, caplog):
    _ruta_estado, ruta_log = rutas
    with caplog.at_level("WARNING", logger="portal.hub"):
        assert hub.actividad(ruta_log=ruta_log) == []
    assert "No está" in caplog.text


def test_rutas_por_defecto_salen_del_modulo_estado(monkeypatch, tmp_path):
    import estado

    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "e.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "l.jsonl"))
    assert hub.rutas() == (str(tmp_path / "e.json"), str(tmp_path / "l.jsonl"))
