# -*- coding: utf-8 -*-
"""La regla de la cadena (SPEC D25).

    "Del SISFE que bajé, es el mismo que tiene que firmar."

Una cédula pertenece a **una sola identidad**: la sesión con la que se leyó
el expediente, la firma que se le pone y la sesión con la que se notifica
son la misma persona. El operador puede ser cualquiera y puede usar sus
claves o las de un compañero — eso está permitido; lo que no se puede es
**mezclar**.

Se prueba la regla en los tres lugares donde vive: el candado (estado), la
verificación (acciones) y de dónde sale la identidad cuando la cédula la
genera el monitor.
"""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import acciones  # noqa: E402
import estado  # noqa: E402
import monitor_playwright as mp  # noqa: E402
import sesion  # noqa: E402
import sisfe_notificar  # noqa: E402

GENTE = {
    "Santiago": {"mail": "santiago@estudio.com", "matricula": "LV029", "firma": "",
                 "perfil": "chrome_profile_portales"},
    "Jr":       {"mail": "jr@estudio.com", "matricula": "12345", "firma": "",
                 "perfil": "chrome_profile_jr"},
    "Socio":    {"mail": "", "matricula": "", "firma": "",
                 "perfil": "chrome_profile_socio"},
}


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    monkeypatch.setattr(sesion, "ARCHIVO", str(tmp_path / "sesion.json"))
    monkeypatch.setattr(sesion, "personas", lambda: GENTE)
    yield tmp_path


def _cedula(id_cedula="rivas_000001", cadena=""):
    estado.registrar_cedula({
        "id": id_cedula, "caratula": "RIVAS C/ ASOCIART ART SA S/ ENFERMEDAD LABORAL",
        "cuij": "21-04253894-6", "ruta_pdf": "", "ruta_firmada": "", "estado": "generada",
        "identidad_cadena": cadena,
    })
    return id_cedula


# ============================================================
#  El candado: de quién es la cédula (estado)
# ============================================================

def test_una_cedula_recien_hecha_no_es_de_nadie_todavia():
    assert estado.cadena_de(_cedula()) == ""


def test_fijar_la_cadena_y_leerla():
    c = _cedula()
    assert estado.fijar_cadena(c, "Santiago") == "Santiago"
    assert estado.cadena_de(c) == "Santiago"


def test_la_cadena_queda_asentada_en_el_log():
    c = _cedula()
    estado.fijar_cadena(c, "Santiago")
    entradas = [l for l in estado.leer_log() if l["accion"] == "cadena_fijada"]
    assert len(entradas) == 1
    assert entradas[0]["identidad"] == "Santiago"
    assert "Santiago" in entradas[0]["detalle"]


def test_la_cadena_no_se_cambia_por_atras():
    """Es un candado, no un dato que se corrige: si ya es de alguien, queda."""
    c = _cedula()
    estado.fijar_cadena(c, "Santiago")
    assert estado.fijar_cadena(c, "Jr") == "Santiago"
    assert estado.cadena_de(c) == "Santiago"


def test_fijar_la_misma_dos_veces_no_ensucia_el_log():
    c = _cedula()
    estado.fijar_cadena(c, "Santiago")
    estado.fijar_cadena(c, "Santiago")
    assert len([l for l in estado.leer_log() if l["accion"] == "cadena_fijada"]) == 1


def test_sin_identidad_no_se_fija_nada():
    c = _cedula()
    assert estado.fijar_cadena(c, "") == ""
    assert estado.cadena_de(c) == ""


# ============================================================
#  La verificación: se puede usar cualquier identidad, no mezclarlas
# ============================================================

def test_sin_cadena_la_identidad_que_se_elija_es_la_que_queda():
    assert acciones.verificar_cadena(_cedula(), "Jr") == "Jr"


def test_con_la_cadena_fijada_se_usa_la_de_la_cedula():
    c = _cedula(cadena="Santiago")
    assert acciones.verificar_cadena(c, "Santiago") == "Santiago"


def test_con_la_cadena_fijada_se_usa_la_de_la_cedula_aunque_no_se_diga_nada():
    """Nadie declaró identidad, pero la cédula ya es de alguien: manda la
    cédula."""
    c = _cedula(cadena="Santiago")
    assert acciones.verificar_cadena(c, "") == "Santiago"


def test_cruzar_la_cadena_se_frena_con_el_motivo():
    """El caso completo: la cédula salió del SISFE con la sesión de Santiago y
    se la quiere firmar con la de Jr. Se frena y se dice por qué."""
    c = _cedula(cadena="Santiago")
    with pytest.raises(acciones.AccionError) as e:
        acciones.verificar_cadena(c, "Jr")

    mensaje = str(e.value)
    assert "es de Santiago — matrícula LV029" in mensaje
    assert "identidad de Jr" in mensaje
    assert "no se puede cruzar" in mensaje


def test_una_cedula_que_no_existe_no_rompe_la_verificacion():
    assert acciones.verificar_cadena("", "Jr") == "Jr"
    assert acciones.verificar_cadena("no_existe", "Jr") == "Jr"


# ============================================================
#  De dónde sale la identidad: el monitor y la matrícula
# ============================================================

def test_el_monitor_marca_la_identidad_de_su_matricula(monkeypatch):
    """Las cédulas que baja el monitor son de quien entró al SISFE con la
    matrícula de esa máquina."""
    monkeypatch.setattr(mp, "SISFE_USUARIO", "LV029")
    assert mp._persona_de_la_matricula() == "Santiago"


def test_el_monitor_no_inventa_si_la_matricula_no_esta_en_la_lista(monkeypatch):
    """Matrícula desconocida: queda vacío y la cadena se fija en el primer acto
    del portal, con la identidad que se elija. No se adivina de quién es."""
    monkeypatch.setattr(mp, "SISFE_USUARIO", "OTRA-MATRICULA")
    assert mp._persona_de_la_matricula() == ""


def test_persona_por_matricula():
    assert sesion.persona_por_matricula("LV029") == "Santiago"
    assert sesion.persona_por_matricula("lv029") == "Santiago"
    assert sesion.persona_por_matricula("12345") == "Jr"
    assert sesion.persona_por_matricula("99999") == ""
    assert sesion.persona_por_matricula("") == ""


# ============================================================
#  Entrar con el mail (D26)
# ============================================================

def test_se_entra_con_el_mail():
    assert sesion.nombre_valido("jr@estudio.com") == "Jr"
    assert sesion.nombre_valido("SANTIAGO@ESTUDIO.COM") == "Santiago"


def test_el_nombre_todavia_sirve_si_no_hay_mail():
    """El socio no tiene mail cargado: entra con el nombre. El campo vacío no
    bloquea a nadie."""
    assert sesion.nombre_valido("Socio") == "Socio"
    assert sesion.nombre_valido("socio@estudio.com") == ""


def test_un_mail_de_afuera_no_entra():
    assert sesion.nombre_valido("alguien@gmail.com") == ""


def test_declarar_con_el_mail_guarda_el_nombre():
    s = sesion.declarar("jr@estudio.com")
    assert s["operador"] == "Jr"
    assert s["mail_operador"] == "jr@estudio.com"
    assert sesion.actual()["operador"] == "Jr"


# ============================================================
#  La regla, de punta a punta: notificar al SISFE
# ============================================================

def _cedula_firmada(tmp_path, cadena=""):
    ruta = tmp_path / "cedula_FIRMADO.pdf"
    ruta.write_bytes(b"%PDF-1.4\n% firmada\n")
    id_cedula = _cedula(cadena=cadena)
    estado.marcar_firmada(id_cedula, str(ruta))
    return id_cedula


def _subida_falsa(monkeypatch, resultado):
    def falso(ruta_pdf, cuij, caratula=None, descripcion=None,
              usar_chrome=True, pausar=None, elegir=None, perfil=None):
        return resultado
    monkeypatch.setattr(sisfe_notificar, "subir", falso)


def _ok():
    return {"ok": True, "cuij": "21-04253894-6", "id_sisfe": "1", "descripcion": "16/09/2026",
            "adjuntado": True, "partes": [], "tildadas": [], "avisos": [],
            "notificado": False}


def test_notificar_una_cedula_de_santiago_con_la_identidad_de_jr_se_frena(monkeypatch, tmp_path):
    id_cedula = _cedula_firmada(tmp_path, cadena="Santiago")
    _subida_falsa(monkeypatch, _ok())

    with pytest.raises(acciones.AccionError) as e:
        acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula, "identidad": "Jr"})

    assert "no se puede cruzar" in str(e.value)


def test_notificar_una_cedula_sin_dueno_le_fija_la_identidad(monkeypatch, tmp_path):
    """La cédula no tenía identidad: se fija con la del primer acto del portal,
    y queda asentada."""
    id_cedula = _cedula_firmada(tmp_path)
    sesion.declarar("Jr", identidad="Santiago")
    _subida_falsa(monkeypatch, _ok())

    r = acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    assert r["ok"] is True
    assert estado.cadena_de(id_cedula) == "Santiago"
    fijadas = [l for l in estado.leer_log() if l["accion"] == "cadena_fijada"]
    assert fijadas and fijadas[0]["identidad"] == "Santiago"


def test_notificar_una_cedula_sin_dueno_con_su_propia_identidad(monkeypatch, tmp_path):
    id_cedula = _cedula_firmada(tmp_path)
    sesion.declarar("Jr")
    _subida_falsa(monkeypatch, _ok())

    acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    assert estado.cadena_de(id_cedula) == "Jr"


def test_una_vez_fijada_la_cadena_los_demas_actos_la_respetan(monkeypatch, tmp_path):
    """Primero se notifica como Santiago (queda fijada); después, si alguien
    intenta firmar con Jr, se frena."""
    id_cedula = _cedula_firmada(tmp_path, cadena="Santiago")
    _subida_falsa(monkeypatch, _ok())
    acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula, "identidad": "Santiago"})

    assert acciones.verificar_cadena(id_cedula, "Santiago") == "Santiago"
    with pytest.raises(acciones.AccionError):
        acciones.verificar_cadena(id_cedula, "Jr")
