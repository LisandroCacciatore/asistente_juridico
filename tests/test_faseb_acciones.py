# -*- coding: utf-8 -*-
"""Épica 2 de la Fase B: el portal sólo puede pedir dos acciones.

El dashboard local conserva todas las acciones del asistente. Un pedido que se
identifica como del portal (`X-Origen-Pedido: portal`) queda limitado a la lista
cerrada: `firmar_lote` y `presentar`.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import faseb_acciones  # noqa: E402
import servidor  # noqa: E402

PORTAL = {"X-Origen-Pedido": "portal"}


@pytest.fixture
def cliente():
    servidor.JOBS.clear()
    return TestClient(servidor.app)


@pytest.mark.parametrize("accion", ["borrar_cedula", "ejecutar_comando", "cedula"])
def test_accion_fuera_de_la_lista(cliente, accion):
    r = cliente.post(f"/api/skill/{accion}", json={"datos": {}}, headers=PORTAL)
    assert r.status_code == 400
    assert "no permitida" in r.json()["error"].lower()
    assert servidor.JOBS == {}, "no debe lanzar ningún trabajo"


def test_accion_solo_espacios(cliente):
    """Una acción que llega vacía o con relleno tampoco pasa."""
    r = cliente.post("/api/skill/%20", json={"datos": {}}, headers=PORTAL)
    assert r.status_code == 400


def test_acciones_permitidas_pasan(cliente):
    for accion in ("firmar_lote", "presentar"):
        r = cliente.post(f"/api/skill/{accion}", json={"datos": {}}, headers=PORTAL)
        assert r.status_code != 400, f"{accion} debe pasar la lista cerrada"


def test_dashboard_conserva_todas_las_acciones(cliente):
    """Sin el header del portal, el dashboard sigue igual que antes."""
    r = cliente.post("/api/skill/cedula", json={"datos": {}})
    assert r.status_code == 200, "el dashboard no puede quedar limitado"


def test_traduccion_de_presentar():
    assert faseb_acciones.resolver("presentar") == "notificar_sisfe"
    assert faseb_acciones.resolver("firmar_lote") == "firmar_lote"


def test_no_distingue_mayusculas_ni_espacios():
    assert faseb_acciones.resolver("  PRESENTAR ") == "notificar_sisfe"


def test_accion_vacia_es_rechazada():
    with pytest.raises(faseb_acciones.AccionNoPermitida):
        faseb_acciones.resolver("")


def test_rechazo_queda_en_el_log(cliente, tmp_path, monkeypatch):
    import estado

    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log.jsonl"))
    cliente.post("/api/skill/borrar_cedula", json={"datos": {}}, headers=PORTAL)
    texto = (tmp_path / "log.jsonl").read_text(encoding="utf-8")
    assert "no permitida" in texto.lower()
