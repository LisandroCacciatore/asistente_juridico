# -*- coding: utf-8 -*-
"""El servidor HTTP del portal: login, estado, log, ficha y documentos.

Todo corre contra una base SQLite y una carpeta de subidas temporales:
ningún test toca `portal.db`, `portal_uploads/` ni `config.py` reales.
"""
import json
import os

import pytest
from fastapi.testclient import TestClient

import estado
from portal import auth, db, hub, permisos, servidor_portal

PDF = b"%PDF-1.4\n% cedula de prueba\n"
CLAVE = "clave-segura-123"


class Portal:
    def __init__(self, cliente, config, tmp_path, ruta_estado, ruta_log):
        self.cliente = cliente
        self.config = config
        self.tmp_path = tmp_path
        self.uploads = os.path.join(str(tmp_path), "uploads")
        self.ruta_estado = ruta_estado
        self.ruta_log = ruta_log


def _sembrar_estado(portal, cedulas=(), pendientes=()):
    """Escribe el estado.json de tmp (la fuente de verdad del portal)."""
    with open(portal.ruta_estado, "w", encoding="utf-8") as archivo:
        json.dump(
            {"cedulas": list(cedulas), "pendientes": list(pendientes)},
            archivo, ensure_ascii=False,
        )


def _sembrar_log(portal, entradas):
    """Agrega líneas al log_acciones.jsonl de tmp."""
    with open(portal.ruta_log, "a", encoding="utf-8") as archivo:
        for entrada in entradas:
            archivo.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def _auditoria():
    with db.conexion() as con:
        return [dict(f) for f in con.execute(
            "SELECT * FROM auditoria ORDER BY id"
        ).fetchall()]


def _auditoria_con(accion):
    return [f for f in _auditoria() if f["accion"] == accion]


def _pedido(peer, xff=None):
    """Request mínimo para probar `_ip_cliente` sin levantar HTTP."""
    cabeceras = {} if xff is None else {"x-forwarded-for": xff}
    return type("Pedido", (), {
        "client": type("Cliente", (), {"host": peer})(),
        "headers": cabeceras,
    })()


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
    # El portal lee el estado real: en tests, un estado.json de tmp.
    ruta_estado = str(tmp_path / "estado.json")
    ruta_log = str(tmp_path / "log_acciones.jsonl")
    monkeypatch.setattr(estado, "ARCHIVO", ruta_estado)
    monkeypatch.setattr(estado, "ARCHIVO_LOG", ruta_log)
    db.inicializar()
    db.crear_persona("santiago", "Santiago", mail="santiago@estudio.test")
    db.guardar_credencial("santiago", auth.hashear(CLAVE))
    db.crear_persona("jr", "Jr")
    db.guardar_credencial("jr", auth.hashear("clave-segura-456"))
    return Portal(TestClient(servidor_portal.app), config, tmp_path, ruta_estado, ruta_log)


def _login(portal, identificador="santiago", password=CLAVE):
    return portal.cliente.post(
        "/login",
        data={"identificador": identificador, "password": password},
        follow_redirects=False,
    )


# --- Sesión -------------------------------------------------------
def test_sin_sesion_da_401(portal):
    assert portal.cliente.get("/api/portal/novedades").status_code == 401


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


# --- Novedades y actividad (lectura del estado real) ---------------
def test_novedades_arranca_vacio(portal):
    _login(portal)
    r = portal.cliente.get("/api/portal/novedades")
    assert r.status_code == 200
    assert r.json()["cedulas"] == []
    assert r.json()["pendientes"] == []


def test_novedades_lee_el_estado_json(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "caratula": "Perez", "identidad_cadena": "Santiago",
         "fecha_generada": "2026-11-01T10:00:00"},
    ])
    r = portal.cliente.get("/api/portal/novedades")
    assert [c["id"] for c in r.json()["cedulas"]] == ["c1"]


def test_novedades_no_devuelve_rutas_ni_textos(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "identidad_cadena": "Santiago",
         "ruta_pdf": "C:/privado/cedula.pdf",
         "ruta_firmada": "C:/privado/firmada.pdf",
         "texto_decreto": "texto que no debe salir"},
    ])
    cedula = portal.cliente.get("/api/portal/novedades").json()["cedulas"][0]
    assert set(cedula) == set(hub.CAMPOS_CEDULA)
    assert "ruta_pdf" not in cedula
    assert "ruta_firmada" not in cedula
    assert "texto_decreto" not in cedula


def test_novedades_filtra_por_identidad(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "propia", "identidad_cadena": "Santiago"},
        {"id": "ajena", "identidad_cadena": "Jr"},
        {"id": "sin_cadena"},
    ])
    ids = [
        c["id"]
        for c in portal.cliente.get("/api/portal/novedades").json()["cedulas"]
    ]
    assert ids == ["propia"]


def test_novedades_admin_ve_todo(portal, monkeypatch):
    config_actual = db.config_portal
    monkeypatch.setattr(db, "config_portal", lambda nombre, default=None: (
        ["santiago"] if nombre == "PORTAL_ADMINISTRADORES" else config_actual(nombre, default)
    ))
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "propia", "identidad_cadena": "Santiago"},
        {"id": "ajena", "identidad_cadena": "Jr"},
        {"id": "sin_cadena"},
    ])
    ids = {
        c["id"]
        for c in portal.cliente.get("/api/portal/novedades").json()["cedulas"]
    }
    assert ids == {"propia", "ajena", "sin_cadena"}


def test_pendientes_ocultos_para_quien_no_es_admin(portal):
    _login(portal)
    _sembrar_estado(portal, pendientes=[{"id": "p1", "caratula": "Perez"}])
    assert portal.cliente.get("/api/portal/novedades").json()["pendientes"] == []


def test_admin_ve_los_pendientes(portal, monkeypatch):
    config_actual = db.config_portal
    monkeypatch.setattr(db, "config_portal", lambda nombre, default=None: (
        ["santiago"] if nombre == "PORTAL_ADMINISTRADORES" else config_actual(nombre, default)
    ))
    _login(portal)
    _sembrar_estado(portal, pendientes=[{"id": "p1", "caratula": "Perez"}])
    pendientes = portal.cliente.get("/api/portal/novedades").json()["pendientes"]
    assert [p["id"] for p in pendientes] == ["p1"]


def test_estado_json_corrupto_no_rompe_el_portal(portal):
    _login(portal)
    with open(portal.ruta_estado, "w", encoding="utf-8") as archivo:
        archivo.write("{ esto no es json")
    r = portal.cliente.get("/api/portal/novedades")
    assert r.status_code == 200
    assert r.json()["cedulas"] == []
    assert portal.cliente.get("/panel").status_code == 200


# --- Actividad (log real) -----------------------------------------
def test_actividad_lee_el_jsonl(portal):
    _login(portal)
    _sembrar_log(portal, [
        {"fecha_hora": "2026-11-01T10:00:00", "accion": "generada",
         "identidad": "Santiago", "operador": "Santiago", "id": "c1"},
    ])
    entradas = portal.cliente.get("/api/portal/actividad").json()["entradas"]
    assert entradas[0]["accion"] == "generada"
    assert entradas[0]["operador"] == "Santiago"


def test_log_tambien_lee_del_hub(portal):
    _login(portal)
    _sembrar_log(portal, [
        {"fecha_hora": "1", "accion": "generada", "identidad": "Santiago"},
    ])
    assert portal.cliente.get("/api/log").json()["entradas"][0]["accion"] == "generada"


def test_actividad_filtra_por_identidad_con_acentos(portal):
    # "José" no lo baja lower() de SQLite: el filtro tiene que ser en Python.
    db.crear_persona("jose", "José")
    db.guardar_credencial("jose", auth.hashear("clave-jose-1234"))
    _login(portal, identificador="jose", password="clave-jose-1234")
    _sembrar_log(portal, [
        {"fecha_hora": "1", "accion": "generada", "identidad": "José"},
        {"fecha_hora": "2", "accion": "generada", "identidad": "JOSÉ"},
        {"fecha_hora": "3", "accion": "generada", "identidad": "Jr"},
    ])
    entradas = portal.cliente.get("/api/portal/actividad").json()["entradas"]
    assert [e["identidad"] for e in entradas] == ["JOSÉ", "José"]


def test_actividad_aplica_el_limite_despues_de_filtrar(portal):
    _login(portal)
    _sembrar_log(portal, [
        {"fecha_hora": "1", "accion": "generada", "identidad": "Santiago"},
        {"fecha_hora": "2", "accion": "generada", "identidad": "Jr"},
        {"fecha_hora": "3", "accion": "generada", "identidad": "Jr"},
    ])
    # Si el límite se aplicara antes del filtro, el único resultado sería "Jr".
    entradas = portal.cliente.get("/api/portal/actividad?limite=1").json()["entradas"]
    assert len(entradas) == 1
    assert entradas[0]["identidad"] == "Santiago"


def test_log_rechaza_accion_vacia(portal):
    # Convertido del POST /api/log (commit 2): la validación vive en db.
    with pytest.raises(ValueError):
        db.agregar_log("")


# --- Ficha --------------------------------------------------------
def test_ficha_ida_y_vuelta(portal):
    _login(portal)
    r = portal.cliente.put("/api/ficha/CUIJ-1", json={"datos": {"caratula": "Perez"}})
    assert r.status_code == 200
    r = portal.cliente.get("/api/ficha/CUIJ-1")
    assert r.status_code == 200
    assert r.json()["ficha"]["caratula"] == "Perez"
    assert portal.cliente.get("/api/ficha/NO-EXISTE").status_code == 404


# --- Cédulas (lectura) --------------------------------------------
# Los endpoints de escritura (`PUT /api/cedulas/{id}`, `/cadena`,
# `/presentar`) se sacaron en el commit 2. Lo que prueban en db ya está
# cubierto por `tests/test_portal_db.py` y `tests/test_cadena.py`; acá
# queda solo lo que hace el servidor: leer y chequear la cadena de otra
# persona.
def test_cedula_cadena_de_otra_persona_frena(portal):
    _login(portal)
    # La cédula es de Jr (en el estado real); santiago no puede verla.
    _sembrar_estado(portal, cedulas=[{"id": "c1", "identidad_cadena": "Jr"}])
    # Y en db, D25 sigue frenando el cruce.
    db.guardar_cedula({"id": "c1", "identidad_cadena": "jr"})
    with pytest.raises(db.ConflictoCadena, match="D25"):
        db.guardar_cedula({"id": "c1", "identidad_cadena": "santiago"})
    with pytest.raises(db.ConflictoCadena, match="D25"):
        db.fijar_cadena_cedula("c1", "santiago")
    # 404, no 403 (no se filtra que existe).
    assert portal.cliente.get("/api/cedulas/c1").status_code == 404
    assert db.buscar_cedula("c1")["identidad_cadena"] == "jr"


def test_guardar_cedula_conserva_la_cadena(portal):
    # Convertido del PUT /api/cedulas/{id} (commit 2): upsert que no pisa D25.
    db.guardar_cedula({"id": "c1", "identidad_cadena": "jr"})
    db.guardar_cedula({"id": "c1", "caratula": "Perez"})
    assert db.buscar_cedula("c1")["identidad_cadena"] == "jr"


def test_cedula_inexistente_da_404(portal):
    _login(portal)
    assert portal.cliente.get("/api/cedulas/no-existe").status_code == 404


def test_filtrar_cedulas_por_estado(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "estado": "generada", "identidad_cadena": "Santiago"},
        {"id": "c2", "estado": "presentada", "identidad_cadena": "Santiago"},
    ])
    r = portal.cliente.get("/api/cedulas?estado=generada")
    assert [c["id"] for c in r.json()["cedulas"]] == ["c1"]


# --- Documentos ---------------------------------------------------
def test_subir_y_descargar_pdf(portal):
    _login(portal)
    # El PDF pertenece a una cédula: sin cadena propia el documento no se ve.
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "cuij": "CUIJ-1", "identidad_cadena": "Santiago"},
    ])
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
    r = portal.cliente.put(
        "/api/ficha/CUIJ-1",
        json={"datos": {"caratula": "Perez"}},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
    r = portal.cliente.put(
        "/api/ficha/CUIJ-1",
        json={"datos": {"caratula": "Perez"}},
        headers={"Origin": "http://testserver"},
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


# --- Auditoría (commit 2) -----------------------------------------
def test_login_ok_queda_en_auditoria_y_no_en_el_log(portal):
    r = _login(portal)
    assert r.status_code == 303
    filas = _auditoria_con("login")
    assert len(filas) == 1
    assert filas[0]["persona_id"] == "santiago"
    assert filas[0]["ip"] == "testclient"
    assert db.leer_log() == []


def test_login_fallido_recorta_el_detalle_y_no_ensucia_el_log(portal):
    identificador = "x" * 200
    r = _login(portal, identificador=identificador)
    assert r.status_code == 401
    filas = _auditoria_con("login_fallido")
    assert len(filas) == 1
    assert filas[0]["detalle"] == identificador[:80]
    assert len(filas[0]["detalle"]) == 80
    assert filas[0]["persona_id"] == identificador[:80]
    assert filas[0]["ip"] == "testclient"
    assert db.leer_log() == []


def test_logout_queda_en_auditoria_con_la_persona(portal):
    _login(portal)
    r = portal.cliente.post("/logout", follow_redirects=False)
    assert r.status_code == 303
    filas = _auditoria_con("logout")
    assert len(filas) == 1
    assert filas[0]["persona_id"] == "santiago"
    assert db.leer_log() == []


def test_registrar_log_escribe_una_linea_con_el_nombre_de_la_sesion(portal):
    _login(portal)
    persona = auth.persona_actual(
        portal.cliente.cookies.get(auth.NOMBRE_COOKIE)
    )
    request = type("Pedido", (), {"client": type("Cliente", (), {"host": "10.0.0.7"})()})()

    entrada = servidor_portal._registrar_log(
        persona, request, "firmada", id_cedula="c1", detalle="ok"
    )

    assert entrada["accion"] == "firmada"
    filas = db.leer_log()
    assert len(filas) == 1
    fila = filas[0]
    assert fila["identidad"] == "Santiago"
    assert fila["operador"] == "Santiago"
    assert fila["usuario"] == "portal"
    assert fila["maquina"] == "10.0.0.7"
    assert fila["id_cedula"] == "c1"
    assert fila["persona_id"] == "santiago"


@pytest.mark.parametrize(
    "metodo, ruta, cuerpo",
    [
        ("PUT", "/api/estado", {"datos": {"cedulas": []}}),
        ("PUT", "/api/cedulas/c1", {"cedula": {"id": "c1"}}),
        ("POST", "/api/cedulas/c1/cadena", None),
        ("POST", "/api/cedulas/c1/presentar", None),
        ("POST", "/api/log", {"accion": "generada"}),
    ],
)
def test_endpoints_de_escritura_borrados_dan_404_o_405(portal, metodo, ruta, cuerpo):
    _login(portal)
    kwargs = {} if cuerpo is None else {"json": cuerpo}
    r = portal.cliente.request(metodo, ruta, **kwargs)
    assert r.status_code in (404, 405)


# --- IP del cliente (Tailscale Serve) ------------------------------
def test_ip_cliente_usa_la_ultima_entrada_de_xff_detras_del_proxy():
    # Detrás de Serve el peer siempre es 127.0.0.1: la IP real viene en el
    # header, y vale la ÚLTIMA entrada (la agrega el proxy de confianza).
    assert servidor_portal._ip_cliente(
        _pedido("127.0.0.1", "9.9.9.9, 100.64.0.5")
    ) == "100.64.0.5"


def test_ip_cliente_ignora_xff_si_el_peer_no_es_local():
    # Si la conexión no viene del proxy, el header lo escribió el cliente.
    assert servidor_portal._ip_cliente(_pedido("100.64.0.9", "1.2.3.4")) == "100.64.0.9"


def test_ip_cliente_sin_xff_usa_el_peer():
    assert servidor_portal._ip_cliente(_pedido("100.64.0.9")) == "100.64.0.9"


def test_ip_cliente_recorta_a_45():
    assert len(servidor_portal._ip_cliente(_pedido("1" * 60))) == 45


def test_logout_sin_sesion_no_audita(portal):
    r = portal.cliente.post("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert _auditoria_con("logout") == []


# --- Visibilidad por identidad (commit 3) --------------------------
def test_visibilidad_por_defecto_solo_lo_propio(portal):
    persona = db.obtener_persona("santiago")
    propia = {"id": "c1", "identidad_cadena": "Santiago"}
    ajena = {"id": "c2", "identidad_cadena": "Jr"}
    sin_cadena = {"id": "c3"}
    assert permisos.puede_ver_cedula(propia, persona) is True
    assert permisos.puede_ver_cedula(ajena, persona) is False
    assert permisos.puede_ver_cedula(sin_cadena, persona) is False
    visibles = permisos.filtrar_cedulas([propia, ajena, sin_cadena], persona)
    assert [c["id"] for c in visibles] == ["c1"]


def test_visibilidad_normaliza_la_cadena(portal):
    persona = db.obtener_persona("santiago")
    assert permisos.puede_ver_cedula(
        {"id": "c1", "identidad_cadena": "  SANTIAGO "}, persona
    ) is True


def test_delegacion_permite_ver_lo_del_otro(portal):
    db.fijar_puede_actuar_como("santiago", ["Jr"])
    persona = db.obtener_persona("santiago")
    assert permisos.puede_ver_cedula({"id": "c2", "identidad_cadena": "jr"}, persona) is True


def test_administrador_ve_todo(portal, monkeypatch):
    config_actual = db.config_portal
    monkeypatch.setattr(
        db, "config_portal",
        lambda nombre, default=None: (
            ["santiago"]
            if nombre == "PORTAL_ADMINISTRADORES"
            else config_actual(nombre, default)
        ),
    )
    persona = db.obtener_persona("santiago")
    assert permisos.puede_ver_cedula({"id": "c3"}, persona) is True
    assert permisos.puede_ver_cedula({"id": "c2", "identidad_cadena": "Jr"}, persona) is True


def test_api_cedulas_filtra_y_api_cedula_da_404(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "identidad_cadena": "Santiago"},
        {"id": "c2", "identidad_cadena": "Jr"},
        {"id": "c3"},
    ])
    r = portal.cliente.get("/api/cedulas")
    assert [c["id"] for c in r.json()["cedulas"]] == ["c1"]
    assert portal.cliente.get("/api/cedulas/c1").status_code == 200
    assert portal.cliente.get("/api/cedulas/c2").status_code == 404
    assert portal.cliente.get("/api/cedulas/c3").status_code == 404


def test_api_log_filtra_por_identidad(portal):
    _login(portal)
    _sembrar_log(portal, [
        {"fecha_hora": "1", "accion": "generada", "identidad": "Santiago"},
        {"fecha_hora": "2", "accion": "generada", "identidad": "Jr"},
    ])
    entradas = portal.cliente.get("/api/log").json()["entradas"]
    assert [e["identidad"] for e in entradas] == ["Santiago"]


def test_pdf_de_otra_identidad_da_404(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "cuij": "CUIJ-1", "identidad_cadena": "Jr"},
    ])
    r = portal.cliente.post(
        "/api/documentos",
        files={"archivo": ("cedula.pdf", PDF, "application/pdf")},
        data={"cuij": "CUIJ-1"},
    )
    documento = r.json()["documento"]
    assert portal.cliente.get(f"/api/documentos/{documento['id']}").status_code == 404


# --- Cadena con delegación (D25 + puede_actuar_como) ---------------
def test_verificar_cadena_con_delegacion_pasa(portal):
    db.fijar_puede_actuar_como("santiago", ["Jr"])
    persona = db.obtener_persona("santiago")
    cedula = {"id": "c1", "identidad_cadena": "Jr"}
    # Devuelve la identidad de la CÉDULA, no la propia.
    assert permisos.verificar_cadena(cedula, persona) == "Jr"


def test_verificar_cadena_sin_delegacion_frena(portal):
    persona = db.obtener_persona("santiago")
    cedula = {"id": "c1", "identidad_cadena": "Jr"}
    with pytest.raises(permisos.ErrorPermiso, match="D25"):
        permisos.verificar_cadena(cedula, persona)


def test_identidad_de_usa_el_nombre_y_no_el_persona_id(portal):
    persona = db.obtener_persona("santiago")
    assert permisos.identidad_de(persona) == "Santiago"


def test_api_estado_ya_no_existe(portal):
    _login(portal)
    # Lo reemplaza /api/portal/novedades (commit 4a).
    assert portal.cliente.get("/api/estado").status_code == 404


def test_panel_muestra_novedades_y_actividad(portal):
    _login(portal)
    texto = portal.cliente.get("/panel").text
    assert "Novedades" in texto
    assert "Actividad" in texto
