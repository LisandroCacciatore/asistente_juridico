# -*- coding: utf-8 -*-
"""El servidor HTTP del portal: login, estado, log, ficha y documentos.

Todo corre contra una base SQLite y una carpeta de subidas temporales:
ningún test toca `portal.db`, `portal_uploads/` ni `config.py` reales.
"""
import io
import json
import os
import re
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import estado
from portal import auth, csrf, db, hub, permisos, servidor_portal

PDF = b"%PDF-1.4\n% cedula de prueba\n"
CLAVE = "clave-segura-123"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    respuesta = portal.cliente.post(
        "/login",
        data={"identificador": identificador, "password": password},
        follow_redirects=False,
    )
    if respuesta.status_code == 303:
        # El token CSRF de la API se deriva de la cookie de sesión.
        cookie = portal.cliente.cookies.get(auth.NOMBRE_COOKIE)
        portal.cliente.headers["X-CSRF-Token"] = csrf.token(cookie)
    return respuesta


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


def test_cedula_cadena_de_otra_persona_frena(portal):
    _login(portal)
    # La cédula es de Jr (en el estado real); santiago no puede verla.
    _sembrar_estado(portal, cedulas=[{"id": "c1", "identidad_cadena": "Jr"}])
    # 404, no 403 (no se filtra que existe).
    assert portal.cliente.get("/api/cedulas/c1").status_code == 404


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


# --- PDF firmado de una cédula (commit 5) --------------------------
def _pdf(texto="CUIJ-1", firma="valida"):
    """PDF sintético con la estructura REAL de una firma.

    El campo `/FT /Sig` no lleva los datos: apunta con `/V` a un diccionario
    `/Type /Sig` con `/Filter`, `/SubFilter`, `/ByteRange` y `/Contents`, que
    es donde los pone un firmador de verdad.

    `firma`: "valida" | "sin_v" | "ceros" | "byterange_malo" | "ninguna".
    `texto`: lo que se dibuja en la página ("" = sin capa de texto).
    """
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (
        ArrayObject, ByteStringObject, DictionaryObject, NameObject,
        NumberObject, TextStringObject,
    )
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    lienzo = canvas.Canvas(buffer, pagesize=(300, 200))
    if texto:
        lienzo.drawString(20, 100, texto)
    lienzo.showPage()
    lienzo.save()

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(buffer.getvalue())))
    if firma == "ninguna":
        salida = io.BytesIO()
        writer.write(salida)
        return salida.getvalue()

    campo = DictionaryObject({
        NameObject("/FT"): NameObject("/Sig"),
        NameObject("/T"): TextStringObject("Firma1"),
        NameObject("/Rect"): ArrayObject([
            NumberObject(0), NumberObject(0), NumberObject(0), NumberObject(0),
        ]),
    })
    if firma != "sin_v":
        byte_range = (
            ArrayObject([NumberObject(0), NumberObject(10)])
            if firma == "byterange_malo"
            else ArrayObject([
                NumberObject(0), NumberObject(100),
                NumberObject(200), NumberObject(50),
            ])
        )
        contenido = (
            b"\x00" * 32
            if firma == "ceros"
            else b"\x30\x82\x01\x0a" + b"\x01" * 20
        )
        diccionario = DictionaryObject({
            NameObject("/Type"): NameObject("/Sig"),
            NameObject("/Filter"): NameObject("/Adobe.PPKLite"),
            NameObject("/SubFilter"): NameObject("/adbe.pkcs7.detached"),
            NameObject("/ByteRange"): byte_range,
            NameObject("/Contents"): ByteStringObject(contenido),
        })
        campo[NameObject("/V")] = writer._add_object(diccionario)

    raiz = writer._root_object
    acro = raiz.get("/AcroForm")
    if acro is None:
        acro = DictionaryObject()
        raiz[NameObject("/AcroForm")] = acro
    acro[NameObject("/Fields")] = ArrayObject([writer._add_object(campo)])

    salida = io.BytesIO()
    writer.write(salida)
    return salida.getvalue()


CEDULA_1B = {
    "id": "c1", "caratula": "Perez", "cuij": "CUIJ-1",
    "estado": "generada", "identidad_cadena": "Santiago", "tipo": "estandar",
}


def _sembrar_cedula(portal, **extra):
    datos = {**CEDULA_1B, **extra}
    _sembrar_estado(portal, cedulas=[datos])
    return datos


def _subir(portal, id_cedula="c1", contenido=None, cuij="CUIJ-1", caratula="Perez"):
    return portal.cliente.post(
        f"/api/portal/cedulas/{id_cedula}/subir",
        files={
            "archivo": (
                "firmada.pdf",
                _pdf() if contenido is None else contenido,
                "application/pdf",
            )
        },
        data={"cuij": cuij, "caratula": caratula},
    )


def test_subir_firmada_marca_la_cedula_y_loguea(portal):
    _login(portal)
    _sembrar_cedula(portal)
    r = _subir(portal)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["id"] == "c1"
    assert cuerpo["sha256"]
    assert cuerpo["estado"] == "firmada"
    # La ruta del servidor no sale por HTTP.
    assert "ruta" not in cuerpo

    cedula = estado.obtener_cedula("c1")
    assert cedula["estado"] == "firmada"
    assert cedula["fecha_firmada"]
    assert os.path.basename(cedula["ruta_firmada"]) == f"{cuerpo['sha256']}.pdf"
    assert os.path.abspath(cedula["ruta_firmada"]).startswith(
        os.path.abspath(portal.uploads)
    )

    entradas = [json.loads(l) for l in _lineas_log(portal)]
    subidas = [e for e in entradas if e["accion"] == "pdf_subido"]
    assert len(subidas) == 1
    assert subidas[0]["detalle"] == cuerpo["sha256"]
    assert subidas[0]["id"] == "c1"


def test_subir_sin_sesion_da_401(portal):
    _sembrar_cedula(portal)
    assert _subir(portal).status_code == 401


def test_subir_cedula_inexistente_da_404(portal):
    _login(portal)
    assert _subir(portal, id_cedula="no-existe").status_code == 404


def test_subir_cedula_ajena_da_404(portal):
    _login(portal)
    _sembrar_cedula(portal, identidad_cadena="Jr")
    assert _subir(portal).status_code == 404


def test_subir_admin_sin_delegacion_da_403(portal, monkeypatch):
    # El administrador NO es excepción: sin delegación explícita, 403.
    config_actual = db.config_portal
    monkeypatch.setattr(db, "config_portal", lambda nombre, default=None: (
        ["santiago"] if nombre == "PORTAL_ADMINISTRADORES" else config_actual(nombre, default)
    ))
    _login(portal)
    _sembrar_cedula(portal, identidad_cadena="Jr")
    assert _subir(portal).status_code == 403


def test_subir_con_delegacion_funciona(portal):
    db.fijar_puede_actuar_como("santiago", ["Jr"])
    _login(portal)
    _sembrar_cedula(portal, identidad_cadena="Jr")
    assert _subir(portal).status_code == 200
    assert estado.obtener_cedula("c1")["estado"] == "firmada"


def test_subir_sin_cadena_da_400(portal, monkeypatch):
    config_actual = db.config_portal
    monkeypatch.setattr(db, "config_portal", lambda nombre, default=None: (
        ["santiago"] if nombre == "PORTAL_ADMINISTRADORES" else config_actual(nombre, default)
    ))
    _login(portal)
    _sembrar_cedula(portal, identidad_cadena="")
    r = _subir(portal)
    assert r.status_code == 400
    assert "identidad fijada" in r.json()["detail"]


def test_subir_cedula_ya_firmada_da_409(portal):
    _login(portal)
    _sembrar_cedula(portal, estado="firmada")
    assert _subir(portal).status_code == 409


def test_subir_cabecera_invalida_da_400(portal):
    _login(portal)
    _sembrar_cedula(portal)
    r = _subir(portal, contenido=b"hola, esto no es un pdf")
    assert r.status_code == 400
    assert "%PDF-" in r.json()["detail"]


def test_subir_pdf_ilegible_da_400(portal):
    _login(portal)
    _sembrar_cedula(portal)
    r = _subir(portal, contenido=b"%PDF-1.4\nbasura que no parsea")
    assert r.status_code == 400
    assert "pypdf" in r.json()["detail"]


def test_subir_cuij_distinto_da_400(portal):
    _login(portal)
    _sembrar_cedula(portal)
    r = _subir(portal, cuij="CUIJ-OTRO")
    assert r.status_code == 400
    assert "CUIJ" in r.json()["detail"]


def test_subir_caratula_distinta_da_400(portal):
    _login(portal)
    _sembrar_cedula(portal)
    r = _subir(portal, caratula="Otra Caratula")
    assert r.status_code == 400
    assert "carátula" in r.json()["detail"]


def test_subir_pdf_sin_firma_da_400(portal):
    _login(portal)
    _sembrar_cedula(portal)
    r = _subir(portal, contenido=_pdf(firma="ninguna"))
    assert r.status_code == 400
    assert "/Sig" in r.json()["detail"]


def test_subir_campo_sin_v_da_400(portal):
    # Un campo /Sig sin /V no tiene firma: es un formulario vacío.
    _login(portal)
    _sembrar_cedula(portal)
    r = _subir(portal, contenido=_pdf(firma="sin_v"))
    assert r.status_code == 400
    assert "/V" in r.json()["detail"]


def test_subir_contenido_en_ceros_da_400(portal):
    # Marcador de firma sin firmar: /Contents todo en ceros.
    _login(portal)
    _sembrar_cedula(portal)
    assert _subir(portal, contenido=_pdf(firma="ceros")).status_code == 400


def test_subir_byterange_mal_formado_da_400(portal):
    _login(portal)
    _sembrar_cedula(portal)
    assert _subir(portal, contenido=_pdf(firma="byterange_malo")).status_code == 400


def test_subir_pdf_de_otra_causa_da_400(portal):
    # El formulario trae el CUIJ correcto, pero el PDF es de otro expediente.
    _login(portal)
    _sembrar_cedula(portal)
    r = _subir(portal, contenido=_pdf(texto="CUIJ-999"), cuij="CUIJ-1")
    assert r.status_code == 400
    assert "no aparece en el texto" in r.json()["detail"]


def test_subir_pdf_sin_texto_da_400(portal):
    _login(portal)
    _sembrar_cedula(portal)
    r = _subir(portal, contenido=_pdf(texto=""))
    assert r.status_code == 400
    assert "extraer texto" in r.json()["detail"]


def test_subir_tope_excedido_da_413(portal):
    portal.config["PORTAL_MAX_SUBIDA_MB"] = 1
    _login(portal)
    _sembrar_cedula(portal)
    grande = b"%PDF-1.4\n" + b"x" * (1024 * 1024 + 10)
    assert _subir(portal, contenido=grande).status_code == 413


def test_subir_el_mismo_pdf_en_otra_cedula_da_409(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        dict(CEDULA_1B, id="c1"),
        dict(CEDULA_1B, id="c2"),
    ])
    pdf = _pdf()
    assert _subir(portal, id_cedula="c1", contenido=pdf).status_code == 200
    assert _subir(portal, id_cedula="c2", contenido=pdf).status_code == 409


def test_bajar_el_pdf_firmado(portal):
    _login(portal)
    _sembrar_cedula(portal)
    assert _subir(portal).status_code == 200
    r = portal.cliente.get("/api/portal/cedulas/c1/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")


def test_bajar_pdf_sin_firmar_da_404(portal):
    _login(portal)
    _sembrar_cedula(portal)
    assert portal.cliente.get("/api/portal/cedulas/c1/pdf").status_code == 404


def test_bajar_pdf_ajeno_da_404(portal):
    _login(portal)
    _sembrar_cedula(portal, identidad_cadena="Jr")
    assert portal.cliente.get("/api/portal/cedulas/c1/pdf").status_code == 404


def test_dos_procesos_subiendo_solo_uno_gana(tmp_path, monkeypatch):
    """Dos procesos reales compitiendo por marcar la misma cédula."""
    ruta_estado = str(tmp_path / "estado.json")
    ruta_log = str(tmp_path / "log.jsonl")
    monkeypatch.setattr(estado, "ARCHIVO", ruta_estado)
    monkeypatch.setattr(estado, "ARCHIVO_LOG", ruta_log)
    estado.registrar_cedula({
        "id": "c1", "caratula": "Perez", "cuij": "CUIJ-1",
        "estado": "generada", "identidad_cadena": "Santiago",
    })

    guion = tmp_path / "intento.py"
    guion.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(RAIZ)!r})\n"
        "import estado\n"
        f"estado.ARCHIVO = {ruta_estado!r}\n"
        f"estado.ARCHIVO_LOG = {ruta_log!r}\n"
        "print(estado.marcar_firmada('c1', 'C:/tmp/f.pdf', identidad='Santiago',"
        " solo_si_generada=True))\n",
        encoding="utf-8",
    )
    procesos = [
        subprocess.Popen(
            [sys.executable, str(guion)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for _ in range(2)
    ]
    salidas = []
    for proceso in procesos:
        salida, _error = proceso.communicate(timeout=120)
        salidas.append(salida.strip().splitlines()[-1] if salida.strip() else "")
    assert sorted(salidas) == ["False", "True"]
    assert estado.obtener_cedula("c1")["estado"] == "firmada"


# --- CSRF y panel -------------------------------------------------
def test_csrf_bloquea_origen_externo(portal, monkeypatch):
    config_actual = db.config_portal
    monkeypatch.setattr(db, "config_portal", lambda nombre, default=None: (
        ["santiago"] if nombre == "PORTAL_ADMINISTRADORES" else config_actual(nombre, default)
    ))
    _login(portal)
    datos = {"persona_id": "nuevo", "nombre": "Nuevo"}
    r = portal.cliente.post(
        "/api/admin/personas", json=datos,
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
    r = portal.cliente.post(
        "/api/admin/personas", json=datos,
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
def _lineas_log(portal):
    """Líneas del log_acciones.jsonl de tmp (vacío si todavía no existe)."""
    if not os.path.exists(portal.ruta_log):
        return []
    with open(portal.ruta_log, encoding="utf-8") as archivo:
        return [linea for linea in archivo.read().splitlines() if linea.strip()]


def test_login_ok_queda_en_auditoria_y_no_en_el_log(portal):
    r = _login(portal)
    assert r.status_code == 303
    filas = _auditoria_con("login")
    assert len(filas) == 1
    assert filas[0]["persona_id"] == "santiago"
    assert filas[0]["ip"] == "testclient"
    assert _lineas_log(portal) == []


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
    assert _lineas_log(portal) == []


def test_logout_queda_en_auditoria_con_la_persona(portal):
    _login(portal)
    r = portal.cliente.post("/logout", follow_redirects=False)
    assert r.status_code == 303
    filas = _auditoria_con("logout")
    assert len(filas) == 1
    assert filas[0]["persona_id"] == "santiago"
    assert _lineas_log(portal) == []


def test_registrar_log_escribe_una_linea_en_el_jsonl(portal):
    _login(portal)
    persona = auth.persona_actual(
        portal.cliente.cookies.get(auth.NOMBRE_COOKIE)
    )
    request = _pedido("10.0.0.7")

    entrada = servidor_portal._registrar_log(
        persona, request, "firmada", id_cedula="c1", detalle="ok"
    )

    assert entrada["accion"] == "firmada"
    lineas = _lineas_log(portal)
    assert len(lineas) == 1
    fila = json.loads(lineas[0])
    assert fila["identidad"] == "Santiago"
    assert fila["operador"] == "Santiago"
    assert fila["usuario"] == "portal"
    assert fila["maquina"] == "10.0.0.7"
    assert fila["id"] == "c1"


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


# --- Fugas del hub: límites, origen y listado ----------------------
def test_limite_por_abajo_es_uno():
    assert servidor_portal._limite(0) == 1
    assert servidor_portal._limite(-5) == 1


def test_limite_por_arriba_es_200():
    assert servidor_portal._limite(999999) == hub.LIMITE_MAXIMO
    assert servidor_portal._limite(hub.LIMITE_MAXIMO) == hub.LIMITE_MAXIMO


def test_limite_invalido_usa_el_default():
    assert servidor_portal._limite("no-es-numero") == hub.LIMITE_POR_DEFECTO


@pytest.mark.parametrize("limite, esperado", [(0, 1), (-5, 1), (999999, 3)])
def test_actividad_respeta_el_limite_pedido(portal, limite, esperado):
    _login(portal)
    _sembrar_log(portal, [
        {"fecha_hora": str(numero), "accion": "generada", "identidad": "Santiago"}
        for numero in range(3)
    ])
    entradas = portal.cliente.get(
        f"/api/portal/actividad?limite={limite}"
    ).json()["entradas"]
    assert len(entradas) == esperado


def test_novedades_respeta_el_limite(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": f"c{numero}", "identidad_cadena": "Santiago",
         "fecha_generada": f"2026-11-0{numero + 1}T00:00:00"}
        for numero in range(3)
    ])
    assert len(
        portal.cliente.get("/api/portal/novedades?limite=999999").json()["cedulas"]
    ) == 3
    assert len(
        portal.cliente.get("/api/portal/novedades?limite=1").json()["cedulas"]
    ) == 1


def test_actividad_no_expone_usuario_ni_maquina(portal):
    _login(portal)
    _sembrar_log(portal, [{
        "fecha_hora": "1", "accion": "generada", "identidad": "Santiago",
        "usuario": "Torso", "maquina": "PC-LIS",
    }])
    entrada = portal.cliente.get("/api/portal/actividad").json()["entradas"][0]
    assert "usuario" not in entrada
    assert "maquina" not in entrada


def test_actividad_admin_si_ve_usuario_y_maquina(portal, monkeypatch):
    config_actual = db.config_portal
    monkeypatch.setattr(db, "config_portal", lambda nombre, default=None: (
        ["santiago"] if nombre == "PORTAL_ADMINISTRADORES" else config_actual(nombre, default)
    ))
    _login(portal)
    _sembrar_log(portal, [{
        "fecha_hora": "1", "accion": "generada", "identidad": "Santiago",
        "usuario": "Torso", "maquina": "PC-LIS",
    }])
    entrada = portal.cliente.get("/api/portal/actividad").json()["entradas"][0]
    assert entrada["usuario"] == "Torso"
    assert entrada["maquina"] == "PC-LIS"



def test_panel_muestra_el_id_de_la_cedula_en_actividad(portal):
    _login(portal)
    _sembrar_log(portal, [{
        "fecha_hora": "2026-11-01T10:00:00", "accion": "generada",
        "identidad": "Santiago", "id": "c1", "cuij": "CUIJ-1",
    }])
    texto = portal.cliente.get("/panel").text
    assert "2026-11-01T10:00:00" in texto
    assert ">c1<" in texto


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


# --- Bloqueo de login (commit 6) -----------------------------------
def _intentar(portal, identificador="santiago", password="mal"):
    return portal.cliente.post(
        "/login",
        data={"identificador": identificador, "password": password},
        follow_redirects=False,
    )


def test_cinco_fallos_bloquean_y_la_respuesta_no_cambia(portal):
    for _ in range(servidor_portal.FALLOS_POR_IDENTIFICADOR):
        r = _intentar(portal)
        assert r.status_code == 401
        assert servidor_portal.MENSAJE_LOGIN in r.text
    # Ni con la clave correcta: el mensaje es exactamente el mismo.
    r = _intentar(portal, password=CLAVE)
    assert r.status_code == 401
    assert servidor_portal.MENSAJE_LOGIN in r.text
    assert len(_auditoria_con("login_bloqueado")) == 1


def test_login_correcto_reinicia_el_contador(portal):
    for _ in range(4):
        _intentar(portal)
    assert _login(portal).status_code == 303
    # Cuatro fallos más: si el contador no se hubiera reiniciado, serían 8.
    for _ in range(4):
        _intentar(portal)
    assert _login(portal).status_code == 303


def test_el_bloqueo_por_ip_usa_un_umbral_mas_alto(portal):
    for numero in range(servidor_portal.FALLOS_POR_IP):
        _intentar(portal, identificador=f"usuario{numero}")
    # Ningún identificador llegó a 5, pero la IP llegó a 20.
    r = _intentar(portal, password=CLAVE)
    assert r.status_code == 401
    assert len(_auditoria_con("login_bloqueado")) == 1


def test_usuario_inexistente_hace_el_mismo_trabajo(portal):
    import time

    inicio = time.perf_counter()
    assert auth.autenticar("no-existe", "cualquier-cosa") is None
    transcurrido = time.perf_counter() - inicio
    # Sin el hash falso esto sería casi instantáneo y delataría qué usuarios existen.
    assert transcurrido > 0.005


# --- Cambio obligatorio de contraseña ------------------------------
CLAVE_PROVISORIA = "clave-provisoria-1"


def _persona_con_clave_provisoria(portal, persona_id="nuevo", nombre="Nuevo"):
    db.crear_persona(persona_id, nombre)
    db.guardar_credencial(
        persona_id, auth.hashear(CLAVE_PROVISORIA), debe_cambiar=1
    )
    return persona_id


def _entrar_como_nuevo(portal):
    return portal.cliente.post(
        "/login",
        data={"identificador": "nuevo", "password": CLAVE_PROVISORIA},
        follow_redirects=False,
    )


def _token_del_form(portal):
    return csrf.token(portal.cliente.cookies.get(auth.NOMBRE_COOKIE))


def test_debe_cambiar_redirige_y_bloquea_la_api(portal):
    _persona_con_clave_provisoria(portal)
    r = _entrar_como_nuevo(portal)
    assert r.status_code == 303
    assert r.headers["location"] == "/cambiar-password"

    panel = portal.cliente.get("/panel", follow_redirects=False)
    assert panel.status_code == 303
    assert panel.headers["location"] == "/cambiar-password"

    assert portal.cliente.get("/api/portal/novedades").status_code == 403
    assert portal.cliente.get("/cambiar-password").status_code == 200


def test_cambiar_password_corta_da_400(portal):
    _persona_con_clave_provisoria(portal)
    _entrar_como_nuevo(portal)
    r = portal.cliente.post(
        "/cambiar-password",
        data={"actual": CLAVE_PROVISORIA, "nueva": "corta1234", "repetida": "corta1234",
              "csrf": _token_del_form(portal)},
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "12" in r.text


def test_cambiar_password_igual_a_la_anterior_da_400(portal):
    _persona_con_clave_provisoria(portal)
    _entrar_como_nuevo(portal)
    r = portal.cliente.post(
        "/cambiar-password",
        data={"actual": CLAVE_PROVISORIA, "nueva": CLAVE_PROVISORIA,
              "repetida": CLAVE_PROVISORIA, "csrf": _token_del_form(portal)},
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "distinta" in r.text


def test_cambiar_password_ok_cierra_las_otras_sesiones(portal):
    _persona_con_clave_provisoria(portal)
    # Otra sesión de la misma persona, como si fuera otra PC.
    otra = TestClient(servidor_portal.app)
    assert otra.post(
        "/login",
        data={"identificador": "nuevo", "password": CLAVE_PROVISORIA},
        follow_redirects=False,
    ).status_code == 303
    _entrar_como_nuevo(portal)
    assert db.contar_sesiones("nuevo") == 2

    r = portal.cliente.post(
        "/cambiar-password",
        data={"actual": CLAVE_PROVISORIA, "nueva": "clave-nueva-larga-1",
              "repetida": "clave-nueva-larga-1", "csrf": _token_del_form(portal)},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/panel"
    assert db.contar_sesiones("nuevo") == 1
    assert db.obtener_credencial("nuevo")["debe_cambiar"] == 0
    assert len(_auditoria_con("password_cambiada")) == 1
    # Ya puede usar la API.
    portal.cliente.headers["X-CSRF-Token"] = csrf.token(
        portal.cliente.cookies.get(auth.NOMBRE_COOKIE)
    )
    assert portal.cliente.get("/api/portal/novedades").status_code == 200


def test_cambiar_password_sin_token_da_403(portal):
    _persona_con_clave_provisoria(portal)
    _entrar_como_nuevo(portal)
    r = portal.cliente.post(
        "/cambiar-password",
        data={"actual": CLAVE_PROVISORIA, "nueva": "clave-nueva-larga-1",
              "repetida": "clave-nueva-larga-1"},
        follow_redirects=False,
    )
    assert r.status_code == 403


# --- Token CSRF (commit 6) -----------------------------------------
def test_api_sin_token_da_403(portal):
    _login(portal)
    portal.cliente.headers.pop("X-CSRF-Token", None)
    assert portal.cliente.post("/api/admin/sesiones-borrar").status_code == 403


def test_api_con_token_incorrecto_da_403(portal):
    _login(portal)
    portal.cliente.headers["X-CSRF-Token"] = "no-es-el-token"
    assert portal.cliente.post("/api/admin/sesiones-borrar").status_code == 403


def test_get_no_necesita_token(portal):
    _login(portal)
    portal.cliente.headers.pop("X-CSRF-Token", None)
    assert portal.cliente.get("/api/portal/novedades").status_code == 200


def test_el_token_se_publica_en_sesion(portal):
    _login(portal)
    cuerpo = portal.cliente.get("/api/sesion").json()
    assert cuerpo["csrf"] == csrf.token(
        portal.cliente.cookies.get(auth.NOMBRE_COOKIE)
    )


# --- Endurecimiento del bloqueo (commit chico) ---------------------
def test_bloqueado_hace_el_mismo_trabajo_que_un_fallo(portal):
    import time

    for _ in range(servidor_portal.FALLOS_POR_IDENTIFICADOR):
        _intentar(portal)
    inicio = time.perf_counter()
    r = _intentar(portal, password=CLAVE)
    transcurrido = time.perf_counter() - inicio
    assert r.status_code == 401
    # Sin la verificación falsa esto sería casi instantáneo y delataría el bloqueo.
    assert transcurrido > 0.005


def test_el_bloqueo_se_audita_una_sola_vez_por_ventana(portal):
    for _ in range(servidor_portal.FALLOS_POR_IDENTIFICADOR):
        _intentar(portal)
    for _ in range(4):
        _intentar(portal, password=CLAVE)
    assert len(_auditoria_con("login_bloqueado")) == 1


def test_los_fallos_de_contrasena_actual_cuentan_para_el_bloqueo(portal):
    _persona_con_clave_provisoria(portal)
    _entrar_como_nuevo(portal)
    token = _token_del_form(portal)
    for _ in range(servidor_portal.FALLOS_POR_IDENTIFICADOR):
        portal.cliente.post(
            "/cambiar-password",
            data={"actual": "no-es-la-clave", "nueva": "clave-nueva-larga-1",
                  "repetida": "clave-nueva-larga-1", "csrf": token},
            follow_redirects=False,
        )
    # El identificador quedó bloqueado: ni con la clave correcta se entra.
    r = portal.cliente.post(
        "/login",
        data={"identificador": "nuevo", "password": CLAVE_PROVISORIA},
        follow_redirects=False,
    )
    assert r.status_code == 401


# --- Interfaz de subida y descarga (commit 7) ----------------------
def test_el_formulario_de_subida_aparece_en_generadas_operables(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "cuij": "CUIJ-1", "caratula": "Perez",
         "estado": "generada", "identidad_cadena": "Santiago"},
    ])
    html = portal.cliente.get("/panel").text
    assert 'class="subir"' in html
    assert 'data-id="c1"' in html
    assert 'data-cuij="CUIJ-1"' in html
    assert "Subir firmado" in html


def test_el_formulario_no_aparece_en_cedulas_que_no_puede_operar(portal, monkeypatch):
    # El admin ve la cédula de Jr pero, sin delegación, no puede operarla.
    config_actual = db.config_portal
    monkeypatch.setattr(db, "config_portal", lambda nombre, default=None: (
        ["santiago"] if nombre == "PORTAL_ADMINISTRADORES" else config_actual(nombre, default)
    ))
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "estado": "generada", "identidad_cadena": "Jr"},
    ])
    html = portal.cliente.get("/panel").text
    assert 'class="subir"' not in html
    assert "Cadena de Jr" in html


def test_la_cedula_ajena_no_aparece_ni_como_fila(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "estado": "generada", "identidad_cadena": "Jr"},
    ])
    html = portal.cliente.get("/panel").text
    assert ">c1<" not in html


def test_el_formulario_no_aparece_en_firmadas_ni_presentadas(portal):
    _login(portal)
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "estado": "firmada", "identidad_cadena": "Santiago"},
        {"id": "c2", "estado": "presentada", "identidad_cadena": "Santiago"},
    ])
    html = portal.cliente.get("/panel").text
    assert 'class="subir"' not in html
    assert "Descargar firmado" not in html


def test_el_enlace_de_descarga_solo_en_firmadas_con_pdf(portal):
    _login(portal)
    ruta = os.path.join(portal.uploads, "c1", "firmado.pdf")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as archivo:
        archivo.write(b"%PDF-1.4\n")
    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "estado": "firmada", "identidad_cadena": "Santiago",
         "ruta_firmada": ruta},
        {"id": "c2", "estado": "generada", "identidad_cadena": "Santiago"},
    ])
    html = portal.cliente.get("/panel").text
    assert 'href="/api/portal/cedulas/c1/pdf"' in html
    assert html.count("Descargar firmado") == 1


def test_el_script_usa_el_token_csrf_y_no_usa_innerhtml(portal):
    _login(portal)
    html = portal.cliente.get("/panel").text
    assert "X-CSRF-Token" in html
    assert "/api/sesion" in html
    assert "innerHTML" not in html
    assert "<script nonce=" in html


def test_el_nonce_del_csp_coincide_con_el_del_script(portal):
    import re as _re

    _login(portal)
    r = portal.cliente.get("/panel")
    nonce_html = _re.search(r'<script nonce="([^"]+)"', r.text).group(1)
    assert f"nonce-{nonce_html}" in r.headers["content-security-policy"]


def test_los_encabezados_de_seguridad_estan(portal):
    _login(portal)
    panel = portal.cliente.get("/panel")
    csp = panel.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "form-action 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert panel.headers["cache-control"] == "no-store"
    assert panel.headers["referrer-policy"] == "no-referrer"

    api = portal.cliente.get("/api/portal/novedades")
    assert api.headers["cache-control"] == "no-store"
    assert api.headers["referrer-policy"] == "no-referrer"


def test_el_pdf_se_sirve_sin_cache(portal):
    _login(portal)
    _sembrar_cedula(portal)
    assert _subir(portal).status_code == 200
    r = portal.cliente.get("/api/portal/cedulas/c1/pdf")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in r.headers["content-security-policy"]


# --- Ajustes post-revisión -----------------------------------------
def test_hay_una_sola_csp_en_el_panel(portal):
    _login(portal)
    r = portal.cliente.get("/panel")
    valores = r.headers.get_list("content-security-policy")
    assert len(valores) == 1
    assert valores[0].count("default-src") == 1


def _verificar_nonce(respuesta):
    nonces = re.findall(r'<script nonce="([^"]*)"', respuesta.text)
    # Ningún <script> sin nonce, y cada nonce presente en la cabecera.
    assert respuesta.text.count("<script") == len(nonces)
    for nonce in nonces:
        assert nonce
        assert f"nonce-{nonce}" in respuesta.headers["content-security-policy"]
    # El CSS va inline: el CSP tiene que permitirlo explícitamente.
    assert "style-src 'self' 'unsafe-inline'" in respuesta.headers[
        "content-security-policy"
    ]


def test_las_paginas_html_llevan_el_nonce(portal):
    _login(portal)
    for ruta in ("/panel", "/cambiar-password"):
        respuesta = portal.cliente.get(ruta)
        assert respuesta.status_code == 200
        _verificar_nonce(respuesta)

    # El login se pide sin sesión, con un cliente limpio.
    limpio = TestClient(servidor_portal.app)
    respuesta = limpio.get("/")
    assert respuesta.status_code == 200
    _verificar_nonce(respuesta)


def test_no_muestra_descarga_si_el_pdf_esta_fuera_de_uploads(portal, tmp_path):
    _login(portal)
    fuera = tmp_path / "firmado-fuera.pdf"
    fuera.write_bytes(b"%PDF-1.4\n")
    assert not str(fuera).startswith(str(portal.uploads))

    _sembrar_estado(portal, cedulas=[
        {"id": "c1", "estado": "firmada", "identidad_cadena": "Santiago",
         "ruta_firmada": str(fuera)},
    ])
    html = portal.cliente.get("/panel").text
    assert "Descargar firmado" not in html
