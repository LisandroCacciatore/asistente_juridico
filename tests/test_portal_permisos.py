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
    # Devuelve el NOMBRE canónico (lo que se guarda en identidad_cadena).
    assert permisos.verificar_cadena(cedula, PERSONA) == "Santiago"


def test_cadena_igual_pasa():
    cedula = {"id": "c1", "identidad_cadena": "santiago"}
    assert permisos.verificar_cadena(cedula, PERSONA) == "santiago"


def test_cadena_distinta_frena():
    cedula = {"id": "c1", "identidad_cadena": "jr"}
    with pytest.raises(permisos.ErrorPermiso, match="D25"):
        permisos.verificar_cadena(cedula, PERSONA)


def test_fijar_cadena_solo_la_primera_vez():
    cedula = {"id": "c1"}
    assert permisos.fijar_cadena(cedula, PERSONA) == "Santiago"
    assert cedula["identidad_cadena"] == "Santiago"
    # Otra persona ya no puede cambiarla.
    with pytest.raises(permisos.ErrorPermiso, match="D25"):
        permisos.fijar_cadena(cedula, OTRA)
    assert cedula["identidad_cadena"] == "Santiago"


def test_cadena_sin_persona_frena():
    with pytest.raises(permisos.ErrorPermiso, match="autenticada"):
        permisos.verificar_cadena({"id": "c1"}, None)


# --- Identidad canónica (commit 3) --------------------------------
def _personas_de_ejemplo():
    """PERSONAS tal como está en config.example.py (la fuente de verdad)."""
    import importlib.util
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "config_de_ejemplo", raiz / "config.example.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.PERSONAS


def test_normalizar_ignora_mayusculas_y_espacios():
    assert permisos.normalizar("  Santiago ") == "santiago"
    assert permisos.normalizar("SANTIAGO") == "santiago"
    assert permisos.normalizar(None) == ""


def test_identidad_de_devuelve_el_nombre_real(monkeypatch):
    personas = _personas_de_ejemplo()
    assert {"Santiago", "Jr", "Socio"} <= set(personas)
    monkeypatch.setattr(permisos, "personas_config", lambda: personas)
    for nombre, datos in personas.items():
        # Aunque el nombre de la base esté desactualizado, manda PERSONAS.
        persona = {"persona_id": datos["persona_id"], "nombre": "Nombre viejo"}
        assert permisos.identidad_de(persona) == nombre


def test_identidad_de_no_devuelve_el_persona_id():
    assert permisos.identidad_de(PERSONA) == "Santiago"
    assert permisos.identidad_de({"persona_id": "x", "nombre": "Otra"}) == "Otra"
    assert permisos.identidad_de(None) == ""
