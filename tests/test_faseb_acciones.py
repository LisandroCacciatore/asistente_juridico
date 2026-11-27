# -*- coding: utf-8 -*-
"""Épica 2 de la Fase B: el portal sólo puede pedir dos acciones.

Hay dos credenciales:
  - TOKEN_ASISTENTE: el dashboard local, con todas las acciones.
  - TOKEN_PORTAL: el portal, sólo `firmar_lote` y `presentar`.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import faseb_acciones  # noqa: E402
import servidor  # noqa: E402

TOKEN_PORTAL = "portal-de-prueba-123"
TOKEN_ASISTENTE = "asistente-de-prueba-456"


@pytest.fixture
def portal(monkeypatch):
    monkeypatch.setattr(servidor, "TOKEN_PORTAL", TOKEN_PORTAL, raising=False)
    monkeypatch.setattr(servidor, "TOKEN_ASISTENTE", TOKEN_ASISTENTE, raising=False)
    return TestClient(servidor.app, headers={"X-Asistente-Token": TOKEN_PORTAL})


@pytest.fixture
def dashboard(monkeypatch):
    monkeypatch.setattr(servidor, "TOKEN_PORTAL", TOKEN_PORTAL, raising=False)
    monkeypatch.setattr(servidor, "TOKEN_ASISTENTE", TOKEN_ASISTENTE, raising=False)
    return TestClient(servidor.app, headers={"X-Asistente-Token": TOKEN_ASISTENTE})


@pytest.mark.parametrize("accion", ["borrar_cedula", "ejecutar_comando", "cedula"])
def test_portal_no_puede_pedir_otras_acciones(portal, accion):
    r = portal.post(f"/api/skill/{accion}", json={"datos": {}})
    assert r.status_code == 400
    assert "no permitida" in r.json()["error"]


def test_portal_puede_pedir_presentar(portal):
    r = portal.post("/api/skill/presentar", json={"datos": {}})
    assert r.status_code != 400


def test_portal_puede_pedir_firmar_lote(portal):
    r = portal.post("/api/skill/firmar_lote", json={"datos": {}})
    assert r.status_code != 400


def test_dashboard_conserva_todas_las_acciones(dashboard):
    # `cedula` no está en ACCIONES_PORTAL: el dashboard la sigue teniendo.
    r = dashboard.post("/api/skill/cedula", json={"datos": {}})
    assert r.status_code != 400


def test_token_ausente_rechazado(monkeypatch):
    monkeypatch.setattr(servidor, "TOKEN_PORTAL", TOKEN_PORTAL, raising=False)
    monkeypatch.setattr(servidor, "TOKEN_ASISTENTE", TOKEN_ASISTENTE, raising=False)
    c = TestClient(servidor.app)
    assert c.post("/api/skill/presentar", json={"datos": {}}).status_code == 401


def test_lista_cerrada_del_portal():
    assert faseb_acciones.ACCIONES_PORTAL == frozenset({"firmar_lote", "presentar"})


def test_presentar_se_traduce_a_notificar_sisfe():
    assert faseb_acciones.resolver("presentar") == "notificar_sisfe"


def test_accion_vacia_es_rechazada():
    with pytest.raises(faseb_acciones.AccionNoPermitida):
        faseb_acciones.resolver("   ")
