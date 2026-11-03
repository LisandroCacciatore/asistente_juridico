# -*- coding: utf-8 -*-
"""Login del portal: hash, autenticación, sesiones y cookie firmada."""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from portal import auth, db  # noqa: E402

CLAVE = "clave-segura-123"


@pytest.fixture
def portal(tmp_path, monkeypatch):
    valores = {
        "PORTAL_HASH": "argon2",
        "PORTAL_SECRETO": "secreto-de-prueba-123",
        "PORTAL_SESION_HORAS": 12,
        "PORTAL_COOKIE_SEGURA": False,
    }
    monkeypatch.setattr(
        db, "config_portal",
        lambda nombre, default=None: valores.get(nombre, default),
    )
    ruta = str(tmp_path / "portal.db")
    db.inicializar(ruta)
    db.crear_persona("santiago", "Santiago", mail="santiago@estudio.test", ruta=ruta)
    db.guardar_credencial("santiago", auth.hashear(CLAVE), ruta=ruta)
    return ruta


def test_hashear_y_verificar(portal):
    hash_guardado = auth.hashear(CLAVE)
    assert hash_guardado.startswith("$argon2")
    assert auth.verificar(CLAVE, hash_guardado) is True
    assert auth.verificar("otra", hash_guardado) is False


def test_verificar_hash_invalido(portal):
    assert auth.verificar(CLAVE, "no-es-un-hash") is False
    assert auth.verificar(CLAVE, "") is False


def test_hashear_vacio(portal):
    with pytest.raises(ValueError):
        auth.hashear("")


def test_algoritmo_desconocido(portal, monkeypatch):
    monkeypatch.setattr(
        db, "config_portal",
        lambda nombre, default=None: "md5" if nombre == "PORTAL_HASH" else default,
    )
    with pytest.raises(auth.ErrorConfiguracion):
        auth.hashear(CLAVE)


def test_cookie_firma_verifica_y_detecta_manipulacion(portal):
    token = "token-de-prueba"
    cookie = auth.firmar_cookie(token)
    assert auth.verificar_cookie(cookie) == token
    assert auth.verificar_cookie(cookie + "x") is None
    assert auth.verificar_cookie("sin-punto") is None
    assert auth.verificar_cookie("token.firma-falsa") is None


def test_secreto_placeholder_falla(portal, monkeypatch):
    monkeypatch.setattr(
        db, "config_portal",
        lambda nombre, default=None: auth.PLACEHOLDER_SECRETO
        if nombre == "PORTAL_SECRETO" else default,
    )
    with pytest.raises(auth.ErrorConfiguracion):
        auth.firmar_cookie("token")


def test_secreto_no_texto_falla(portal, monkeypatch):
    monkeypatch.setattr(
        db, "config_portal",
        lambda nombre, default=None: 123 if nombre == "PORTAL_SECRETO" else default,
    )
    with pytest.raises(auth.ErrorConfiguracion):
        auth.firmar_cookie("token")


def test_autenticar_por_id_y_mail(portal):
    assert auth.autenticar("santiago", CLAVE, ruta=portal)["persona_id"] == "santiago"
    assert auth.autenticar("SANTIAGO@ESTUDIO.TEST", CLAVE, ruta=portal)["persona_id"] == "santiago"
    assert auth.autenticar("santiago", "mala", ruta=portal) is None
    assert auth.autenticar("nadie", CLAVE, ruta=portal) is None


def test_autenticar_persona_inactiva(portal):
    db.desactivar_persona("santiago", ruta=portal)
    assert auth.autenticar("santiago", CLAVE, ruta=portal) is None


def test_iniciar_y_validar_sesion(portal):
    token, persona = auth.iniciar_sesion("santiago", CLAVE, ruta=portal)
    assert persona["persona_id"] == "santiago"
    assert auth.validar_sesion(token, ruta=portal)["persona_id"] == "santiago"
    assert auth.validar_sesion("token-invalido", ruta=portal) is None


def test_validar_sesion_renueva(portal):
    token = auth.crear_sesion("santiago", horas=1, ruta=portal)
    antes = db.obtener_sesion(auth.hash_token(token), ruta=portal)["expira"]
    assert auth.validar_sesion(token, ruta=portal)["persona_id"] == "santiago"
    despues = db.obtener_sesion(auth.hash_token(token), ruta=portal)["expira"]
    assert despues > antes


def test_validar_sesion_vencida(portal):
    token = "token-vencido"
    db.crear_sesion(
        auth.hash_token(token), "santiago",
        "2000-01-01T00:00:00+00:00", ruta=portal,
    )
    assert auth.validar_sesion(token, ruta=portal) is None
    assert db.obtener_sesion(auth.hash_token(token), ruta=portal) is None


def test_cerrar_sesion(portal):
    token = auth.crear_sesion("santiago", ruta=portal)
    assert auth.cerrar_sesion(token, ruta=portal) is True
    assert auth.validar_sesion(token, ruta=portal) is None


def test_persona_actual(portal):
    token = auth.crear_sesion("santiago", ruta=portal)
    cookie = auth.firmar_cookie(token)
    assert auth.persona_actual(cookie, ruta=portal)["persona_id"] == "santiago"
    assert auth.persona_actual("basura", ruta=portal) is None


def test_opciones_cookie(portal):
    opciones = auth.opciones_cookie()
    assert opciones["httponly"] is True
    assert opciones["samesite"] == "lax"
    assert opciones["secure"] is False
    assert opciones["max_age"] == 12 * 3600
