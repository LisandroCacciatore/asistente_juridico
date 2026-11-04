# -*- coding: utf-8 -*-
"""Consola de administración del portal."""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import portal_admin  # noqa: E402
from portal import auth, db  # noqa: E402


@pytest.fixture
def ruta(tmp_path, monkeypatch):
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
    r = str(tmp_path / "portal.db")
    db.inicializar(r)
    return r


def test_sembrar_desde_config(ruta):
    personas = {
        "Santiago": {
            "persona_id": "santiago", "mail": "s@x.test",
            "matricula": "LV029", "perfil": "chrome_profile_portales",
        },
        "Jr": {
            "persona_id": "jr", "mail": "", "matricula": "",
            "perfil": "chrome_profile_jr",
        },
    }
    ids = portal_admin.sembrar_desde_config(personas, ruta=ruta)
    assert ids == ["santiago", "jr"]
    persona = db.obtener_persona("santiago", ruta=ruta)
    assert persona["mail"] == "s@x.test"
    assert persona["matricula"] == "LV029"
    assert "perfil" not in persona


def test_sembrar_es_idempotente_y_actualiza(ruta):
    portal_admin.sembrar_desde_config(
        {"Santiago": {"persona_id": "santiago", "mail": "a@x.test"}}, ruta=ruta
    )
    portal_admin.sembrar_desde_config(
        {"Santiago": {"persona_id": "santiago", "mail": "b@x.test"}}, ruta=ruta
    )
    assert db.obtener_persona("santiago", ruta=ruta)["mail"] == "b@x.test"
    assert len(db.listar_personas(ruta=ruta)) == 1


def test_guardar_password_y_autenticar(ruta):
    db.crear_persona("santiago", "Santiago", ruta=ruta)
    portal_admin.guardar_password("santiago", "clave-segura-123", ruta=ruta)
    assert auth.autenticar("santiago", "clave-segura-123", ruta=ruta)["persona_id"] == "santiago"


def test_password_corta(ruta):
    db.crear_persona("santiago", "Santiago", ruta=ruta)
    with pytest.raises(ValueError, match="al menos"):
        portal_admin.guardar_password("santiago", "corta", ruta=ruta)


def test_password_persona_inexistente(ruta):
    with pytest.raises(db.PersonaNoEncontrada):
        portal_admin.guardar_password("nadie", "clave-segura-123", ruta=ruta)


def test_activar_desactivar(ruta):
    db.crear_persona("jr", "Jr", ruta=ruta)
    db.desactivar_persona("jr", ruta=ruta)
    assert db.obtener_persona("jr", ruta=ruta)["activo"] == 0
    db.activar_persona("jr", ruta=ruta)
    assert db.obtener_persona("jr", ruta=ruta)["activo"] == 1


def test_listar_sin_personas(ruta, capsys):
    assert portal_admin.listar(ruta=ruta) == []
    assert "No hay personas" in capsys.readouterr().out


def test_main_crear_y_listar(ruta, capsys):
    assert portal_admin.main(["--db", ruta, "crear", "santiago", "Santiago"]) == 0
    assert portal_admin.main(["--db", ruta, "listar"]) == 0
    salida = capsys.readouterr().out
    assert "santiago" in salida
    assert "Santiago" in salida


def test_main_puede_actuar_fija_y_limpia(ruta, capsys):
    portal_admin.main(["--db", ruta, "crear", "jr", "Jr"])
    assert portal_admin.main(
        ["--db", ruta, "puede-actuar", "jr", "Santiago", "Socio"]
    ) == 0
    assert db.puede_actuar_como("jr", ruta=ruta) == ["Santiago", "Socio"]
    assert "Santiago, Socio" in capsys.readouterr().out

    assert portal_admin.main(["--db", ruta, "puede-actuar", "jr", "--limpiar"]) == 0
    assert db.puede_actuar_como("jr", ruta=ruta) == []
    assert "(ninguna)" in capsys.readouterr().out

    # Listar muestra la columna.
    portal_admin.main(["--db", ruta, "puede-actuar", "jr", "Santiago"])
    portal_admin.main(["--db", ruta, "listar"])
    assert "actua como" in capsys.readouterr().out
