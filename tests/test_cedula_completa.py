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
    _autoridad, _fuero, _fuero_simple, _juzgado_cuerpo, _juzgado_encabezado,
    generar_pdf_estandar, generar_pdf_audiencia_51, generar_pdf_peritos,
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


# --------------------------------------------- cómo se nombra el juzgado
def test_encabezado_del_juzgado_con_nominacion():
    """Así lo escribe el portal en la común (5ª/10ª Nom. de Rosario)."""
    txt = _juzgado_encabezado({"nominacion": "5", "ciudad": "Rosario"})
    assert txt == ("JUZGADO DE PRIMERA INSTANCIA DE DISTRITO EN LO LABORAL "
                   "DE LA 5 NOMINACIÓN DE ROSARIO")


def test_encabezado_del_juzgado_sin_nominacion():
    """Reconquista tiene un solo juzgado del trabajo: 'DE LA LOCALIDAD DE …'."""
    txt = _juzgado_encabezado({"ciudad": "Reconquista"})
    assert txt == ("JUZGADO DE PRIMERA INSTANCIA DE DISTRITO EN LO LABORAL "
                   "DE LA LOCALIDAD DE RECONQUISTA")


def test_encabezado_del_juzgado_de_otro_fuero():
    txt = _juzgado_encabezado({"nominacion": "12", "ciudad": "Rafaela", "fuero": "CIVIL"})
    assert txt == ("JUZGADO DE PRIMERA INSTANCIA DE DISTRITO EN LO CIVIL "
                   "DE LA 12 NOMINACIÓN DE RAFAELA")


def test_el_nombre_cargado_del_juzgado_gana():
    """Si el expediente trae el nombre del juzgado, se usa tal cual.

    El Juzgado Laboral Nº 8 se nombra distinto ('JUZGADO EN LO LABORAL Nº 8
    DISTRITO JUDICIAL NRO. 2 - ROSARIO') y ese número de distrito no se deduce
    de la ciudad: distrito judicial no es la circunscripción y la provincia
    los numera sin orden (San Jorge es el Nº 11).
    """
    datos = {"juzgado_header": "JUZGADO EN LO LABORAL Nº 8 DISTRITO JUDICIAL NRO. 2 - ROSARIO"}
    assert _juzgado_encabezado(datos) == (
        "JUZGADO EN LO LABORAL Nº 8 DISTRITO JUDICIAL NRO. 2 - ROSARIO")
    assert _juzgado_cuerpo(datos) == (
        "JUZGADO EN LO LABORAL Nº 8 DISTRITO JUDICIAL NRO. 2 - ROSARIO")


def test_en_la_frase_el_juzgado_va_con_la_ciudad():
    """Dentro de la frase el portal agrega 'LA CIUDAD DE'."""
    assert _juzgado_cuerpo({"nominacion": "10", "ciudad": "Rosario"}) == (
        "JUZGADO LABORAL DE LA 10 NOMINACIÓN DE LA CIUDAD DE ROSARIO")
    assert _juzgado_cuerpo({"ciudad": "Reconquista"}) == (
        "JUZGADO LABORAL DE LA LOCALIDAD DE RECONQUISTA")


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


def test_pdf_imprime_el_domicilio_tambien_en_persona_juridica(tmp_path, base):
    """Una cédula real del SISFE imprime el domicilio de una S.R.L. (16/09/2026).

    Antes se suprimía por ser persona jurídica. En el Art. 51 ese domicilio no
    es decorativo: el artículo manda citar a las partes "en el real".
    """
    base["destinatario_nombre"] = "CHICHILO'S PIZZAS SRL"
    base["destinatario_domicilio"] = "CATAMARCA Nº 2501 DE LA CIUDAD ROSARIO"
    ruta = tmp_path / "c.pdf"
    generar_pdf_estandar(base, str(ruta))
    texto = _texto(ruta)
    assert "Domicilio" in texto
    assert "CATAMARCA" in texto


def test_pdf_sin_domicilio_no_inventa_la_linea(tmp_path, base):
    del base["destinatario_domicilio"]
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
    assert "Señor" not in texto
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


# ============================================================
#  Modelo del SISFE para el Art. 51 (16/09/2026)
# ------------------------------------------------------------
#  Comparado contra una cédula real del portal: Juzgado en lo Laboral Nº 8
#  de Rosario, "PALOMEQUE YAIR MILTON C/ CHICHILO'S PIZZAS SRL", 07/04/2026.
#  Los datos de acá abajo son los de ese caso.
# ============================================================
def _plano(ruta):
    """Texto del PDF con los espacios normalizados (para comparar frases)."""
    return " ".join(_texto(ruta).split())


@pytest.fixture
def caso51():
    return {
        "nominacion": "8", "ciudad": "Rosario", "fuero": "LABORAL",
        "caratula": "PALOMEQUE YAIR MILTON C/ CHICHILO'S PIZZAS SRL S/ COBRO DE PESOS",
        "cuij": "21-04267528-5",
        "juez": "Silvana Laura Quagliatti", "secretario": "Pedro Daniel Herrero",
        "fecha_decreto": "07/04/2026",
        "texto_decreto": "Téngase al compareciente por presentado. Notifíquese por cédula.",
        "destinatario_nombre": "CHICHILO'S PIZZAS SRL",
        "destinatario_domicilio": "CATAMARCA Nº 2501 DE LA CIUDAD ROSARIO",
        "fecha_audiencia": "29/05/2026", "hora_audiencia": "09:45",
    }


def test_c51_es_la_comun_mas_los_articulos(tmp_path, caso51):
    """Santiago (16/09/2026): la del Art. 51 es la común + los arts. 51, 52 y 66."""
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    # el encabezado, el destinatario y la frase son los de la común
    assert ("JUZGADO DE PRIMERA INSTANCIA DE DISTRITO EN LO LABORAL "
            "DE LA 8 NOMINACIÓN DE ROSARIO") in texto
    assert "Señor: CHICHILO'S PIZZAS SRL" in texto
    assert "Domicilio: CATAMARCA" in texto
    assert "dentro de los autos caratulados" in texto
    assert "se ha dictado lo siguiente" in texto
    # lo que agrega es la transcripción de los tres artículos y nada más
    assert "ARTICULO 51" in texto
    assert "ARTÍCULO 52" in texto
    assert "ARTICULO 66" in texto
    assert "ARTICULO 71" not in texto
    # y el cierre va al final
    assert texto.index("ARTICULO 66") < texto.index("En consecuencia")


def test_c51_el_nombre_cargado_del_juzgado_manda(tmp_path, caso51):
    """Para un juzgado que se nombra distinto, el nombre viene en el dato."""
    caso51["juzgado_header"] = "JUZGADO EN LO LABORAL Nº 8 DISTRITO JUDICIAL NRO. 2 - ROSARIO"
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    assert "JUZGADO EN LO LABORAL Nº 8 DISTRITO JUDICIAL NRO. 2 - ROSARIO" in texto
    assert "DE LA 8 NOMINACIÓN" not in texto


def test_c51_sin_bloque_de_firma(tmp_path, caso51):
    """Las cédulas reales no traen 'Firma y sello': se firman digitalmente."""
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    assert "Firma y sello" not in texto
    assert "Sin más, lo saludo" not in texto
    assert "Saluda Atte" not in texto


def test_c51_no_imprime_la_fecha_arriba_ni_la_duplica(tmp_path, caso51):
    """La fecha va dentro del decreto, una sola vez."""
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    assert texto.count("07/04/2026") == 1
    assert "07/04/2026" not in texto.split("Hago saber")[0]


# ============================================================
#  Cédula de peritos: la común + los arts. 78 y 79 (16/09/2026)
# ------------------------------------------------------------
#  Comparada contra una cédula real del SISFE: designación del perito
#  MUÑOZ MARCELO ALFREDO (Juzgado de Primera Instancia de Distrito en lo
#  Laboral de la Localidad de Reconquista, "FERRERO C/ PREVENCION ART SA").
# ============================================================
@pytest.fixture
def caso_perito():
    return {
        "nominacion": "", "ciudad": "Reconquista", "fuero": "LABORAL",
        "caratula": "FERRERO HECTOR ALFREDO C/ PREVENCION ART SA S/ ENFERMEDAD PROFESIONAL",
        "cuij": "21-16746052-3", "fecha_decreto": "",
        "juez": "Jorgelina Yedro", "secretario": "Leonardo Cristófoli",
        "texto_decreto": ("En la ciudad de Reconquista, siendo dia y hora de audiencia, "
                          "resulta sorteado el profesional MUÑOZ MARCELO ALFREDO. "
                          "Todo por ante mi que doy fe.-"),
        "destinatario_nombre": "MUÑOZ MARCELO ALFREDO",
        "destinatario_domicilio": "Olessio N° 1577 - Reconquista",
    }


def test_peritos_encabezado_de_localidad(tmp_path, caso_perito):
    """Reconquista no numera su juzgado: 'DE LA LOCALIDAD DE RECONQUISTA'."""
    ruta = tmp_path / "per.pdf"
    generar_pdf_peritos(caso_perito, str(ruta))
    texto = _plano(ruta)
    assert ("JUZGADO DE PRIMERA INSTANCIA DE DISTRITO EN LO LABORAL "
            "DE LA LOCALIDAD DE RECONQUISTA") in texto
    assert "Señor: MUÑOZ MARCELO ALFREDO" in texto
    assert "Domicilio: Olessio N° 1577 - Reconquista" in texto


def test_peritos_agrega_la_intimacion_y_los_arts_78_y_79(tmp_path, caso_perito):
    ruta = tmp_path / "per.pdf"
    generar_pdf_peritos(caso_perito, str(ruta))
    texto = _plano(ruta)
    assert "Se hace saber a Ud. su designación y se lo/la intima a ACEPTAR EL CARGO" in texto
    assert "se transcriben los artículos 78 y 79" in texto
    assert "ARTÍCULO 78. (Aceptación)" in texto
    assert "ARTÍCULO 79. (Plazo)" in texto


def test_peritos_no_lleva_los_articulos_del_51(tmp_path, caso_perito):
    """Los arts. 51, 52 y 66 son de la cédula de audiencia, no de la de peritos."""
    ruta = tmp_path / "per.pdf"
    generar_pdf_peritos(caso_perito, str(ruta))
    texto = _plano(ruta)
    assert "ARTICULO 51" not in texto
    assert "ARTICULO 66" not in texto


def test_peritos_cierra_como_la_comun(tmp_path, caso_perito):
    ruta = tmp_path / "per.pdf"
    generar_pdf_peritos(caso_perito, str(ruta))
    texto = _plano(ruta)
    assert texto.rstrip().endswith(
        "En consecuencia queda usted debidamente notificado del decreto que antecede.")
    assert "Firma y sello" not in texto
