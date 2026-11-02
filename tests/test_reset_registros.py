# -*- coding: utf-8 -*-
"""El reset de registros vacía lo regenerable y conserva los pendientes.

`estado.json` tiene dos cosas distintas: las cédulas (se regeneran) y los
pendientes (decretos detectados que esperan clasificación humana). Vaciar los
pendientes perdería trabajo que el monitor ya hizo.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

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

    estado = _leer(tmp_path / "estado.json")
    assert estado["cedulas"] == []
    assert estado["pendientes"] == pendientes
    assert _leer(tmp_path / "cedulas_procesadas.json") == {}
    assert _leer(tmp_path / "estado_expedientes.json") == {}


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
