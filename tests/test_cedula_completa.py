# -*- coding: utf-8 -*-
"""Cédula completa: fuero, ciudad, prosecretario y persona jurídica.

Cubre lo de la fase 1 del SPEC_CIRCUITO_v0.2.md. No necesita portal: son
plantillas y reglas sobre texto.
"""
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cedulas_pdf import (  # noqa: E402
    _autoridad, _autoridad_51, _es_juridica, _fuero, _fuero_simple,
    generar_pdf_estandar, generar_pdf_audiencia_51,
)
from cedula_desde_texto import extraer_ciudad, extraer_fuero  # noqa: E402


# ---------------------------------------------------------------- fuero
def test_fuero_por_defecto_es_laboral():
    assert _fuero({}) == "EN LO LABORAL"
    assert _fuero_simple({}) == "LABORAL"


@pytest.mark.parametrize("fuero,esperado", [
    ("CIVIL", "EN LO CIVIL"),
    ("COMERCIAL", "EN LO COMERCIAL"),
    ("CONTRACTUAL", "EN LO CONTRACTUAL"),
    ("FAMILIA", "EN LO FAMILIAR"),
    ("civil", "EN LO CIVIL"),
])
def test_fuero_de_los_otros_fueros(fuero, esperado):
    assert _fuero({"fuero": fuero}) == esperado


def test_fuero_desconocido_no_se_pierde():
    assert _fuero({"fuero": "PENAL"}) == "EN LO PENAL"


# ---------------------------------------------------------------- autoridad
def test_autoridad_completa():
    assert _autoridad({"juez": "Ana Pérez", "secretario": "Luis Gómez"}) == (
        "del/la DR./DRA. ANA PÉREZ (JUEZ), SECRETARIO DR./DRA. LUIS GÓMEZ"
    )


def test_autoridad_incluye_prosecretario():
    txt = _autoridad({
        "juez": "Ana Pérez", "secretario": "Luis Gómez",
        "prosecretario": "Marta Díaz",
    })
    assert txt.endswith("PROSECRETARIO DR./DRA. MARTA DÍAZ")


def test_autoridad_con_prosecretario_y_cargo_propio():
    txt = _autoridad({"secretario": "Luis Gómez", "prosecretario": "Marta Díaz",
                      "cargo_prosecretario": "PROSECRETARIA LETRADA"})
    assert "PROSECRETARIA LETRADA DR./DRA. MARTA DÍAZ" in txt


def test_autoridad_no_inventa_lo_que_falta():
    """Si falta un nombre, no aparece '____' ni una coma colgando."""
    assert _autoridad({"juez": "Ana Pérez"}) == "del/la DR./DRA. ANA PÉREZ (JUEZ)"
    assert _autoridad({"secretario": "Luis Gómez"}) == "del/la SECRETARIO DR./DRA. LUIS GÓMEZ"
    assert _autoridad({}) == ""
    assert _autoridad({"juez": "   "}) == ""


def test_autoridad_51_mantiene_su_redaccion():
    txt = _autoridad_51({"juez": "Ana Pérez", "secretario": "Luis Gómez"})
    assert txt == "la/el DRA./DR. ANA PÉREZ (JUEZ), SECRETARIO de la/el DRA./DR. LUIS GÓMEZ"


# ---------------------------------------------------------------- jurídica
@pytest.mark.parametrize("nombre", [
    "ART EJEMPLO S.A.", "COMERCIAL EJEMPLO S.R.L.", "MUNICIPALIDAD DE ROSARIO",
    "CAJA FORENSE ROSARIO", "BANCO MUNICIPAL", "FISCO DE LA PROVINCIA",
])
def test_detecta_persona_juridica(nombre):
    assert _es_juridica({"destinatario_nombre": nombre}) is True


@pytest.mark.parametrize("nombre", ["Juan Pérez", "MARIA GOMEZ", "RODRIGUEZ, ANA"])
def test_detecta_persona_fisica(nombre):
    assert _es_juridica({"destinatario_nombre": nombre}) is False


def test_flag_explicito_gana_sobre_la_heuristica():
    assert _es_juridica({"destinatario_nombre": "Juan Pérez",
                         "destinatario_es_juridica": True}) is True
    assert _es_juridica({"destinatario_nombre": "ART EJEMPLO S.A.",
                         "destinatario_es_juridica": False}) is False


# ---------------------------------------------------------------- PDF real
def _texto(ruta):
    return " ".join((p.extract_text() or "") for p in PdfReader(str(ruta)).pages)


@pytest.fixture
def base():
    return {
        "caratula": "PEREZ c/ ART EJEMPLO S.A. S/ ACCIDENTE LABORAL",
        "cuij": "21-00000001-0", "nominacion": "3", "fecha_decreto": "01/03/2026",
        "texto_decreto": "Notifíquese.", "juez": "Ana Pérez",
        "secretario": "Luis Gómez", "destinatario_nombre": "Juan Pérez",
        "destinatario_domicilio": "Calle Falsa 123 - Rosario",
    }


def test_pdf_estandar_muestra_prosecretario(tmp_path, base):
    base["prosecretario"] = "Marta Díaz"
    ruta = tmp_path / "c.pdf"
    generar_pdf_estandar(base, str(ruta))
    texto = _texto(ruta)
    assert "MARTA DÍAZ" in texto
    assert "PROSECRETARIO" in texto


def test_pdf_estandar_sin_juez_ni_secretario_no_deja_guiones(tmp_path, base):
    del base["juez"], base["secretario"]
    ruta = tmp_path / "c.pdf"
    generar_pdf_estandar(base, str(ruta))
    texto = _texto(ruta)
    # El cuerpo es lo que va antes del cierre; la firma SÍ lleva una línea de
    # guiones bajos a propósito, así que no se cuenta.
    cuerpo = texto.split("En consecuencia")[0]
    assert "___" not in cuerpo
    assert "None" not in texto
    assert "a cargo" not in texto


def test_pdf_estandar_fuero_civil(tmp_path, base):
    base["fuero"] = "CIVIL"
    ruta = tmp_path / "c.pdf"
    generar_pdf_estandar(base, str(ruta))
    texto = _texto(ruta)
    assert "EN LO CIVIL" in texto
    assert "JUZGADO CIVIL" in texto
    assert "EN LO LABORAL" not in texto


def test_pdf_juridica_no_imprime_domicilio(tmp_path, base):
    base["destinatario_nombre"] = "ART EJEMPLO S.A."
    ruta = tmp_path / "c.pdf"
    generar_pdf_estandar(base, str(ruta))
    assert "Domicilio" not in _texto(ruta)


def test_pdf_fisica_si_imprime_domicilio(tmp_path, base):
    ruta = tmp_path / "c.pdf"
    generar_pdf_estandar(base, str(ruta))
    texto = _texto(ruta)
    assert "Domicilio" in texto and "Calle Falsa 123" in texto


def test_pdf_sin_destinatario_no_imprime_la_linea(tmp_path, base):
    del base["destinatario_nombre"]
    ruta = tmp_path / "c.pdf"
    generar_pdf_estandar(base, str(ruta))
    texto = _texto(ruta)
    assert "Señor/a" not in texto
    assert "Domicilio" not in texto


def test_pdf_audiencia_51_con_prosecretario(tmp_path, base):
    base["prosecretario"] = "Marta Díaz"
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(base, str(ruta))
    assert "MARTA DÍAZ" in _texto(ruta)


# ---------------------------------------------------------------- extractores
@pytest.mark.parametrize("texto,esperado", [
    ("ROSARIO, 04 de Agosto de 2026.-\nNotifíquese.", "ROSARIO"),
    ("En la ciudad de RAFAELA, a los 4 días del mes de agosto de 2026", "RAFAELA"),
    ("JUZGADO DE 1RA. INST. LABORAL 2DA. NOM. DE VENADO TUERTO", "VENADO TUERTO"),
    ("", ""),
    ("Texto sin ciudad alguna", ""),
])
def test_extraer_ciudad(texto, esperado):
    assert extraer_ciudad(texto) == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("Juzg. 1ra. Inst. Laboral 3ra. Nom. SEC.UNICA", "LABORAL"),
    ("JUZGADO DE PRIMERA INSTANCIA EN LO CIVIL Y COMERCIAL 12ma NOM.", "CIVIL"),
    ("Juzgado de Primera Instancia en lo Comercial 5ta Nom.", "COMERCIAL"),
    ("Juzg. 1ra. Inst. Contractual 2da Nom.", "CONTRACTUAL"),
    ("Juzg.Unipersonal de Familia N° 8 - ROSARIO", "FAMILIA"),
    ("", ""),
])
def test_extraer_fuero(texto, esperado):
    assert extraer_fuero(texto) == esperado
