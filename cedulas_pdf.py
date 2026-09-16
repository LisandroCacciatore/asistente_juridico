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
# Cierre del modelo del SISFE para el Art. 51: centrado y en negrita.
ESTILO_CIERRE = ParagraphStyle(
    "cierre", fontName="Helvetica-Bold", fontSize=10,
    alignment=TA_CENTER, spaceAfter=6, leading=14,
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
    """Autoridad con la redacción del modelo del SISFE (Art. 51).

    El portal escribe el cargo ENTRE PARÉNTESIS después del nombre y sin
    'Dr./Dra.' adelante:

        a cargo de SILVANA LAURA QUAGLIATTI (JUEZ/A), PEDRO DANIEL HERRERO
        (SECRETARIO / PROSECRETARIO)

    Verificado contra una cédula real del SISFE (Juzgado en lo Laboral Nº 8,
    Rosario, 07/04/2026). Las dos etiquetas son FIJAS: son parte de la
    plantilla del portal, no un dato del expediente — por eso no se usan
    cargo_juez / cargo_secretario acá. El portal tiene DOS casilleros: el juez
    y, en el segundo, el secretario o el prosecretario; por eso la etiqueta
    dice 'SECRETARIO / PROSECRETARIO' sin distinguir cuál de los dos es.

    Solo con los datos que existen: si falta un nombre, ese tramo no se
    imprime. Devuelve '' si no hay ninguno.
    """
    juez = (datos.get("juez") or "").strip().upper()
    sec = (datos.get("secretario") or "").strip().upper()
    pros = (datos.get("prosecretario") or "").strip().upper()

    partes = []
    if juez:
        partes.append(f"{juez} (JUEZ/A)")
    segundo = sec or pros
    if segundo:
        partes.append(f"{segundo} (SECRETARIO / PROSECRETARIO)")
    # Si además hay un prosecretario distinto del secretario, no se pierde: va
    # con su propio cargo. El portal tiene DOS casilleros, así que en la
    # práctica no muestra los tres nombres; acá preferimos no tirar un dato del
    # expediente a copiar la plantilla al pie de la letra.
    if sec and pros:
        partes.append(f"{pros} (PROSECRETARIO)")
    return ", ".join(partes)


# --- Cuándo se imprime el domicilio ---------------------------------------
# Regla (16/09/2026): se imprime SIEMPRE QUE LO TENGAMOS, sea persona física o
# jurídica. Antes se suprimía cuando el destinatario era una sociedad, con el
# argumento de que la notificación va por SISFE; una cédula real del portal
# mostró lo contrario: imprime el domicilio de una S.R.L. (Juzgado en lo
# Laboral Nº 8, Rosario, 07/04/2026). Y en el Art. 51 no es decorativo — ese
# artículo manda citar a las partes "en el real, además del procesal".
# Lo que sigue prohibido es inventarlo: si no está, no se imprime (mirá los
# `if domicilio and destinatario` de cada plantilla).


# --- Distrito judicial: el número que el SISFE imprime en el encabezado ----
# ("JUZGADO EN LO LABORAL Nº 8 DISTRITO JUDICIAL NRO. 2 - ROSARIO").
# OJO: distrito judicial NO es lo mismo que circunscripción, y la provincia
# numera los distritos de forma no secuencial (San Jorge es el Nº 11), así que
# acá van SOLO los números verificados:
#   - ROSARIO  = 2, leído en una cédula real del SISFE (07/04/2026).
#   - SANTA FE = 1, del Consejo de la Magistratura: "Distrito Judicial Nº 1
#     Santa Fe" (santafe.gov.ar).
# Para cualquier otra ciudad el número NO se adivina: se pasa explícito en
# datos["distrito"] y, si no está, el encabezado sale sin ese tramo.
_DISTRITOS = {"ROSARIO": "2", "SANTA FE": "1"}


def _distrito(datos):
    """Número de distrito judicial, o '' si no está verificado."""
    explicito = str(datos.get("distrito") or "").strip()
    if explicito:
        return explicito
    ciudad = str(datos.get("ciudad") or "Rosario").strip().upper()
    return _DISTRITOS.get(ciudad, "")


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

    # El destinatario y el domicilio solo se imprimen si hay dato. El domicilio
    # va también en las personas jurídicas: se imprime si lo tenemos, nunca se
    # inventa (ver la nota de arriba).
    destinatario = _esc(datos.get("destinatario_nombre", "")).upper()
    if destinatario:
        elementos.append(Paragraph(f"<b>Señor/a:</b> {destinatario}", ESTILO_CAMPO))
    domicilio = _esc(datos.get("destinatario_domicilio", ""))
    if domicilio and destinatario:
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
    """Cédula de audiencia Art. 51 CPL, con transcripción de los artículos.

    Sigue el modelo del SISFE (verificado contra una cédula real del Juzgado
    en lo Laboral Nº 8 de Rosario, del 07/04/2026):

      - Encabezado centrado: 'CÉDULA' y el tribunal como lo escribe el portal.
      - 'Señor:' con el destinatario, y el domicilio siempre que lo tengamos.
      - La autoridad con el cargo entre paréntesis y sin 'Dr./Dra.'.
      - La carátula y el CUIJ van dentro de la frase, no en líneas aparte.
      - 'Se ha dictado lo siguiente:' seguido del decreto, sin comillas.
      - Primero las transcripciones y AL FINAL el cierre, centrado y en negrita.
      - Sin bloque de firma: se firma digitalmente, como en el portal.
    """
    nom = _esc(datos.get("nominacion") or "____")
    ciudad = _esc(datos.get("ciudad", "Rosario")).upper()
    fuero = _fuero(datos)
    autoridad = _autoridad_51(datos)
    distrito = _distrito(datos)
    tribunal = f"JUZGADO {fuero} Nº {nom}"

    elementos = [
        Paragraph("CÉDULA", ESTILO_ENCABEZADO),
        Paragraph(
            tribunal + (f" DISTRITO JUDICIAL NRO. {_esc(distrito)}" if distrito else "")
            + f" - {ciudad}",
            ESTILO_ENCABEZADO,
        ),
        Spacer(1, 6),
    ]

    # El destinatario y el domicilio solo si hay dato (nunca se inventan).
    destinatario = _esc(datos.get("destinatario_nombre", "")).upper()
    if destinatario:
        elementos.append(Paragraph(f"<b>Señor:</b> {destinatario}", ESTILO_CAMPO))
    domicilio = _esc(datos.get("destinatario_domicilio", ""))
    if domicilio and destinatario:
        elementos.append(Paragraph(f"<b>Domicilio:</b> {domicilio}", ESTILO_CAMPO))
    elementos.append(Spacer(1, 10))

    caratula = _esc(datos.get("caratula", "")).upper()
    cuij = _esc(datos.get("cuij", ""))
    elementos.append(Paragraph(
        f"Hago saber a Ud. que en el juicio seguido ante el {tribunal}"
        + (f", a cargo de {_esc(autoridad)}" if autoridad else "")
        + f", dentro de los autos caratulados: &ldquo;{caratula}&rdquo;"
        + (f" {cuij}" if cuij else ""),
        ESTILO_CUERPO,
    ))

    elementos.append(Paragraph(
        f"Se ha dictado lo siguiente: {_esc(datos.get('texto_decreto', ''))}",
        ESTILO_CUERPO,
    ))

    # Transcripción de artículos, un párrafo por artículo
    for bloque in ARTICULOS_AUD_51.split("\n\n"):
        if bloque.strip():
            elementos.append(Paragraph(_esc(bloque.strip()), ESTILO_ARTICULOS))

    # El cierre va DESPUÉS de las transcripciones, corto y centrado: así lo
    # escribe el portal (nosotros antes lo poníamos antes y con el detalle de
    # los apercibimientos, que el portal no incluye).
    fecha_aud = _esc(datos.get("fecha_audiencia") or "___/___/______")
    hora_aud = _esc(datos.get("hora_audiencia") or "__:__")
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(
        f"En consecuencia queda usted debidamente notificado del decreto que antecede, "
        f"que la Audiencia de ART 51 se realizará el día {fecha_aud} a las {hora_aud} horas "
        f"y de todos los derechos que efecto hubiera lugar. Saluda Atte.-",
        ESTILO_CIERRE,
    ))

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
