# -*- coding: utf-8 -*-
"""Épica 1 de la Fase B: sólo el portal puede dar órdenes al asistente.

Hoy `servidor.py` escucha en 127.0.0.1:8000 sin validar quién llama. Un sitio
abierto en el mismo navegador ya no puede POSTear cross-site (lo frena
`_proteger_csrf` con 403), pero un proceso local cualquiera sí.

Estos tests definen el contrato del token compartido:
  - sin token válido no se ejecuta NADA
  - el rechazo queda anotado
  - el token nunca aparece en la respuesta
  - el pedido cross-site sigue rechazado (regresión de lo que ya existía)
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import servidor  # noqa: E402

TOKEN = "token-de-prueba-1234567890"


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(servidor, "TOKEN_ASISTENTE", TOKEN, raising=False)
    servidor.JOBS.clear()
    return TestClient(servidor.app)


def test_sin_token_no_ejecuta_nada(cliente):
    r = cliente.post("/api/firmar", json={"id_cedula": "x", "identidad": "jr"})
    assert r.status_code == 401
    assert servidor.JOBS == {}, "no debe crear ningún trabajo"


def test_token_incorrecto_rechazado(cliente):
    r = cliente.post(
        "/api/firmar",
        json={"id_cedula": "x", "identidad": "jr"},
        headers={"X-Asistente-Token": "otro-token"},
    )
    assert r.status_code == 401
    assert servidor.JOBS == {}


def test_token_valido_pasa_la_autenticacion(cliente):
    r = cliente.post(
        "/api/firmar",
        json={"id_cedula": "no-existe", "identidad": "jr"},
        headers={"X-Asistente-Token": TOKEN},
    )
    assert r.status_code != 401, "con token válido no debe rechazar por credencial"


def test_token_no_aparece_en_la_respuesta(cliente):
    r = cliente.post("/api/firmar", json={"id_cedula": "x"})
    assert TOKEN not in r.text


def test_origen_ajeno_sigue_rechazado(cliente):
    """Regresión: el anti-CSRF que ya existía no se puede romper."""
    r = cliente.post(
        "/api/firmar",
        json={"id_cedula": "x"},
        headers={
            "X-Asistente-Token": TOKEN,
            "Origin": "https://sitio-cualquiera.example",
            "Host": "127.0.0.1:8000",
        },
    )
    assert r.status_code == 403


def test_rechazo_queda_registrado(cliente, tmp_path, monkeypatch):
    """El escenario pide que el rechazo se anote."""
    import estado

    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log.jsonl"))
    cliente.post("/api/firmar", json={"id_cedula": "x"})
    texto = (tmp_path / "log.jsonl").read_text(encoding="utf-8")
    assert "token" in texto.lower() or "credencial" in texto.lower()


def test_dashboard_inyecta_el_token(cliente):
    """El dashboard recibe el token en el HTML y lo manda en cada fetch."""
    r = cliente.get("/")
    assert r.status_code == 200
    assert TOKEN in r.text, "el token debe quedar inyectado en la página"
    assert "__TOKEN_ASISTENTE__" not in r.text, "no debe quedar el marcador"


def test_dashboard_sin_token_no_deja_marcador(monkeypatch):
    monkeypatch.setattr(servidor, "TOKEN_ASISTENTE", "", raising=False)
    r = TestClient(servidor.app).get("/")
    assert "__TOKEN_ASISTENTE__" not in r.text


def test_dns_rebinding_host_ajeno(monkeypatch):
    """Un dominio que resuelve a 127.0.0.1 manda Host y Origin iguales."""
    monkeypatch.setattr(servidor, "TOKEN_ASISTENTE", TOKEN, raising=False)
    c = TestClient(servidor.app, base_url="http://evil.example")
    r = c.get("/")
    assert r.status_code == 403, "no debe servir el HTML a un host ajeno"
    assert "asistente-token" not in r.text


def test_dns_rebinding_post_con_origin_igual(monkeypatch):
    monkeypatch.setattr(servidor, "TOKEN_ASISTENTE", TOKEN, raising=False)
    c = TestClient(servidor.app, base_url="http://evil.example")
    r = c.post(
        "/api/firmar",
        json={"id_cedula": "x"},
        headers={"X-Asistente-Token": TOKEN, "Origin": "http://evil.example"},
    )
    assert r.status_code == 403


def test_token_en_todos_los_post(cliente):
    """Un POST nuevo no puede quedar abierto por olvido."""
    for ruta in ("/api/destinatarios", "/api/sesion", "/api/generar_desde_pendiente"):
        r = cliente.post(ruta, json={})
        assert r.status_code == 401, f"{ruta} debe exigir token"


def test_host_local_sigue_pasando(monkeypatch):
    monkeypatch.setattr(servidor, "TOKEN_ASISTENTE", TOKEN, raising=False)
    c = TestClient(servidor.app, base_url="http://localhost:8000")
    assert c.get("/").status_code == 200
