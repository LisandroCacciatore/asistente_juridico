# ============================================================
#  CEDULAS_PDF.PY - Genera las cédulas directamente en PDF
# ============================================================

import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from cedulas import ARTICULOS_AUD_51


# --- Estilos: cuerpo justificado, títulos centrados ---
ESTILO_TITULO = ParagraphStyle(
    "titulo", fontName="Helvetica-Bold", fontSize=13,
    alignment=TA_CENTER, spaceAfter=8, leading=16,
)
ESTILO_ENCABEZADO = ParagraphStyle(
    "encabezado", fontName="Helvetica-Bold", fontSize=10.5,
    alignment=TA_CENTER, spaceAfter=14, leading=14,
)
ESTILO_CUERPO = ParagraphStyle(
    "cuerpo", fontName="Helvetica", fontSize=10,
    alignment=TA_JUSTIFY, spaceAfter=10, leading=14,
)
ESTILO_CAMPO = ParagraphStyle(
    "campo", fontName="Helvetica", fontSize=10,
    alignment=TA_LEFT, spaceAfter=3, leading=13,
)
ESTILO_ARTICULOS = ParagraphStyle(
    "articulos", fontName="Helvetica", fontSize=8,
    alignment=TA_JUSTIFY, spaceAfter=6, leading=10,
)
ESTILO_FIRMA = ParagraphStyle(
    "firma", fontName="Helvetica", fontSize=10,
    alignment=TA_CENTER, spaceAfter=2, leading=13,
)


def _esc(texto):
    """Escapa caracteres que reportlab interpreta como markup."""
    if texto is None:
        return ""
    return (str(texto).replace("&", "&amp;")
                      .replace("<", "&lt;")
                      .replace(">", "&gt;"))


def _doc(ruta):
    return SimpleDocTemplate(
        ruta, pagesize=A4,
        leftMargin=3 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title="Cédula", author="Estudio Jurídico Segovia",
    )


# --- Fuero: el encabezado dice "en lo laboral/civil/comercial/contractual" ---
FUEROS = {
    "LABORAL": "EN LO LABORAL",
    "CIVIL": "EN LO CIVIL",
    "COMERCIAL": "EN LO COMERCIAL",
    "CONTRACTUAL": "EN LO CONTRACTUAL",
    "FAMILIA": "EN LO FAMILIAR",
}


def _fuero(datos):
    """'EN LO LABORAL' / 'EN LO CIVIL' / … para el encabezado.

    Antes estaba escrito a mano "EN LO LABORAL" en la plantilla, así que una
    cédula de Civil o Comercial salía con el fuero equivocado.
    """
    f = (datos.get("fuero") or "LABORAL").strip().upper()
    return FUEROS.get(f, f"EN LO {f}")


def _fuero_simple(datos):
    """Igual que _fuero pero pelado, para 'JUZGADO LABORAL DE LA …'."""
    f = (datos.get("fuero") or "LABORAL").strip().upper()
    return "FAMILIA" if f in ("FAMILIA", "FAMILIAR") else f


def _autoridad(datos, prefijo="del/la"):
    """Arma '{prefijo} DR./DRA. {juez} ({cargo}), {cargo} DR./DRA. {sec}…'.

    Solo con los datos que existen: si falta un nombre, esa parte no se
    imprime — nunca sale '____' ni 'None'. Incluye el prosecretario cuando
    está. Devuelve '' si no hay ninguno de los tres.
    """
    juez = (datos.get("juez") or "").strip().upper()
    sec = (datos.get("secretario") or "").strip().upper()
    pros = (datos.get("prosecretario") or "").strip().upper()
    cargo_j = (datos.get("cargo_juez") or "JUEZ").strip()
    cargo_s = (datos.get("cargo_secretario") or "SECRETARIO").strip()
    cargo_p = (datos.get("cargo_prosecretario") or "PROSECRETARIO").strip()

    if juez and sec:
        txt = f"{prefijo} DR./DRA. {juez} ({cargo_j}), {cargo_s} DR./DRA. {sec}"
    elif juez:
        txt = f"{prefijo} DR./DRA. {juez} ({cargo_j})"
    elif sec:
        txt = f"{prefijo} {cargo_s} DR./DRA. {sec}"
    else:
        return ""
    if pros:
        txt += f", {cargo_p} DR./DRA. {pros}"
    return txt


def _autoridad_51(datos):
    """Igual que _autoridad pero con la redacción propia del Art. 51.

    Esa cédula dice 'a cargo de la/el DRA./DR. …' — se mantiene tal cual.
    """
    juez = (datos.get("juez") or "").strip().upper()
    sec = (datos.get("secretario") or "").strip().upper()
    pros = (datos.get("prosecretario") or "").strip().upper()
    cargo_j = (datos.get("cargo_juez") or "JUEZ").strip()
    cargo_s = (datos.get("cargo_secretario") or "SECRETARIO").strip()
    cargo_p = (datos.get("cargo_prosecretario") or "PROSECRETARIO").strip()

    if juez and sec:
        txt = f"la/el DRA./DR. {juez} ({cargo_j}), {cargo_s} de la/el DRA./DR. {sec}"
    elif juez:
        txt = f"la/el DRA./DR. {juez} ({cargo_j})"
    elif sec:
        txt = f"la/el DRA./DR. {sec} ({cargo_s})"
    else:
        return ""
    if pros:
        txt += f", {cargo_p} de la/el DRA./DR. {pros}"
    return txt


# Personas jurídicas: la notificación va por SISFE, así que el domicilio no
# se imprime. Se puede forzar con datos["destinatario_es_juridica"].
_JURIDICA = re.compile(
    r"\b(S\.?A\.?|S\.?R\.?L\.?|S\.?A\.?S\.?|LTDA\.?|SOCIEDAD|EMPRESA|COOPERATIVA|"
    r"MUTUAL|ASEGURADORA|ART|CAJA|BANCO|MUNICIPALIDAD|COMUNA|PROVINCIA|FISCO|"
    r"OBRA SOCIAL|INSTITUTO|FUNDACION|FUNDACIÓN|ASOCIACION|ASOCIACIÓN)\b",
    re.I,
)


def _es_juridica(datos):
    """True si el destinatario es persona jurídica (o si se fuerza el flag)."""
    if "destinatario_es_juridica" in datos:
        return bool(datos["destinatario_es_juridica"])
    return bool(_JURIDICA.search(datos.get("destinatario_nombre") or ""))


def _bloque_firma():
    return [
        Spacer(1, 24),
        Paragraph("_______________________________", ESTILO_FIRMA),
        Paragraph("Firma y sello", ESTILO_FIRMA),
    ]


def generar_pdf_estandar(datos, ruta):
    """Cédula estándar (modelo Racca/Arriola) en PDF."""
    nom = _esc(datos.get("nominacion") or "____")
    ciudad = _esc(datos.get("ciudad", "Rosario")).upper()
    autoridad = _autoridad(datos)

    elementos = [
        Paragraph("CÉDULA", ESTILO_TITULO),
        Paragraph(
            f"JUZGADO DE PRIMERA INSTANCIA DE DISTRITO {_fuero(datos)} "
            f"DE LA {nom} NOMINACIÓN DE {ciudad}",
            ESTILO_ENCABEZADO,
        ),
    ]

    # El destinatario y el domicilio solo se imprimen si hay dato. En las
    # personas jurídicas el domicilio no va: la notificación sale por SISFE.
    destinatario = _esc(datos.get("destinatario_nombre", "")).upper()
    if destinatario:
        elementos.append(Paragraph(f"<b>Señor/a:</b> {destinatario}", ESTILO_CAMPO))
    domicilio = _esc(datos.get("destinatario_domicilio", ""))
    if domicilio and destinatario and not _es_juridica(datos):
        elementos.append(Paragraph(f"<b>Domicilio:</b> {domicilio}", ESTILO_CAMPO))

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(
            f"Hago saber a Ud. que en el juicio seguido ante el JUZGADO "
            f"{_fuero_simple(datos)} DE LA "
            f"{nom} NOMINACIÓN DE LA CIUDAD DE {ciudad}"
            + (f", a cargo {autoridad}" if autoridad else "")
            + f", dentro de los autos caratulados: "
            f"&ldquo;{_esc(datos.get('caratula',''))}&rdquo; CUIJ {_esc(datos.get('cuij',''))} "
            f"se ha dictado lo siguiente: {ciudad}, {_esc(datos.get('fecha_decreto',''))} "
            f"{_esc(datos.get('texto_decreto',''))}",
            ESTILO_CUERPO,
        ))
    elementos.append(Spacer(1, 8))
    elementos.append(Paragraph(
        "<b>En consecuencia queda usted debidamente notificado/a del decreto que antecede.</b>",
        ESTILO_CUERPO,
    ))
    elementos += _bloque_firma()
    _doc(ruta).build(elementos)
    return ruta


def generar_pdf_audiencia_51(datos, ruta):
    """Cédula de audiencia Art. 51 CPL con transcripción de artículos, en PDF."""
    nom = _esc(datos.get("nominacion") or "____")
    ciudad = _esc(datos.get("ciudad", "Rosario"))
    autoridad = _autoridad_51(datos)
    fecha_aud = _esc(datos.get("fecha_audiencia") or "___/___/______")
    hora_aud = _esc(datos.get("hora_audiencia") or "__:__ hs.")

    cabecera = [
        Paragraph(f"JUZGADO DEL TRABAJO {nom}ª NOMINACIÓN &nbsp;&nbsp;&nbsp; CÉDULA JUDICIAL", ESTILO_ENCABEZADO),
        Paragraph(f"{ciudad}, {_esc(datos.get('fecha_decreto',''))}.-", ESTILO_CAMPO),
        Spacer(1, 6),
    ]
    destinatario = _esc(datos.get("destinatario_nombre", "")).upper()
    if destinatario:
        cabecera.append(Paragraph(f"<b>SEÑOR/A:</b> {destinatario}.-", ESTILO_CAMPO))
    domicilio = _esc(datos.get("destinatario_domicilio", ""))
    if domicilio and destinatario and not _es_juridica(datos):
        cabecera.append(Paragraph(f"<b>DOMICILIO:</b> {domicilio}.-", ESTILO_CAMPO))
    cabecera.append(Spacer(1, 10))

    elementos = cabecera + [
        Paragraph(
            f"Hago saber a Ud. que en el juicio seguido por ante el Juzgado del Trabajo de la "
            f"{nom}ª Nominación de la ciudad de {ciudad}"
            + (f", a cargo de {autoridad}." if autoridad else "."),
            ESTILO_CUERPO,
        ),
        Paragraph(f"<b>Por:</b> {_esc(datos.get('actor') or '________________')}.", ESTILO_CAMPO),
        Paragraph(f"<b>Contra:</b> {_esc(datos.get('demandado') or '________________')}.", ESTILO_CAMPO),
        Paragraph(f"<b>Sobre:</b> {_esc(datos.get('objeto') or 'ACCIDENTES DEL TRABAJO')}.", ESTILO_CAMPO),
        Paragraph(f"<b>Expte. N°:</b> {_esc(datos.get('cuij',''))}.", ESTILO_CAMPO),
        Spacer(1, 8),
        Paragraph("Se ha dictado lo siguiente:", ESTILO_CAMPO),
        Paragraph(f"&ldquo;{_esc(datos.get('texto_decreto',''))}&rdquo;.-", ESTILO_CUERPO),
        Spacer(1, 6),
        Paragraph(
            f"En consecuencia queda Ud. debidamente notificado/a del/os decreto/s que antecede/n, "
            f"por el/los cual/es se le hace saber que el día {fecha_aud} a las {hora_aud} se celebrará "
            f"la audiencia a los fines del Art. 51 CPL (Ley 7945 modif. por Ley 13.039), es decir, para "
            f"conciliación, reconocimiento de la documental, absolución de posiciones y exhibición de los "
            f"recaudos legales intimados en la demanda, a la que la demandada deberá comparecer muñida de "
            f"su Documento Nacional de Identidad y de los instrumentos que acrediten la representación que "
            f"inviste para ABSOLVER POSICIONES y RECONOCER DOCUMENTAL, todo bajo los apercibimientos de que "
            f"si faltare sin justa causa previa y debidamente acreditada será tenido por confeso de los "
            f"hechos expuestos en la demanda y por reconocidos los documentos detallados en la misma "
            f"(art. 66 y 71 Ley 7945). Asimismo, se lo intima para que en la referida audiencia del Art. 51 "
            f"CPL presente DOCUMENTAL INTIMATIVA detallada en la demanda; todo ello bajo los apercibimientos "
            f"contenidos en los arts. 51, 52 y 66 CPL.-",
            ESTILO_CUERPO,
        ),
        Spacer(1, 8),
    ]

    # Transcripción de artículos, un párrafo por artículo
    for bloque in ARTICULOS_AUD_51.split("\n\n"):
        if bloque.strip():
            elementos.append(Paragraph(_esc(bloque.strip()), ESTILO_ARTICULOS))

    elementos.append(Spacer(1, 8))
    elementos.append(Paragraph("Sin más, lo saludo atte.-", ESTILO_CUERPO))
    elementos += _bloque_firma()

    _doc(ruta).build(elementos)
    return ruta


def generar_pdf_bus_federal(datos, ruta):
    """
    Cédula Bus Federal (Ley 22.172) para notificar fuera de Santa Fe.
    El destinatario y el domicilio quedan en blanco para completar a mano.
    """
    nom = _esc(datos.get("nominacion") or "____")
    ciudad = _esc(datos.get("ciudad", "Rosario")).upper()
    autoridad = _autoridad(datos, prefijo="la/el")

    dest = _esc(datos.get("destinatario_nombre", "")).upper()
    dom = _esc(datos.get("destinatario_domicilio", ""))
    linea = "_" * 60

    elementos = [
        Paragraph(
            f"JUZGADO DE PRIMERA INSTANCIA DE DISTRITO {_fuero(datos)}<br/>"
            f"{nom}ª NOMINACIÓN DE {ciudad}<br/>PROVINCIA DE SANTA FE",
            ESTILO_ENCABEZADO,
        ),
        Paragraph("C É D U L A", ESTILO_TITULO),
        Spacer(1, 6),
        Paragraph(f"<b>EXPTE. N°:</b> {_esc(datos.get('cuij',''))}", ESTILO_CAMPO),
        Paragraph(f"<b>Caratulado:</b> &ldquo;{_esc(datos.get('caratula',''))}&rdquo;", ESTILO_CAMPO),
        Spacer(1, 10),
        Paragraph(f"<b>Señor/es:</b> {dest or linea}", ESTILO_CAMPO),
        Paragraph(linea, ESTILO_CAMPO),
        Paragraph(linea, ESTILO_CAMPO),
        Paragraph(f"<b>Domicilio:</b> {dom or linea}", ESTILO_CAMPO),
        Spacer(1, 12),
        Paragraph(
            f"En el juicio seguido ante el JUZGADO {_fuero_simple(datos)} DE LA {nom}ª NOMINACIÓN DE LA CIUDAD DE "
            f"{ciudad}"
            + (f", a cargo de {autoridad}" if autoridad else "")
            + f", dentro de los autos caratulados: &ldquo;{_esc(datos.get('caratula',''))}&rdquo;, "
            f"CUIJ {_esc(datos.get('cuij',''))}, se ha dictado el siguiente decreto:",
            ESTILO_CUERPO,
        ),
        Spacer(1, 6),
        Paragraph(f"<b>{ciudad}, {_esc(datos.get('fecha_decreto',''))}:</b>", ESTILO_CAMPO),
        Paragraph(f"&ldquo;{_esc(datos.get('texto_decreto',''))}&rdquo;", ESTILO_CUERPO),
        Spacer(1, 10),
        Paragraph(
            "<b>En consecuencia queda usted debidamente notificado del decreto que antecede.</b>",
            ESTILO_CUERPO,
        ),
    ]
    elementos += _bloque_firma()
    _doc(ruta).build(elementos)
    return ruta


def _limpiar_nombre(texto, largo=28):
    """Limpia un texto para usarlo en un nombre de archivo de Windows."""
    if not texto:
        return ""
    t = re.sub(r'[<>:"/\\|?*,]', "", str(texto))
    t = re.sub(r'\s+', "_", t.strip())
    return t[:largo].strip("_")


def guardar_cedula_pdf(datos, ruta_carpeta, es_aud51=False, fecha_archivo="", novedad="", es_bus_federal=False):
    """Construye un nombre de archivo único y genera el PDF."""
    os.makedirs(ruta_carpeta, exist_ok=True)
    fecha = (fecha_archivo or datos.get("fecha_decreto") or "").replace("/", "-").replace(" ", "_")
    dest = _limpiar_nombre(datos.get("destinatario_nombre") or "COMPLETAR", 28)
    nov = _limpiar_nombre(novedad, 24)

    partes = ["cedula"]
    if es_bus_federal:
        partes.append("BUSFEDERAL")
    partes.append(fecha)
    if nov:
        partes.append(nov)
    partes.append(dest)
    base = "_".join(p for p in partes if p)

    ruta = os.path.join(ruta_carpeta, f"{base}.pdf")

    # Si ya existe un archivo con ese nombre, agregar sufijo numérico
    n = 2
    while os.path.exists(ruta):
        ruta = os.path.join(ruta_carpeta, f"{base}_{n}.pdf")
        n += 1

    if es_bus_federal:
        return generar_pdf_bus_federal(datos, ruta)
    if es_aud51:
        return generar_pdf_audiencia_51(datos, ruta)
    return generar_pdf_estandar(datos, ruta)
