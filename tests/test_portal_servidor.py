# -*- coding: utf-8 -*-
"""El servidor HTTP del portal: login, estado, log, ficha y documentos.

Todo corre contra una base SQLite y una carpeta de subidas temporales:
ningún test toca `portal.db`, `portal_uploads/` ni `config.py` reales.
"""
import os

import pytest
from fastapi.testclient import TestClient

from portal import auth, db, servidor_portal

PDF = b"%PDF-1.4\n% cedula de prueba\n"
CLAVE = "clave-segura-123"


class Portal:
    def __init__(self, cliente, config, tmp_path):
        self.cliente = cliente
        self.config = config
        self.tmp_path = tmp_path
        self.uploads = os.path.join(str(tmp_path), "uploads")


@pytest.fixture
def portal(tmp_path, monkeypatch):
    config = {
        "PORTAL_DB": str(tmp_path / "portal.db"),
        "PORTAL_UPLOADS": str(tmp_path / "uploads"),
        "PORTAL_SECRETO": "secreto-de-prueba-123",
        "PORTAL_HASH": "argon2",
        "PORTAL_SESION_HORAS": 12,
        "PORTAL_COOKIE_SEGURA": False,
        "PORTAL_ORIGENES": [],
        "PORTAL_MAX_SUBIDA_MB": 5,
        "PORTAL_ADMINISTRADORES": [],
    }
    monkeypatch.setattr(
        db, "config_portal", lambda nombre, default=None: config.get(nombre, default)
    )
    monkeypatch.setattr(servidor_portal, "_ORIGENES", [])
    db.inicializar()
    db.crear_persona("santiago", "Santiago", mail="santiago@estudio.test")
    db.guardar_credencial("santiago", auth.hashear(CLAVE))
    db.crear_persona("jr", "Jr")
    db.guardar_credencial("jr", auth.hashear("clave-segura-456"))
    return Portal(TestClient(servidor_portal.app), config, tmp_path)


def _login(portal, identificador="santiago", password=CLAVE):
    return portal.cliente.post(
        "/login",
        data={"identificador": identificador, "password": password},
        follow_redirects=False,
    )


# --- Sesión -------------------------------------------------------
def test_sin_sesion_da_401(portal):
    assert portal.cliente.get("/api/estado").status_code == 401


def test_login_incorrecto_no_abre_sesion(portal):
    r = _login(portal, password="mala")
    assert r.status_code == 401
    assert portal.cliente.get("/api/sesion").status_code == 401


def test_login_y_sesion(portal):
    r = _login(portal)
    assert r.status_code == 303
    r = portal.cliente.get("/api/sesion")
    assert r.status_code == 200
    assert r.json()["persona"]["persona_id"] == "santiago"
    assert "hash" not in r.json()["persona"]


def test_logout_cierra_la_sesion(portal):
    _login(portal)
    r = portal.cliente.post("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert portal.cliente.get("/api/sesion").status_code == 401


def test_login_con_mail(portal):
    r = _login(portal, identificador="santiago@estudio.test")
    assert r.status_code == 303


def test_login_sin_secreto_avisa_en_la_puerta(portal):
    portal.config["PORTAL_SECRETO"] = db.SECRETO_PLACEHOLDER
    r = _login(portal)
    assert r.status_code == 500
    assert "no está configurado" in r.text
    assert db.contar_sesiones() == 0


def test_persona_desactivada_no_entra(portal):
    db.desactivar_persona("jr")
    r = _login(portal, identificador="jr", password="clave-segura-456")
    assert r.status_code == 401


# --- Estado -------------------------------------------------------
def test_estado_arranca_vacio(portal):
    _login(portal)
    r = portal.cliente.get("/api/estado")
    assert r.status_code == 200
    assert r.json()["datos"] == {"cedulas": [], "pendientes": []}
    assert r.json()["version"] == 0


def test_escribir_estado_sincroniza(portal):
    _login(portal)
    r = portal.cliente.put(
        "/api/estado",
        json={"datos": {"cedulas": [{"id": "c1", "caratula": "Perez"}], "pendientes": []}},
    )
    assert r.status_code == 200
    assert r.json()["datos"]["cedulas"][0]["id"] == "c1"
    assert portal.cliente.get("/api/estado").json()["version"] == 1


def test_estado_no_borra_cedulas_que_no_vienen(portal):
    _login(portal)
    portal.cliente.put("/api/estado", json={"datos": {"cedulas": [{"id": "c1"}]}})
    portal.cliente.put("/api/estado", json={"datos": {"cedulas": [{"id": "c2"}]}})
    ids = [c["id"] for c in portal.cliente.get("/api/estado").json()["datos"]["cedulas"]]
    assert ids == ["c1", "c2"]


def test_estado_no_puede_cambiar_una_cadena(portal):
    _login(portal)
    portal.cliente.put(
        "/api/estado", json={"datos": {"cedulas": [{"id": "c1", "identidad_cadena": "jr"}]}}
    )
    r = portal.cliente.put(
        "/api/estado", json={"datos": {"cedulas": [{"id": "c1", "identidad_cadena": "santiago"}]}}
    )
    assert r.status_code == 403
    assert "D25" in r.json()["error"]


def test_estado_conserva_la_cadena_si_no_la_manda(portal):
    _login(portal)
    portal.cliente.put(
        "/api/estado", json={"datos": {"cedulas": [{"id": "c1", "identidad_cadena": "jr"}]}}
    )
    portal.cliente.put(
        "/api/estado", json={"datos": {"cedulas": [{"id": "c1", "caratula": "Perez"}]}}
    )
    assert portal.cliente.get("/api/cedulas/c1").json()["cedula"]["identidad_cadena"] == "jr"


# --- Log ----------------------------------------------------------
def test_agregar_y_leer_log(portal):
    _login(portal)
    r = portal.cliente.post(
        "/api/log", json={"accion": "generada", "id_cedula": "c1", "detalle": "ok"}
    )
    assert r.status_code == 200
    assert r.json()["entrada"]["operador"] == "Santiago"
    assert r.json()["entrada"]["identidad"] == "santiago"
    entradas = portal.cliente.get("/api/log").json()["entradas"]
    assert entradas[0]["accion"] == "generada"


def test_log_rechaza_accion_vacia(portal):
    _login(portal)
    r = portal.cliente.post("/api/log", json={"accion": ""})
    assert r.status_code == 400


# --- Ficha --------------------------------------------------------
def test_ficha_ida_y_vuelta(portal):
    _login(portal)
    r = portal.cliente.put("/api/ficha/CUIJ-1", json={"datos": {"caratula": "Perez"}})
    assert r.status_code == 200
    r = portal.cliente.get("/api/ficha/CUIJ-1")
    assert r.status_code == 200
    assert r.json()["ficha"]["caratula"] == "Perez"
    assert portal.cliente.get("/api/ficha/NO-EXISTE").status_code == 404


# --- Cédulas, cadena y anti-duplicado -----------------------------
def _guardar_cedula(portal, id_cedula="c1", **datos):
    return portal.cliente.put(
        f"/api/cedulas/{id_cedula}", json={"cedula": datos}
    )


def test_cedula_cadena_y_presentar(portal):
    _login(portal)
    r = _guardar_cedula(portal, "c1", caratula="Perez", cuij="CUIJ-1")
    assert r.status_code == 200
    r = portal.cliente.post("/api/cedulas/c1/cadena")
    assert r.status_code == 200
    assert r.json()["identidad"] == "santiago"
    assert portal.cliente.get("/api/cedulas/c1").json()["cedula"]["identidad_cadena"] == "santiago"

    r = portal.cliente.post("/api/cedulas/c1/presentar")
    assert r.status_code == 200
    assert r.json()["cedula"]["estado"] == "presentada"
    assert r.json()["cedula"]["identidad_cadena"] == "santiago"

    r = portal.cliente.post("/api/cedulas/c1/presentar")
    assert r.status_code == 409
    assert "presentada" in r.json()["error"]
    assert portal.cliente.get("/api/cedulas/c1").json()["cedula"]["estado"] == "presentada"


def test_guardar_cedula_conserva_la_cadena(portal):
    _login(portal)
    _guardar_cedula(portal, "c1", identidad_cadena="jr")
    _guardar_cedula(portal, "c1", caratula="Perez")
    assert portal.cliente.get("/api/cedulas/c1").json()["cedula"]["identidad_cadena"] == "jr"


def test_cadena_de_otra_persona_frena(portal):
    _login(portal)
    _guardar_cedula(portal, "c1", identidad_cadena="jr")
    r = portal.cliente.post("/api/cedulas/c1/presentar")
    assert r.status_code == 403
    assert "D25" in r.json()["error"]
    r = portal.cliente.post("/api/cedulas/c1/cadena")
    assert r.status_code == 403
    assert portal.cliente.get("/api/cedulas/c1").json()["cedula"]["identidad_cadena"] == "jr"


def test_cedula_inexistente_da_404(portal):
    _login(portal)
    assert portal.cliente.get("/api/cedulas/no-existe").status_code == 404
    assert portal.cliente.post("/api/cedulas/no-existe/presentar").status_code == 404


def test_filtrar_cedulas_por_estado(portal):
    _login(portal)
    _guardar_cedula(portal, "c1", estado="generada")
    _guardar_cedula(portal, "c2", estado="presentada")
    r = portal.cliente.get("/api/cedulas?estado=generada")
    assert [c["id"] for c in r.json()["cedulas"]] == ["c1"]


# --- Documentos ---------------------------------------------------
def test_subir_y_descargar_pdf(portal):
    _login(portal)
    r = portal.cliente.post(
        "/api/documentos",
        files={"archivo": ("cedula.pdf", PDF, "application/pdf")},
        data={"cuij": "CUIJ-1"},
    )
    assert r.status_code == 200
    documento = r.json()["documento"]
    assert documento["nombre"] == "cedula.pdf"
    assert documento["sha256"]
    assert os.path.abspath(documento["ruta"]).startswith(os.path.abspath(portal.uploads))

    r = portal.cliente.get(f"/api/documentos/{documento['id']}")
    assert r.status_code == 200
    assert r.content == PDF
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.headers["content-disposition"].lower().startswith("inline")

    r = portal.cliente.get("/api/documentos?cuij=CUIJ-1")
    assert [d["id"] for d in r.json()["documentos"]] == [documento["id"]]


def test_nombre_peligroso_no_sale_de_uploads(portal):
    _login(portal)
    r = portal.cliente.post(
        "/api/documentos",
        files={"archivo": ("../../cedula.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 200
    documento = r.json()["documento"]
    assert documento["nombre"] == "cedula.pdf"
    ruta = os.path.abspath(documento["ruta"])
    assert os.path.commonpath([ruta, os.path.abspath(portal.uploads)]) == os.path.abspath(portal.uploads)


def test_cuij_peligroso_no_sale_de_uploads(portal):
    _login(portal)
    r = portal.cliente.post(
        "/api/documentos",
        files={"archivo": ("cedula.pdf", PDF, "application/pdf")},
        data={"cuij": "../../fuera/CUIJ-1"},
    )
    assert r.status_code == 200
    documento = r.json()["documento"]
    ruta = os.path.abspath(documento["ruta"])
    assert os.path.commonpath([ruta, os.path.abspath(portal.uploads)]) == os.path.abspath(portal.uploads)
    assert os.path.basename(os.path.dirname(ruta)) == "fueraCUIJ-1"


def test_cuij_se_sanea_a_letras_numeros_y_guiones(portal):
    _login(portal)
    r = portal.cliente.post(
        "/api/documentos",
        files={"archivo": ("cedula.pdf", PDF, "application/pdf")},
        data={"cuij": "21-00000001-0 / .."},
    )
    assert r.status_code == 200
    documento = r.json()["documento"]
    ruta = os.path.abspath(documento["ruta"])
    assert os.path.basename(os.path.dirname(ruta)) == "21-00000001-0"


def test_archivo_sin_cabecera_pdf_da_400(portal):
    _login(portal)
    r = portal.cliente.post(
        "/api/documentos",
        files={"archivo": ("falso.pdf", b"esto no es un PDF", "application/pdf")},
    )
    assert r.status_code == 400
    assert "%PDF-" in r.json()["detail"]


def test_cabeceras_de_seguridad(portal):
    r = portal.cliente.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_dentro_de_uploads_rechaza_afuera(portal):
    assert servidor_portal._dentro_de_uploads(
        os.path.join(portal.uploads, "cedula.pdf")
    ) is True
    assert servidor_portal._dentro_de_uploads(
        os.path.join(str(portal.tmp_path), "fuera.pdf")
    ) is False


def test_solo_pdf(portal):
    _login(portal)
    r = portal.cliente.post(
        "/api/documentos",
        files={"archivo": ("notas.txt", b"hola", "text/plain")},
    )
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def test_tope_de_subida(portal):
    portal.config["PORTAL_MAX_SUBIDA_MB"] = 1
    _login(portal)
    grande = b"%PDF-1.4\n" + b"x" * (1024 * 1024 + 10)
    r = portal.cliente.post(
        "/api/documentos",
        files={"archivo": ("grande.pdf", grande, "application/pdf")},
    )
    assert r.status_code == 413


def test_documento_inexistente_da_404(portal):
    _login(portal)
    assert portal.cliente.get("/api/documentos/no-existe").status_code == 404


# --- CSRF y panel -------------------------------------------------
def test_csrf_bloquea_origen_externo(portal):
    _login(portal)
    r = portal.cliente.post(
        "/api/log", json={"accion": "x"}, headers={"Origin": "https://evil.example"}
    )
    assert r.status_code == 403
    r = portal.cliente.post(
        "/api/log", json={"accion": "x"}, headers={"Origin": "http://testserver"}
    )
    assert r.status_code == 200


def test_panel_pide_login(portal):
    r = portal.cliente.get("/panel", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_panel_muestra_la_persona(portal):
    _login(portal)
    r = portal.cliente.get("/panel")
    assert r.status_code == 200
    assert "Trabajando" in r.text
    assert "Santiago" in r.text


def test_panel_muestra_la_ficha(portal):
    _login(portal)
    portal.cliente.put("/api/ficha/CUIJ-1", json={"datos": {"caratula": "Perez"}})
    r = portal.cliente.get("/panel?cuij=CUIJ-1")
    assert r.status_code == 200
    assert "Perez" in r.text


def test_personas_publicas_sin_hash(portal):
    _login(portal)
    r = portal.cliente.get("/api/personas")
    assert r.status_code == 200
    ids = [p["persona_id"] for p in r.json()["personas"]]
    assert "santiago" in ids
    assert all("hash" not in p for p in r.json()["personas"])


def test_salud(portal):
    r = portal.cliente.get("/api/salud")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# --- Administración por HTTP --------------------------------------
def test_admin_por_defecto_da_403(portal):
    _login(portal)
    assert portal.cliente.get("/api/admin/personas").status_code == 403


def test_admin_puede_crear_y_manejar_personas(portal):
    portal.config["PORTAL_ADMINISTRADORES"] = ["santiago"]
    _login(portal)

    r = portal.cliente.get("/api/admin/personas")
    assert r.status_code == 200
    assert any(p["persona_id"] == "jr" for p in r.json()["personas"])

    r = portal.cliente.post(
        "/api/admin/personas",
        json={"persona_id": "nuevo", "nombre": "Nuevo", "password": "clave-nueva-123"},
    )
    assert r.status_code == 200
    assert db.obtener_credencial("nuevo") is not None

    r = portal.cliente.put(
        "/api/admin/personas/nuevo", json={"nombre": "Nuevo Nombre"}
    )
    assert r.status_code == 200
    assert r.json()["persona"]["nombre"] == "Nuevo Nombre"

    r = portal.cliente.post(
        "/api/admin/personas/nuevo/password", json={"password": "otra-clave-123"}
    )
    assert r.status_code == 200

    r = portal.cliente.post("/api/admin/personas/nuevo/desactivar")
    assert r.status_code == 200
    assert r.json()["persona"]["activo"] is False

    r = portal.cliente.post("/api/admin/sesiones-borrar")
    assert r.status_code == 200
    assert r.json()["borradas"] >= 1


def test_admin_password_corta_da_400(portal):
    portal.config["PORTAL_ADMINISTRADORES"] = ["santiago"]
    _login(portal)
    r = portal.cliente.post(
        "/api/admin/personas/santiago/password", json={"password": "corta"}
    )
    assert r.status_code == 400


def test_admin_persona_duplicada_da_400(portal):
    portal.config["PORTAL_ADMINISTRADORES"] = ["santiago"]
    _login(portal)
    r = portal.cliente.post(
        "/api/admin/personas", json={"persona_id": "jr", "nombre": "Otro Jr"}
    )
    assert r.status_code == 400
