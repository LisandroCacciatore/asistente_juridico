# -*- coding: utf-8 -*-
"""Permisos del portal: persona activa y regla de la cadena (D25).

No toca la base ni el servidor: son funciones puras sobre el diccionario
de la persona y el de la cédula.
"""
import pytest

from portal import db, permisos

PERSONA = {"persona_id": "santiago", "nombre": "Santiago", "activo": 1}
OTRA = {"persona_id": "jr", "nombre": "Jr", "activo": 1}


def test_identidad_y_activa():
    assert permisos.identidad(PERSONA) == "santiago"
    assert permisos.identidad({}) == ""
    assert permisos.esta_activa(PERSONA) is True
    assert permisos.esta_activa({**PERSONA, "activo": 0}) is False
    assert permisos.esta_activa(None) is False


def test_exigir_activo():
    permisos.exigir_activo(PERSONA)
    with pytest.raises(permisos.ErrorPermiso, match="autenticada"):
        permisos.exigir_activo(None)
    with pytest.raises(permisos.ErrorPermiso, match="desactivada"):
        permisos.exigir_activo({**PERSONA, "activo": 0})


def test_todos_pueden_operar():
    for accion in permisos.ACCIONES_DE_TODOS:
        assert permisos.puede(PERSONA, accion) is True


def test_desactivada_no_puede():
    assert permisos.puede({**PERSONA, "activo": 0}, permisos.LEER_ESTADO) is False


def test_accion_desconocida():
    with pytest.raises(ValueError, match="desconocida"):
        permisos.puede(PERSONA, "borrar_todo")
    with pytest.raises(ValueError, match="desconocida"):
        permisos.exigir(PERSONA, "borrar_todo")


def test_administrar_por_defecto_no(monkeypatch):
    monkeypatch.setattr(db, "config_portal", lambda nombre, default=None: default)
    assert permisos.es_administrador(PERSONA) is False
    assert permisos.puede(PERSONA, permisos.ADMINISTRAR) is False
    with pytest.raises(permisos.ErrorPermiso, match="administrar"):
        permisos.exigir(PERSONA, permisos.ADMINISTRAR)


def test_administrar_con_lista(monkeypatch):
    monkeypatch.setattr(
        db, "config_portal",
        lambda nombre, default=None: ["santiago"] if nombre == "PORTAL_ADMINISTRADORES" else default,
    )
    assert permisos.es_administrador(PERSONA) is True
    assert permisos.es_administrador(OTRA) is False
    assert permisos.puede(PERSONA, permisos.ADMINISTRAR) is True
    permisos.exigir(PERSONA, permisos.ADMINISTRAR)


def test_administradores_acepta_texto(monkeypatch):
    monkeypatch.setattr(
        db, "config_portal",
        lambda nombre, default=None: "santiago, jr" if nombre == "PORTAL_ADMINISTRADORES" else default,
    )
    assert permisos.administradores() == {"santiago", "jr"}


def test_cadena_vacia_devuelve_la_persona():
    cedula = {"id": "c1"}
    assert permisos.cadena_de(cedula) == ""
    assert permisos.verificar_cadena(cedula, PERSONA) == "santiago"


def test_cadena_igual_pasa():
    cedula = {"id": "c1", "identidad_cadena": "santiago"}
    assert permisos.verificar_cadena(cedula, PERSONA) == "santiago"


def test_cadena_distinta_frena():
    cedula = {"id": "c1", "identidad_cadena": "jr"}
    with pytest.raises(permisos.ErrorPermiso, match="D25"):
        permisos.verificar_cadena(cedula, PERSONA)


def test_fijar_cadena_solo_la_primera_vez():
    cedula = {"id": "c1"}
    assert permisos.fijar_cadena(cedula, PERSONA) == "santiago"
    assert cedula["identidad_cadena"] == "santiago"
    # Otra persona ya no puede cambiarla.
    with pytest.raises(permisos.ErrorPermiso, match="D25"):
        permisos.fijar_cadena(cedula, OTRA)
    assert cedula["identidad_cadena"] == "santiago"


def test_cadena_sin_persona_frena():
    with pytest.raises(permisos.ErrorPermiso, match="autenticada"):
        permisos.verificar_cadena({"id": "c1"}, None)
