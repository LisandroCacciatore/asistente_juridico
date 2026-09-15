# -*- coding: utf-8 -*-
"""
TEST_CEDULA_DESDE_TEXTO.PY

Pruebas puras sobre cedula_desde_texto.py — sin Playwright, sin SISFE,
sin red. Corren en menos de un segundo y sirven de red de seguridad
para cualquier cambio futuro a las reglas de parseo/recorte.

Uso:  python -m pytest tests/test_cedula_desde_texto.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cedula_desde_texto import (
    es_sentencia, recortar_sentencia, extraer_caratula, extraer_cuij,
    extraer_fecha_decreto, extraer_juzgado, nombre_archivo_santiago,
)


# ============================================================
#  es_sentencia / recortar_sentencia
# ============================================================

SENTENCIA_REAL = """En la ciudad de Rosario, a los 4 días del mes de agosto de 2026, se
reúne el Tribunal...

Y VISTOS: Estos autos caratulados "GONZALEZ c/ ART EJEMPLO S/ ACCIDENTE
LABORAL" CUIJ 21-00000001-0, de trámite por ante este Juzgado...

DE LOS QUE RESULTA: Que se presenta la parte actora iniciando demanda...

CONSIDERANDO: Que corresponde analizar la prueba producida en autos...

Por ello, y de conformidad con la normativa citada, FALLO: 1) Haciendo
lugar a la demanda interpuesta por GONZALEZ contra ART EJEMPLO S.A.,
condenando a esta última a abonar la suma de PESOS UN MILLON. 2) Con
costas a la demandada. Insértese, regístrese y hágase saber.
Notifíquese."""

DECRETO_COMUN = """ROSARIO, 04 de Agosto de 2026.- Téngase presente lo
manifestado. Notifíquese por cédula."""


def test_es_sentencia_detecta_sentencia_real():
    assert es_sentencia(SENTENCIA_REAL) is True


def test_es_sentencia_no_marca_decreto_comun():
    assert es_sentencia(DECRETO_COMUN) is False


def test_es_sentencia_texto_vacio_no_rompe():
    assert es_sentencia("") is False
    assert es_sentencia(None) is False


def test_recortar_sentencia_incluye_marca_de_corte():
    recorte = recortar_sentencia(SENTENCIA_REAL)
    assert "[…]" in recorte


def test_recortar_sentencia_incluye_parte_resolutiva_completa():
    recorte = recortar_sentencia(SENTENCIA_REAL)
    assert "FALLO:" in recorte
    assert "Notifíquese" in recorte


def test_recortar_sentencia_no_transcribe_el_relato_completo():
    # el "DE LOS QUE RESULTA" (relato de hechos) NO debe quedar en el
    # recorte — es justo lo que se reemplaza por "[…]"
    recorte = recortar_sentencia(SENTENCIA_REAL)
    assert "DE LOS QUE RESULTA" not in recorte


def test_recortar_sentencia_no_toca_un_decreto_comun():
    # sobre un decreto común, recortar_sentencia debe devolver el texto
    # tal cual (no es sentencia, no hay nada que recortar)
    assert recortar_sentencia(DECRETO_COMUN) == DECRETO_COMUN


# ============================================================
#  extraer_caratula
# ============================================================

def test_extraer_caratula_entre_comillas():
    car = extraer_caratula(SENTENCIA_REAL)
    assert car == "GONZALEZ c/ ART EJEMPLO S/ ACCIDENTE LABORAL"


def test_extraer_caratula_sin_comillas_primera_linea():
    texto = "PEREZ WALTER JOSE C/ GALENO ART SA S/ ENFERMEDADES DEL TRABAJO\nJuzg. 1ra. Inst. Laboral 1ra. Nom."
    car = extraer_caratula(texto)
    assert car == "PEREZ WALTER JOSE C/ GALENO ART SA S/ ENFERMEDADES DEL TRABAJO"


def test_extraer_caratula_vacio_si_no_hay_patron():
    assert extraer_caratula("Un texto cualquiera sin carátula.") == ""


# ============================================================
#  extraer_cuij
# ============================================================

def test_extraer_cuij_encuentra_el_primero():
    assert extraer_cuij(SENTENCIA_REAL) == "21-00000001-0"


def test_extraer_cuij_vacio_si_no_hay():
    assert extraer_cuij("Sin ningún CUIJ acá.") == ""


# ============================================================
#  extraer_fecha_decreto
# ============================================================

def test_extraer_fecha_decreto_formato_dd_mm_aaaa():
    assert extraer_fecha_decreto("ROSARIO, 04 de Agosto de 2026.-") == "04/08/2026"


def test_extraer_fecha_decreto_dia_sin_cero_inicial():
    assert extraer_fecha_decreto("RAFAELA, 4 de julio de 2026") == "04/07/2026"


def test_extraer_fecha_decreto_vacio_si_no_hay():
    assert extraer_fecha_decreto("Texto sin ninguna fecha con ese formato.") == ""


# ============================================================
#  nombre_archivo_santiago
# ============================================================

def test_nombre_archivo_formato_esperado():
    nombre = nombre_archivo_santiago("FISCALÍA DE ESTADO PROVINCIAL", "04/08/2026")
    assert nombre == "Cédula a FISCALÍA DE ESTADO PROVINCIAL decreto fecha 04-08-26.pdf"


def test_nombre_archivo_sanitiza_caracteres_invalidos_de_windows():
    nombre = nombre_archivo_santiago('DESTINATARIO: "RARO"/<>', "01/01/2026")
    for caracter_prohibido in '<>:"/\\|?*':
        assert caracter_prohibido not in nombre


def test_nombre_archivo_sin_fecha_usa_hoy_sin_romper():
    # no debe lanzar excepción; el nombre tiene que seguir siendo válido
    nombre = nombre_archivo_santiago("ALGUIEN", "")
    assert nombre.startswith("Cédula a ALGUIEN decreto fecha ")
    assert nombre.endswith(".pdf")


# ============================================================
#  extraer_juzgado (best-effort, solo confirma que no rompe)
# ============================================================

def test_extraer_juzgado_no_rompe_con_texto_vacio():
    assert extraer_juzgado("") == ""
