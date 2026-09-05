# ============================================================
#  GENERAR_TRANSFERENCIA.PY
#  Un solo PDF de escritos: OFICIO (pág. 1) + MANIFIESTA/SOLICITA (pág. 2),
#  nunca mezclados. Si se pasan PDFs adjuntos (informe, constancia) también
#  arma un _COMPLETO.pdf = escritos + adjuntos.
#  Uso: python3 generar_transferencia.py datos.json CARPETA_SALIDA [pdf1 pdf2 ...]
#  Formato: cuerpo justificado; "OFICIO" centrado; "MANIFIESTA/SOLICITA" a la derecha.
# ============================================================
import os, re, sys, json
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

ESTILO_TITULO = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=12,
    alignment=TA_CENTER, spaceAfter=4, leading=15)
ESTILO_TITULO_DER = ParagraphStyle("titulo_der", fontName="Helvetica-Bold", fontSize=11,
    alignment=TA_RIGHT, spaceAfter=2, leading=14)
ESTILO_CAMPO = ParagraphStyle("campo", fontName="Helvetica", fontSize=11,
    alignment=TA_LEFT, spaceAfter=3, leading=15)
ESTILO_CUERPO = ParagraphStyle("cuerpo", fontName="Helvetica", fontSize=11,
    alignment=TA_JUSTIFY, spaceAfter=12, leading=17, firstLineIndent=0)
ESTILO_CUERPO_SANGRIA = ParagraphStyle("cuerpo_sangria", fontName="Helvetica", fontSize=11,
    alignment=TA_JUSTIFY, spaceAfter=12, leading=17, firstLineIndent=1.2 * cm)

def _esc(texto):
    if texto is None:
        return ""
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def _doc(ruta):
    return SimpleDocTemplate(ruta, pagesize=A4,
        leftMargin=3 * cm, rightMargin=2.5 * cm, topMargin=2.5 * cm, bottomMargin=2.5 * cm,
        title="Transferencia de capital", author="Estudio Jurídico Segovia")

def _trato(cargo):
    c = (cargo or "").strip().upper()
    fem = c.endswith("A") or c.endswith("A (S)") or "JUEZA" in c or "SECRETARIA" in c
    return ("de la", "Dra.") if fem else ("del", "Dr.")

def _banco_origen(d):
    return _esc(d.get("banco_origen_nombre", "Banco Municipal de Rosario"))

def _sucursal_origen(d):
    return _esc(d.get("sucursal_origen_desc", "Sucursal N&deg; 80 &ndash; Caja de Abogados"))

def _juzgado_desc(d):
    jd = d.get("juzgado_desc")
    if jd:
        return _esc(jd)
    nom = _esc(d.get("nominacion") or "____")
    ciudad = _esc(d.get("ciudad", "Rosario"))
    return f"Juzgado de Primera Instancia en lo Laboral de la {nom} Nominación de {ciudad}"

def _bloque_transferencia(d):
    cuil = _esc(d.get("cuil", ""))
    frag_cuil = f", CUIL N&deg; {cuil}" if cuil else ""
    return (
        f"la suma de Pesos {_esc(d.get('monto_letras',''))} "
        f"(${_esc(d.get('monto_num',''))},00.-), que se encuentra depositada en la "
        f"Cuenta Judicial N&ordm; {_esc(d.get('cuenta_judicial',''))}, "
        f"CBU: {_esc(d.get('cbu_origen',''))}, del {_banco_origen(d)} "
        f"({_sucursal_origen(d)}) "
        f"a la Cuenta {_esc(d.get('tipo_cuenta_destino','Caja de ahorro'))} "
        f"N&deg; {_esc(d.get('cuenta_destino',''))} "
        f"CBU {_esc(d.get('cbu_destino',''))}, del Banco {_esc(d.get('banco_destino',''))}, "
        f"a favor de la parte actora, {_esc(d.get('titular',''))}, "
        f"titular del DNI N&ordm; {_esc(d.get('dni',''))}{frag_cuil}, "
        f"en concepto de {_esc(d.get('concepto','capital'))}."
    )

def _ref_autos(d):
    cuij = _esc(d.get("cuij", ""))
    expte = d.get("expte_interno")
    if expte:
        return f"EXPTE N&ordm; {_esc(expte)} - CUIJ {cuij}"
    if d.get("omitir_expte"):
        return f"CUIJ {cuij}"
    return f"EXPTE N&ordm; ____________ - CUIJ {cuij}"

def elementos_oficio(d):
    ciudad = _esc(d.get("ciudad", "Rosario"))
    dia = _esc(d.get("fecha_dia", "")) or "____"
    mes = _esc(d.get("fecha_mes", "")); anio = _esc(d.get("fecha_anio", ""))
    cargo_j = _esc(d.get("cargo_juez", "JUEZ")); cargo_s = _esc(d.get("cargo_secretario", "SECRETARIO"))
    juez = _esc(d.get("juez") or "________________"); sec = _esc(d.get("secretario") or "________________")
    tomo = _esc(d.get("abogado_matricula_tomo", "LV")); folio = _esc(d.get("abogado_matricula_folio", "029"))
    apellido_abog = _esc(d.get("abogado_apellido", "Segovia"))
    art_j, trato_j = _trato(d.get("cargo_juez", "JUEZ"))
    art_s, trato_s = _trato(d.get("cargo_secretario", "SECRETARIO"))
    banco_dest = _esc(d.get("banco_origen_nombre", "Banco Municipal de Rosario")).upper()
    suc_linea = _esc(d.get("sucursal_origen_linea", d.get("sucursal_origen_desc", "Sucursal 80 &ndash; Caja de Abogados")))
    return [
        Paragraph("OFICIO", ESTILO_TITULO),
        Spacer(1, 10),
        Paragraph(f"N&ordm; ..............&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                  f"&nbsp;&nbsp;&nbsp;{ciudad}, {dia} de {mes} de {anio}", ESTILO_CAMPO),
        Spacer(1, 14),
        Paragraph("Señores", ESTILO_CAMPO),
        Paragraph(f"<b>{banco_dest}</b>", ESTILO_CAMPO),
        Paragraph(suc_linea, ESTILO_CAMPO),
        Paragraph("<b>Presente</b>", ESTILO_CAMPO),
        Spacer(1, 14),
        Paragraph(
            f"En los autos caratulados &ldquo;{_esc(d.get('caratula',''))}&rdquo; "
            f"{_ref_autos(d)}, que tramitan por ante este {_juzgado_desc(d)}, a cargo {art_j} "
            f"{cargo_j} {trato_j} {juez}, Secretaría {art_s} {cargo_s} {trato_s} {sec}, se ha "
            f"dispuesto dirigir a Usted el presente a efectos de que sirva TRANSFERIR, "
            + _bloque_transferencia(d), ESTILO_CUERPO),
        Spacer(1, 6),
        Paragraph("Salúdale a Ud. Atentamente.-", ESTILO_CUERPO),
        Spacer(1, 30),
        Paragraph(
            f"Se hace saber que el Dr. {apellido_abog} abogado, Matrícula L&ordm; {tomo}, "
            f"F&ordm; {folio} se encuentra debidamente habilitado para el diligenciamiento "
            f"del presente Oficio.-", ESTILO_CUERPO),
    ]

def elementos_escrito(d):
    abogado = _esc(d.get("abogado", "SANTIAGO A. SEGOVIA"))
    return [
        Paragraph("MANIFIESTA", ESTILO_TITULO_DER),
        Paragraph("SOLICITA", ESTILO_TITULO_DER),
        Spacer(1, 14),
        Paragraph("<b>Sr. Juez:</b>", ESTILO_CAMPO),
        Spacer(1, 6),
        Paragraph(
            f"{abogado}, abogado por la parte actora, en la representación acreditada dentro "
            f"de los autos caratulados: &ldquo;{_esc(d.get('caratula',''))} "
            f"{_esc(d.get('cuij',''))}&rdquo;, ante V.S. me presento y digo:",
            ESTILO_CUERPO_SANGRIA),
        Paragraph("<b>MANIFIESTA:</b>", ESTILO_CAMPO),
        Spacer(1, 4),
        Paragraph("I.- Que vengo por intermedio de la presente a solicitar se TRANSFIERA, "
            + _bloque_transferencia(d), ESTILO_CUERPO),
        Paragraph("<b>SOLICITA:</b>", ESTILO_CAMPO),
        Spacer(1, 4),
        Paragraph("II.- Conforme lo expuesto en el Punto I, solicito a V.S. se libre oficio de pago "
            "de capital.", ESTILO_CUERPO),
        Spacer(1, 10),
        Paragraph("Proveer de conformidad,", ESTILO_CUERPO),
        Paragraph("<b>Y SERA JUSTICIA.</b>", ESTILO_CAMPO),
    ]

def generar_pdf(d, ruta):
    elementos = elementos_oficio(d) + [PageBreak()] + elementos_escrito(d)
    _doc(ruta).build(elementos)
    return ruta

def _merge(pdfs, ruta):
    from pypdf import PdfWriter
    w = PdfWriter()
    for f in pdfs:
        w.append(f)
    with open(ruta, "wb") as fh:
        w.write(fh)
    return ruta

def _apellido(caratula):
    m = re.match(r'^\s*([A-Za-zÁÉÍÓÚÑáéíóúñ]+)', caratula or "")
    return m.group(1).upper() if m else "ACTOR"

def _nombre_archivo(prefijo, d):
    apellido = _apellido(d.get("caratula", ""))
    cuij = re.sub(r'[^0-9-]', '', d.get("cuij", "")) or "SINCUIJ"
    return f"{prefijo}_{apellido}_{cuij}.pdf"

def main():
    if len(sys.argv) < 3:
        print("Uso: python3 generar_transferencia.py datos.json CARPETA_SALIDA "
              "[informe.pdf constancia.pdf ...]"); sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)
    carpeta = sys.argv[2]; os.makedirs(carpeta, exist_ok=True)
    extras = sys.argv[3:]
    ruta = os.path.join(carpeta, _nombre_archivo("TRANSFERENCIA", d))
    generar_pdf(d, ruta)
    print("Generado (escritos):\n ", ruta)
    if extras:
        completo = os.path.join(carpeta, _nombre_archivo("TRANSFERENCIA", d).replace(".pdf", "_COMPLETO.pdf"))
        _merge([ruta] + extras, completo)
        print("Generado (completo):\n ", completo)

if __name__ == "__main__":
    main()
