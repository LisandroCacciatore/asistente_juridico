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
    _autoridad, _autoridad_51, _distrito, _fuero, _fuero_simple,
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


def test_autoridad_51_usa_el_modelo_del_sisfe():
    """El portal pone el cargo entre paréntesis y NO escribe 'Dr./Dra.'."""
    txt = _autoridad_51({"juez": "Silvana Laura Quagliatti",
                         "secretario": "Pedro Daniel Herrero"})
    assert txt == ("SILVANA LAURA QUAGLIATTI (JUEZ/A), "
                   "PEDRO DANIEL HERRERO (SECRETARIO / PROSECRETARIO)")
    assert "DR./DRA." not in txt


def test_autoridad_51_solo_juez():
    assert _autoridad_51({"juez": "Ana Pérez"}) == "ANA PÉREZ (JUEZ/A)"


def test_autoridad_51_el_prosecretario_ocupa_el_segundo_casillero():
    """El portal tiene dos casilleros: juez, y 'SECRETARIO / PROSECRETARIO'."""
    txt = _autoridad_51({"juez": "Ana Pérez", "prosecretario": "Marta Díaz"})
    assert txt == "ANA PÉREZ (JUEZ/A), MARTA DÍAZ (SECRETARIO / PROSECRETARIO)"


def test_autoridad_51_sin_nombres_devuelve_vacio():
    assert _autoridad_51({}) == ""
    assert _autoridad_51({"juez": "   "}) == ""


def test_autoridad_51_no_pierde_al_prosecretario_si_hay_secretario():
    """El portal tiene dos casilleros; nosotros no tiramos un dato del expediente."""
    txt = _autoridad_51({"juez": "Ana Pérez", "secretario": "Luis Gómez",
                         "prosecretario": "Marta Díaz"})
    assert txt == ("ANA PÉREZ (JUEZ/A), LUIS GÓMEZ (SECRETARIO / PROSECRETARIO), "
                   "MARTA DÍAZ (PROSECRETARIO)")


# ------------------------------------------- domicilio y distrito judicial
def test_distrito_de_las_ciudades_verificadas():
    assert _distrito({"ciudad": "Rosario"}) == "2"
    assert _distrito({"ciudad": "ROSARIO"}) == "2"
    assert _distrito({"ciudad": "Santa Fe"}) == "1"


def test_distrito_no_se_inventa_para_otra_ciudad():
    """Rafaela no está verificado: mejor sin el tramo que con un número inventado.

    Distrito judicial no es lo mismo que circunscripción, y la provincia los
    numera de forma no secuencial (San Jorge es el Nº 11).
    """
    assert _distrito({"ciudad": "Rafaela"}) == ""
    assert _distrito({"ciudad": "Venado Tuerto"}) == ""


def test_distrito_explicito_gana_sobre_la_tabla():
    assert _distrito({"ciudad": "Rafaela", "distrito": "5"}) == "5"


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


def test_c51_encabezado_como_el_portal(tmp_path, caso51):
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    assert "CÉDULA" in texto
    assert "JUZGADO EN LO LABORAL Nº 8 DISTRITO JUDICIAL NRO. 2 - ROSARIO" in texto


def test_c51_sin_distrito_verificado_no_lo_inventa(tmp_path, caso51):
    caso51["ciudad"] = "Rafaela"
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    assert "RAFAELA" in texto
    assert "DISTRITO JUDICIAL" not in texto


def test_c51_destinatario_domicilio_y_autoridad(tmp_path, caso51):
    """'Señor:' (no 'Señor/a:'), el domicilio de la S.R.L. y el cargo entre paréntesis."""
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    assert "Señor: CHICHILO'S PIZZAS SRL" in texto
    assert "CATAMARCA" in texto
    assert "QUAGLIATTI (JUEZ/A)" in texto
    assert "HERRERO (SECRETARIO / PROSECRETARIO)" in texto
    assert "DR./DRA." not in texto
    assert "Señor/a" not in texto


def test_c51_la_caratula_va_dentro_de_la_frase(tmp_path, caso51):
    """El portal no usa líneas 'Por:' / 'Contra:' / 'Sobre:' / 'Expte N°'."""
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    for etiqueta in ("Por:", "Contra:", "Sobre:", "Expte"):
        assert etiqueta not in texto
    assert "dentro de los autos caratulados" in texto
    assert "21-04267528-5" in texto


def test_c51_el_cierre_va_al_final(tmp_path, caso51):
    """El portal transcribe primero y cierra después, con una frase corta."""
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    cierre = "En consecuencia queda usted debidamente notificado del decreto que antecede"
    assert cierre in texto
    assert "29/05/2026" in texto and "09:45" in texto
    assert texto.index(cierre) > texto.index("ARTICULO 66")


def test_c51_transcribe_51_52_y_66_pero_no_71(tmp_path, caso51):
    """El decreto ordena transcribir los arts. 51, 52 y 66. El 71 no va."""
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    assert "ARTICULO 51" in texto
    assert "ARTÍCULO 52" in texto
    assert "ARTICULO 66" in texto
    assert "ARTICULO 71" not in texto


def test_c51_sin_bloque_de_firma(tmp_path, caso51):
    """El portal no imprime 'Firma y sello': la cédula se firma digitalmente."""
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    texto = _plano(ruta)
    assert "Firma y sello" not in texto
    assert "Sin más, lo saludo" not in texto


def test_c51_no_imprime_la_fecha_arriba(tmp_path, caso51):
    """El portal no pone la fecha suelta arriba: va dentro del decreto."""
    ruta = tmp_path / "c51.pdf"
    generar_pdf_audiencia_51(caso51, str(ruta))
    encabezado = _plano(ruta).split("Hago saber")[0]
    assert "07/04/2026" not in encabezado
