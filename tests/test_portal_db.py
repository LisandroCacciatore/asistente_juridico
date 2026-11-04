# -*- coding: utf-8 -*-
"""Base SQLite del portal: personas, credenciales, sesiones, estado, log, ficha."""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from portal import db  # noqa: E402


@pytest.fixture
def ruta(tmp_path):
    r = str(tmp_path / "portal.db")
    db.inicializar(r)
    return r


def test_inicializar_crea_tablas_y_es_idempotente(ruta):
    db.inicializar(ruta)
    with db.conexion(ruta) as con:
        tablas = {f["name"] for f in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
    assert {
        "personas", "credenciales", "sesiones", "estado",
        "log_acciones", "fichas", "documentos", "presentaciones",
        "auditoria",
    } <= tablas


def test_crear_obtener_y_listar_personas(ruta):
    db.crear_persona("santiago", "Santiago", mail="S@Estudio.Test", matricula="LV029", ruta=ruta)
    persona = db.obtener_persona("santiago", ruta=ruta)
    assert persona["nombre"] == "Santiago"
    assert persona["mail"] == "s@estudio.test"
    assert persona["activo"] == 1
    assert [p["persona_id"] for p in db.listar_personas(ruta=ruta)] == ["santiago"]


def test_persona_duplicada(ruta):
    db.crear_persona("santiago", "Santiago", ruta=ruta)
    with pytest.raises(db.PersonaExistente):
        db.crear_persona("santiago", "Otro", ruta=ruta)


def test_mail_unico_si_no_esta_vacio(ruta):
    db.crear_persona("santiago", "Santiago", mail="a@b.test", ruta=ruta)
    with pytest.raises(db.PersonaExistente):
        db.crear_persona("jr", "Jr", mail="A@B.TEST", ruta=ruta)
    db.crear_persona("socio", "Socio", mail="", ruta=ruta)
    db.crear_persona("otro", "Otro", mail="", ruta=ruta)


def test_persona_id_invalido(ruta):
    with pytest.raises(ValueError, match="slug"):
        db.crear_persona("Santiago", "Santiago", ruta=ruta)


def test_obtener_por_identificador_id_y_mail(ruta):
    db.crear_persona("santiago", "Santiago", mail="s@x.test", ruta=ruta)
    assert db.obtener_persona_por_identificador("santiago", ruta=ruta)["persona_id"] == "santiago"
    assert db.obtener_persona_por_identificador("S@X.TEST", ruta=ruta)["persona_id"] == "santiago"
    assert db.obtener_persona_por_identificador("nadie", ruta=ruta) is None


def test_actualizar_desactivar_y_borrar_sesiones(ruta):
    db.crear_persona("jr", "Jr", ruta=ruta)
    db.crear_sesion("th", "jr", "2099-01-01T00:00:00+00:00", ruta=ruta)
    db.actualizar_persona("jr", nombre="Junior", mail="jr@x.test", matricula="M1", ruta=ruta)
    assert db.obtener_persona("jr", ruta=ruta)["nombre"] == "Junior"
    db.desactivar_persona("jr", ruta=ruta)
    assert db.obtener_persona("jr", ruta=ruta)["activo"] == 0
    assert db.contar_sesiones("jr", ruta=ruta) == 0
    db.activar_persona("jr", ruta=ruta)
    assert db.obtener_persona("jr", ruta=ruta)["activo"] == 1


def test_credencial_upsert(ruta):
    db.crear_persona("santiago", "Santiago", ruta=ruta)
    db.guardar_credencial("santiago", "hash-1", ruta=ruta)
    assert db.obtener_credencial("santiago", ruta=ruta)["hash"] == "hash-1"
    db.guardar_credencial("santiago", "hash-2", ruta=ruta)
    assert db.obtener_credencial("santiago", ruta=ruta)["hash"] == "hash-2"


def test_credencial_persona_inexistente(ruta):
    with pytest.raises(db.PersonaNoEncontrada):
        db.guardar_credencial("nadie", "hash", ruta=ruta)


def test_sesiones_crud_y_limpieza(ruta):
    db.crear_persona("santiago", "Santiago", ruta=ruta)
    db.crear_sesion(
        "th1", "santiago", "2099-01-01T00:00:00+00:00",
        usuario_windows="win", maquina="PC", ruta=ruta,
    )
    assert db.obtener_sesion("th1", ruta=ruta)["maquina"] == "PC"
    assert db.renovar_sesion("th1", "2099-02-01T00:00:00+00:00", ruta=ruta) is True
    assert db.obtener_sesion("th1", ruta=ruta)["expira"].startswith("2099-02")
    db.crear_sesion("th2", "santiago", "2000-01-01T00:00:00+00:00", ruta=ruta)
    assert db.limpiar_sesiones_expiradas("2026-01-01T00:00:00+00:00", ruta=ruta) == 1
    assert db.eliminar_sesion("th1", ruta=ruta) is True
    assert db.eliminar_sesion("th1", ruta=ruta) is False


def test_estado_default_escribir_version_y_mutar(ruta):
    assert db.leer_estado(ruta=ruta) == {"cedulas": [], "pendientes": []}
    assert db.version_estado(ruta=ruta) == 0
    db.escribir_estado(
        {"cedulas": [{"id": "c1"}], "pendientes": []},
        persona_id="santiago", ruta=ruta,
    )
    assert db.leer_estado(ruta=ruta)["cedulas"][0]["id"] == "c1"
    assert db.version_estado(ruta=ruta) == 1

    def mod(data):
        data["cedulas"].append({"id": "c2"})

    db.mutar_estado(mod, persona_id="jr", ruta=ruta)
    assert [c["id"] for c in db.leer_estado(ruta=ruta)["cedulas"]] == ["c1", "c2"]
    assert db.version_estado(ruta=ruta) == 2


def test_mutar_estado_si_falla_no_pisa(ruta):
    db.escribir_estado({"cedulas": [{"id": "c1"}], "pendientes": []}, ruta=ruta)

    def falla(data):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        db.mutar_estado(falla, ruta=ruta)
    assert [c["id"] for c in db.leer_estado(ruta=ruta)["cedulas"]] == ["c1"]
    assert db.version_estado(ruta=ruta) == 1


def test_estado_invalido(ruta):
    with pytest.raises(db.ErrorPortal):
        db.escribir_estado({"cedulas": "no-es-lista"}, ruta=ruta)


def test_log_append_y_orden(ruta):
    db.agregar_log("generada", "c1", caratula="X", ruta=ruta)
    db.agregar_log("presentada", "c1", caratula="X", persona_id="santiago", ruta=ruta)
    log = db.leer_log(ruta=ruta)
    assert [e["accion"] for e in log] == ["presentada", "generada"]
    assert db.leer_log(limite=1, ruta=ruta)[0]["accion"] == "presentada"


def test_auditoria_guarda_y_recorta_el_detalle(ruta):
    db.registrar_auditoria(
        persona_id="santiago", accion="login", ip="127.0.0.1", detalle="x" * 200, ruta=ruta
    )
    with db.conexion(ruta) as con:
        fila = dict(con.execute("SELECT * FROM auditoria").fetchone())
    assert fila["persona_id"] == "santiago"
    assert fila["accion"] == "login"
    assert fila["ip"] == "127.0.0.1"
    assert fila["detalle"] == "x" * 80
    assert fila["fecha"]
    # La auditoría no va al log de cédulas.
    assert db.leer_log(ruta=ruta) == []


def test_ficha_merge_y_listado(ruta):
    db.guardar_ficha("CUIJ-1", {"caratula": "Perez", "notas": "hola"}, persona_id="santiago", ruta=ruta)
    db.guardar_ficha("CUIJ-1", {"notas": "chau"}, persona_id="jr", ruta=ruta)
    ficha = db.leer_ficha("CUIJ-1", ruta=ruta)
    assert ficha["caratula"] == "Perez"
    assert ficha["notas"] == "chau"
    assert ficha["actualizado_por"] == "jr"
    assert [f["cuij"] for f in db.listar_fichas(ruta=ruta)] == ["CUIJ-1"]
    assert db.leer_ficha("NO", ruta=ruta) is None


def test_documentos_crud(ruta):
    doc = db.registrar_documento(
        "cedula.pdf", "C:/tmp/cedula.pdf", "abc123", tamano=10,
        cuij="CUIJ-1", subido_por="santiago", ruta=ruta,
    )
    assert db.obtener_documento(doc["id"], ruta=ruta)["sha256"] == "abc123"
    assert [d["id"] for d in db.listar_documentos(cuij="CUIJ-1", ruta=ruta)] == [doc["id"]]
    assert db.eliminar_documento(doc["id"], ruta=ruta) is True
    assert db.obtener_documento(doc["id"], ruta=ruta) is None


def test_presentaciones_anti_duplicado(ruta):
    db.marcar_presentada("c1", persona_id="santiago", ruta=ruta)
    assert db.ya_presentada("c1", ruta=ruta) is True
    with pytest.raises(db.YaPresentada):
        db.marcar_presentada("c1", persona_id="jr", ruta=ruta)
    assert db.ya_presentada("c2", ruta=ruta) is False
    assert len(db.listar_presentaciones(ruta=ruta)) == 1
