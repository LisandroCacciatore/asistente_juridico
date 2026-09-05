#!/usr/bin/env python3
"""Genera los 3 oficios por incumplimiento al pago de boletas (Colegio de Abogados,
Caja de Seguridad Social y Caja Forense) en PDF, a partir de un JSON de datos.

Uso: python3 generar_oficios.py datos.json [carpeta_salida]
Formato: texto justificado, títulos centrados. Requiere reportlab.
"""
import json
import sys
import os

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether

FONT = "Times-Roman"
FONT_B = "Times-Bold"
SIZE = 12

ART25 = ('"ARTÍCULO 25: Será también deber de los defensores, como auxiliares de la '
         'justicia, colaborar en el desarrollo e impulsión de los procesos en que '
         'intervengan. Con este objeto, sin perjuicio de las funciones del secretario, '
         'los abogados y procuradores podrán realizar los actos siguientes: a) Firmar y '
         'diligenciar los oficios dirigidos a Bancos, oficinas públicas o entes privados, '
         'sólo con respecto a pedidos de informes, saldos o estados de cuentas; así como '
         'solicitudes de certificados y liquidaciones;…".-')

# Los 3 destinatarios fijos de este tipo de oficio.
DESTINATARIOS = [
    ("COLEGIO DE ABOGADOS - ROSARIO", "OFICIO A COLEGIO DE ABOGADOS ROSARIO"),
    ("CAJA DE SEG. SOCIAL DE ABOGADOS Y PROCURADORES", "OFICIO A CAJA DE SEG. SOC"),
    ("CAJA FORENSE - ROSARIO", "OFICIO A CAJA FORENSE"),
]


def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def frase_profesionales(profs):
    """Arma: 'los Dres. NOMBRE1 (MAT1) y NOMBRE2 (MAT2), <extra>'."""
    partes = []
    extra = ""
    for p in profs:
        s = p["nombre"].strip()
        if p.get("matricula"):
            s += f" ({p['matricula'].strip()})"
        partes.append(s)
        if p.get("extra"):
            extra = p["extra"].strip()
    listado = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]
    txt = f"el incumplimiento correspondiente al pago de las boletas a las Cajas Profesionales de los Dres. {listado}"
    if extra:
        txt += f", {extra}"
    return txt


def build_styles():
    return {
        "titulo": ParagraphStyle("titulo", fontName=FONT_B, fontSize=SIZE,
                                 alignment=TA_CENTER, spaceAfter=14, leading=16),
        "left": ParagraphStyle("left", fontName=FONT, fontSize=SIZE,
                               alignment=TA_LEFT, spaceAfter=8, leading=14),
        "left0": ParagraphStyle("left0", fontName=FONT, fontSize=SIZE,
                                alignment=TA_LEFT, spaceAfter=0, leading=14),
        "just": ParagraphStyle("just", fontName=FONT, fontSize=SIZE,
                               alignment=TA_JUSTIFY, spaceAfter=8, leading=14),
        "just_ind": ParagraphStyle("just_ind", fontName=FONT, fontSize=SIZE,
                                   alignment=TA_JUSTIFY, spaceAfter=8, leading=14,
                                   leftIndent=1.2 * cm),
        "center": ParagraphStyle("center", fontName=FONT, fontSize=SIZE,
                                 alignment=TA_CENTER, spaceAfter=0, leading=15),
        "centerb": ParagraphStyle("centerb", fontName=FONT_B, fontSize=SIZE,
                                  alignment=TA_CENTER, spaceAfter=0, leading=15),
    }


def build_oficio(data, destinatario, styles):
    juzgado = esc(data["juzgado"])
    caratula = esc(data["caratula"])
    mes = esc(data.get("fecha_mes", ""))
    anio = esc(data.get("fecha_anio", ""))
    decreto = esc(data["decreto_transcripto"])
    profs_txt = esc(frase_profesionales(data["profesionales"]))

    S = styles
    flow = []
    flow.append(Paragraph("O F I C I O", S["titulo"]))
    flow.append(Paragraph("<b>NRO. ___________</b>", S["left"]))
    flow.append(Paragraph(f"Rosario, ____ de {mes} de {anio}.-", S["left"]))
    flow.append(Paragraph("<b>SRES.</b>", S["left0"]))
    flow.append(Paragraph(f"<b><u>{esc(destinatario)}</u></b>", S["left0"]))
    flow.append(Paragraph("<b>Rosario, Provincia de Santa Fe</b>", S["left"]))

    flow.append(Paragraph(
        f'En los autos caratulados: "{caratula}", que tramitan por ante el {juzgado}, '
        f"se ha dispuesto dirigir a Ud. el presente oficio a fin de que se sirva:", S["just"]))

    flow.append(Paragraph("<b><u>INFORMAR:</u></b>", S["left"]))
    flow.append(Paragraph(profs_txt, S["just_ind"]))

    flow.append(Paragraph(
        "Todo ello deberá ser informado en el plazo de diez (10) días hábiles, bajo "
        "apercibimientos de ley.-", S["just"]))

    flow.append(Paragraph(
        f'Asimismo, se transcribe el siguiente decreto: <i>"{decreto}"</i>', S["just"]))

    flow.append(Paragraph(
        f'A continuación se transcribe el Art. 25 del CPCCSF: <i>{esc(ART25)}</i>', S["just"]))

    flow.append(Paragraph(
        "Se deja constancia que el Dr. Santiago A. Segovia se encuentra debidamente "
        "autorizado para el diligenciamiento del presente oficio.-", S["just"]))

    flow.append(Paragraph(
        f"La respuesta deberá remitirse al {juzgado}, Provincia de Santa Fe.-", S["just"]))

    flow.append(Paragraph("Sin otro particular, saludo a Ud. atentamente.-", S["just"]))
    flow.append(KeepTogether([
        Spacer(1, 1.2 * cm),
        Paragraph("_______________________________", S["center"]),
        Paragraph("<b>JUEZ/A</b>", S["centerb"]),
        Paragraph(juzgado, S["center"]),
    ]))
    return flow


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 generar_oficios.py datos.json [carpeta_salida]")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(outdir, exist_ok=True)

    cuij = data.get("cuij", "")
    styles = build_styles()
    generados = []
    for destinatario, prefijo in DESTINATARIOS:
        flow = build_oficio(data, destinatario, styles)
        nombre = f"{prefijo} - {cuij}.pdf" if cuij else f"{prefijo}.pdf"
        ruta = os.path.join(outdir, nombre)
        doc = SimpleDocTemplate(ruta, pagesize=letter,
                                topMargin=2.0 * cm, bottomMargin=2.0 * cm,
                                leftMargin=2.5 * cm, rightMargin=2.5 * cm)
        doc.build(flow)
        generados.append(ruta)
        print("Generado:", ruta)
    return generados


if __name__ == "__main__":
    main()
