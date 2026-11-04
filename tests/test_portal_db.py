# -*- coding: utf-8 -*-
"""Base SQLite del portal: personas, credenciales, sesiones, documentos y auditoría."""
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
    assert {"personas", "credenciales", "sesiones", "auditoria"} <= tablas
    # Las tablas del portal viejo ya no se crean (commits 4b y 5).
    assert not (set(db.TABLAS_VIEJAS) & tablas)


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


def test_auditoria_limpia_controles_y_recorta_campos(ruta):
    db.registrar_auditoria(
        persona_id="a\nb" + "x" * 100,
        accion="login\t" * 20,
        ip="1.2.3.4\n" + "y" * 60,
        detalle="d\x01e" + "z" * 100,
        ruta=ruta,
    )
    with db.conexion(ruta) as con:
        fila = dict(con.execute("SELECT * FROM auditoria").fetchone())
    assert "\n" not in fila["persona_id"]
    assert "\t" not in fila["accion"]
    assert "\x01" not in fila["detalle"]
    assert len(fila["persona_id"]) == 80
    assert len(fila["accion"]) == 40
    assert len(fila["ip"]) == 45
    assert len(fila["detalle"]) == 80
    assert fila["persona_id"].startswith("ab")
    assert fila["detalle"].startswith("de")


def test_reducir_esquema_hace_backup_y_conserva_personas(tmp_path):
    ruta = str(tmp_path / "portal.db")
    db.inicializar(ruta)
    db.crear_persona("jr", "Jr", ruta=ruta)
    db.guardar_credencial("jr", "hash-de-prueba", ruta=ruta)
    # Una base del portal viejo tenía estas cuatro tablas.
    with db.conexion(ruta) as con:
        for tabla in db.TABLAS_VIEJAS:
            con.execute(f"CREATE TABLE {tabla} (id INTEGER PRIMARY KEY)")
        con.execute("INSERT INTO estado (id) VALUES (1)")
        con.commit()

    backup = db.reducir_esquema(ruta)

    assert backup and os.path.isfile(backup)
    with db.conexion(ruta) as con:
        tablas = {
            f["name"]
            for f in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        personas = con.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
        credenciales = con.execute("SELECT COUNT(*) FROM credenciales").fetchone()[0]
    assert not (set(db.TABLAS_VIEJAS) & tablas)
    assert personas == 1
    assert credenciales == 1

    # El backup conserva lo que se borró.
    with db.conexion(backup) as con:
        viejas = {
            f["name"]
            for f in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert set(db.TABLAS_VIEJAS) <= viejas

    # Idempotente: la segunda vez no hay nada que borrar ni backup nuevo.
    assert db.reducir_esquema(ruta) is None


def test_migracion_agrega_debe_cambiar(tmp_path):
    # Una base creada antes del commit 6 no tiene la columna: inicializar la
    # agrega con 0 y conserva la credencial.
    ruta = str(tmp_path / "vieja.db")
    with db.conexion(ruta) as con:
        con.execute(
            "CREATE TABLE personas (persona_id TEXT PRIMARY KEY, nombre TEXT NOT NULL, "
            "mail TEXT NOT NULL DEFAULT '', matricula TEXT NOT NULL DEFAULT '', "
            "activo INTEGER NOT NULL DEFAULT 1, "
            "puede_actuar_como TEXT NOT NULL DEFAULT '', "
            "creado TEXT NOT NULL, actualizado TEXT NOT NULL)"
        )
        con.execute(
            "CREATE TABLE credenciales (persona_id TEXT PRIMARY KEY, "
            "hash TEXT NOT NULL, actualizado TEXT NOT NULL)"
        )
        con.execute(
            "INSERT INTO personas (persona_id, nombre, creado, actualizado) "
            "VALUES ('jr', 'Jr', 'x', 'x')"
        )
        con.execute(
            "INSERT INTO credenciales VALUES ('jr', 'hash-x', 'x')"
        )
        con.commit()
    db.inicializar(ruta)
    with db.conexion(ruta) as con:
        columnas = {
            fila["name"] for fila in con.execute("PRAGMA table_info(credenciales)")
        }
        credencial = dict(con.execute("SELECT * FROM credenciales").fetchone())
    assert "debe_cambiar" in columnas
    assert credencial["debe_cambiar"] == 0
    assert credencial["hash"] == "hash-x"


def test_migracion_agrega_puede_actuar_como(tmp_path):
    # Una base creada antes del commit 3 no tiene la columna: inicializar la
    # agrega sin perder datos (CREATE TABLE IF NOT EXISTS no la tocaría).
    ruta = str(tmp_path / "vieja.db")
    with db.conexion(ruta) as con:
        con.execute(
            "CREATE TABLE personas ("
            "persona_id TEXT PRIMARY KEY, nombre TEXT NOT NULL, "
            "mail TEXT NOT NULL DEFAULT '', matricula TEXT NOT NULL DEFAULT '', "
            "activo INTEGER NOT NULL DEFAULT 1, "
            "creado TEXT NOT NULL, actualizado TEXT NOT NULL)"
        )
        con.execute(
            "INSERT INTO personas (persona_id, nombre, creado, actualizado) "
            "VALUES ('jr', 'Jr', 'x', 'x')"
        )
        con.commit()
    db.inicializar(ruta)
    with db.conexion(ruta) as con:
        columnas = {f["name"] for f in con.execute("PRAGMA table_info(personas)")}
        fila = dict(con.execute("SELECT * FROM personas").fetchone())
    assert "puede_actuar_como" in columnas
    assert fila["puede_actuar_como"] == ""
    assert fila["nombre"] == "Jr"


def test_fijar_puede_actuar_como_guarda_dedup_y_limpia(ruta):
    db.crear_persona("jr", "Jr", ruta=ruta)
    db.fijar_puede_actuar_como("jr", ["Santiago", "socio", "Santiago"], ruta=ruta)
    assert db.puede_actuar_como("jr", ruta=ruta) == ["Santiago", "socio"]
    db.fijar_puede_actuar_como("jr", [], ruta=ruta)
    assert db.puede_actuar_como("jr", ruta=ruta) == []
    with pytest.raises(db.PersonaNoEncontrada):
        db.fijar_puede_actuar_como("nadie", ["Jr"], ruta=ruta)


