# -*- coding: utf-8 -*-
"""El reset de registros vacía lo regenerable y conserva los pendientes.

`estado.json` tiene dos cosas distintas: las cédulas (se regeneran) y los
pendientes (decretos detectados que esperan clasificación humana). Vaciar los
pendientes perdería trabajo que el monitor ya hizo.

Los otros dos registros son dicts para el monitor: su vacío correcto es `{}`,
no una lista.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import estado  # noqa: E402
import reset_registros  # noqa: E402


def _escribir(ruta, datos):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def test_vacia_cedulas_y_conserva_pendientes(tmp_path):
    pendientes = [
        {"id": "p1", "caratula": "PEREZ C/ ART"},
        {"id": "p2", "caratula": "GOMEZ C/ PROVINCIA"},
    ]
    _escribir(tmp_path / "estado.json", {
        "cedulas": [{"id": "c1"}, {"id": "c2"}],
        "pendientes": pendientes,
    })
    _escribir(tmp_path / "cedulas_procesadas.json", {"21-00000001-0": "ok"})
    _escribir(tmp_path / "estado_expedientes.json", {"21-00000001-0": {"visto": True}})

    reset_registros.resetear(str(tmp_path))

    estado_json = _leer(tmp_path / "estado.json")
    assert estado_json["cedulas"] == []
    assert estado_json["pendientes"] == pendientes
    assert _leer(tmp_path / "cedulas_procesadas.json") == {}
    assert _leer(tmp_path / "estado_expedientes.json") == {}


def test_estado_queda_con_cedulas_lista_y_pendientes_lista(tmp_path):
    _escribir(tmp_path / "estado.json", {
        "cedulas": [{"id": "c1"}],
        "pendientes": [{"id": "p1"}],
    })

    reset_registros.resetear(str(tmp_path))

    estado_json = _leer(tmp_path / "estado.json")
    assert isinstance(estado_json["cedulas"], list)
    assert isinstance(estado_json["pendientes"], list)
    assert estado_json == {"cedulas": [], "pendientes": [{"id": "p1"}]}


def test_cedulas_procesadas_queda_como_dict_vacio(tmp_path):
    # monitor_playwright.cargar_registro() espera un dict {cuij: {decreto: ...}}.
    _escribir(tmp_path / "cedulas_procesadas.json", {
        "21-00000001-0": {"decreto-1": {"archivos": []}},
    })

    reset_registros.resetear(str(tmp_path))

    datos = _leer(tmp_path / "cedulas_procesadas.json")
    assert isinstance(datos, dict)
    assert datos == {}


def test_estado_expedientes_queda_como_dict_vacio(tmp_path):
    # monitor_playwright.cargar_estado() espera un dict {cuij: {...}}.
    _escribir(tmp_path / "estado_expedientes.json", {
        "21-00000001-0": {"cantidad_movimientos": 3},
    })

    reset_registros.resetear(str(tmp_path))

    datos = _leer(tmp_path / "estado_expedientes.json")
    assert isinstance(datos, dict)
    assert datos == {}


def test_estado_real_usa_el_lock_de_estado(tmp_path, monkeypatch):
    """El estado.json real se toca con estado._mutar (lock + escritura atómica)."""
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    _escribir(tmp_path / "estado.json", {
        "cedulas": [{"id": "c1"}],
        "pendientes": [{"id": "p1"}],
    })

    llamadas = {"n": 0}
    mutar_real = estado._mutar

    def mutar_espia(modificador):
        llamadas["n"] += 1
        return mutar_real(modificador)

    monkeypatch.setattr(estado, "_mutar", mutar_espia)

    reset_registros.resetear(str(tmp_path))

    assert llamadas["n"] == 1
    assert _leer(tmp_path / "estado.json") == {
        "cedulas": [],
        "pendientes": [{"id": "p1"}],
    }


def test_estado_sin_pendientes_queda_con_lista_vacia(tmp_path):
    _escribir(tmp_path / "estado.json", {"cedulas": [{"id": "c1"}]})

    reset_registros.resetear(str(tmp_path))

    assert _leer(tmp_path / "estado.json") == {"cedulas": [], "pendientes": []}


def test_no_crea_archivos_que_no_existen(tmp_path):
    reset_registros.resetear(str(tmp_path))

    assert not (tmp_path / "estado.json").exists()
    assert not (tmp_path / "cedulas_procesadas.json").exists()
    assert not (tmp_path / "estado_expedientes.json").exists()


def test_informa_que_hizo_con_cada_registro(tmp_path):
    _escribir(tmp_path / "estado.json", {"cedulas": [], "pendientes": []})

    resultados = dict(reset_registros.resetear(str(tmp_path)))

    assert resultados["estado.json"] == "vaciado"
    assert resultados["cedulas_procesadas.json"] == "no existia"
    assert resultados["estado_expedientes.json"] == "no existia"
