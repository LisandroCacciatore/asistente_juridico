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

from cedulas import ARTICULOS_AUD_51, ARTICULOS_PERITOS, PERITOS_INTIMACION


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
# Cierre de la cédula: en negrita y alineado a la izquierda, como en las
# cédulas reales del SISFE (la común, la de peritos y la del Art. 51).
ESTILO_CIERRE = ParagraphStyle(
    "cierre", fontName="Helvetica-Bold", fontSize=10,
    alignment=TA_LEFT, spaceBefore=6, spaceAfter=6, leading=14,
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


# --- Cómo se nombra el juzgado --------------------------------------------
# Los juzgados no se nombran todos igual: el SISFE copia el nombre que cada uno
# tiene cargado. Sobre cédulas reales aparecen dos formas:
#
#   'JUZGADO DE PRIMERA INSTANCIA DE DISTRITO EN LO LABORAL DE LA 5
#    NOMINACIÓN DE ROSARIO'   — la 5ª/10ª Nom. de Rosario y Reconquista
#   'JUZGADO EN LO LABORAL Nº 8 DISTRITO JUDICIAL NRO. 2 - ROSARIO'
#                             — el Juzgado Laboral Nº 8 (la forma vieja)
#
# Por eso: si el expediente trae el nombre cargado (datos["juzgado_header"]) se
# usa TAL CUAL, y si no se compone la primera forma, que es la del común.
# El 'DISTRITO JUDICIAL NRO. N' NO se deduce de la ciudad: distrito judicial no
# es la circunscripción y la provincia los numera sin orden (San Jorge es el
# Nº 11). Cuando un juzgado use esa forma, el nombre viene en el dato.
def _juzgado_encabezado(datos):
    """Nombre del juzgado para el encabezado, en mayúsculas."""
    propio = str(datos.get("juzgado_header") or "").strip()
    if propio:
        return _esc(propio).upper()
    nom = str(datos.get("nominacion") or "").strip()
    ciudad = _esc(datos.get("ciudad", "Rosario")).upper()
    # Reconquista tiene un solo juzgado del trabajo y no se numera: el portal
    # escribe 'DE LA LOCALIDAD DE RECONQUISTA' (verificado en una cédula real).
    cuerpo = f"LA {nom} NOMINACIÓN DE {ciudad}" if nom else f"LA LOCALIDAD DE {ciudad}"
    return f"JUZGADO DE PRIMERA INSTANCIA DE DISTRITO {_fuero(datos)} DE {cuerpo}"


def _juzgado_cuerpo(datos):
    """Igual, pero como se lo nombra dentro de la frase ('... ante el ...')."""
    propio = str(datos.get("juzgado_header") or "").strip()
    if propio:
        return _esc(propio).upper()
    nom = str(datos.get("nominacion") or "").strip()
    ciudad = _esc(datos.get("ciudad", "Rosario")).upper()
    cuerpo = (f"LA {nom} NOMINACIÓN DE LA CIUDAD DE {ciudad}" if nom
              else f"LA LOCALIDAD DE {ciudad}")
    return f"JUZGADO {_fuero_simple(datos)} DE {cuerpo}"


# --- Cuándo se imprime el domicilio ---------------------------------------
# Regla (16/09/2026): se imprime SIEMPRE QUE LO TENGAMOS, sea persona física o
# jurídica. Antes se suprimía cuando el destinatario era una sociedad, con el
# argumento de que la notificación va por SISFE; una cédula real del portal
# mostró lo contrario: imprime el domicilio de una S.R.L. (Juzgado en lo
# Laboral Nº 8, Rosario, 07/04/2026). Y en el Art. 51 no es decorativo — ese
# artículo manda citar a las partes "en el real, además del procesal".
# Lo que sigue prohibido es inventarlo: si no está, no se imprime.


def _decreto_con_fecha(datos):
    """El texto del decreto tal como va en la cédula.

    En las cédulas reales el decreto arranca con su propia fecha ('Rosario, 10
    de Septiembre de 2025- Por presentado…'), porque así se copia del SISFE.
    Si el texto pegado ya la trae, no se le agrega nada (si no, saldría dos
    veces); si no la trae, se le adelanta ciudad y fecha para que la cédula no
    salga sin fecha.
    """
    texto = (datos.get("texto_decreto") or "").strip()
    fecha = _esc(datos.get("fecha_decreto", ""))
    if not fecha or re.match(r"^[A-Za-zÁÉÍÓÚÑáéíóúñ\.\s]{3,40},\s*\d", texto):
        return texto
    return f"{_esc(datos.get('ciudad', 'Rosario')).upper()}, {fecha} {texto}"


def _cuerpo_comun(datos):
    """Lo que comparten TODAS las cédulas.

    La común, la de audiencia del Art. 51 y la de peritos son el MISMO
    documento: las otras dos son la común más un bloque de transcripciones (lo
    definió Santiago el 16/09/2026, y se ve en las cédulas reales del SISFE).
    Acá se arma una sola vez lo que no cambia: el encabezado, el destinatario,
    el domicilio y la frase del 'Hago saber' con la carátula y el CUIJ adentro.
    """
    autoridad = _autoridad(datos)

    elementos = [
        Paragraph("CÉDULA", ESTILO_TITULO),
        Paragraph(_juzgado_encabezado(datos), ESTILO_ENCABEZADO),
    ]

    # El destinatario y el domicilio solo si hay dato: nunca se inventan.
    destinatario = _esc(datos.get("destinatario_nombre", "")).upper()
    if destinatario:
        elementos.append(Paragraph(f"<b>Señor:</b> {destinatario}", ESTILO_CAMPO))
    domicilio = _esc(datos.get("destinatario_domicilio", ""))
    if domicilio and destinatario:
        elementos.append(Paragraph(f"<b>Domicilio:</b> {domicilio}", ESTILO_CAMPO))

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(
        f"Hago saber a Ud. que en el juicio seguido ante el {_juzgado_cuerpo(datos)}"
        + (f", a cargo {autoridad}" if autoridad else "")
        + f", dentro de los autos caratulados: "
        f"&ldquo;{_esc(datos.get('caratula',''))}&rdquo; CUIJ {_esc(datos.get('cuij',''))} "
        f"se ha dictado lo siguiente: {_decreto_con_fecha(datos)}",
        ESTILO_CUERPO,
    ))
    return elementos


def _cierre_comun():
    """El cierre: una sola frase, en negrita.

    Las tres cédulas reales cierran así. Antes cerrábamos con 'notificado/a' y
    un bloque de 'Firma y sello' que ninguna de las tres trae: la cédula se
    firma digitalmente y el sello lo pone FirmAr.
    """
    return Paragraph(
        "<b>En consecuencia queda usted debidamente notificado del decreto que antecede.</b>",
        ESTILO_CIERRE,
    )


def _transcripcion(texto):
    """Los artículos, un párrafo por artículo."""
    bloques = []
    for bloque in texto.split("\n\n"):
        if bloque.strip():
            bloques.append(Paragraph(_esc(bloque.strip()), ESTILO_ARTICULOS))
    return bloques


def generar_pdf_estandar(datos, ruta):
    """La cédula común: la base de todas las demás.

    Verificada contra cédulas reales del SISFE (una contestación de demanda y
    una designación de perito). Las otras cédulas son ésta más un bloque de
    transcripciones — ver generar_pdf_peritos y generar_pdf_audiencia_51.
    """
    elementos = _cuerpo_comun(datos)
    elementos.append(_cierre_comun())
    _doc(ruta).build(elementos)
    return ruta


def generar_pdf_peritos(datos, ruta):
    """Cédula al perito designado: la común + los arts. 78 y 79 del CPL.

    Verificada contra una cédula real del SISFE (Juzgado de Primera Instancia
    de Distrito en lo Laboral de la Localidad de Reconquista). El decreto que
    se notifica es el acta del sorteo; lo que agrega la cédula es la intimación
    a aceptar el cargo y la transcripción de los dos artículos.
    """
    elementos = _cuerpo_comun(datos)
    elementos.append(Paragraph(_esc(PERITOS_INTIMACION), ESTILO_CUERPO))
    elementos += _transcripcion(ARTICULOS_PERITOS)
    elementos.append(_cierre_comun())
    _doc(ruta).build(elementos)
    return ruta


def generar_pdf_audiencia_51(datos, ruta):
    """Cédula que notifica la audiencia del Art. 51: la común + los arts. 51, 52 y 66.

    Verificada contra una cédula real del SISFE (Juzgado en lo Laboral Nº 8 de
    Rosario, 07/04/2026). Santiago definió el 16/09/2026 que esta cédula es la
    común más la transcripción de los artículos — no un documento aparte.

    Dos cosas que el portal hace distinto según el juzgado que la emite, y que
    acá NO se copiaron: nombra al tribunal de otra forma ('JUZGADO EN LO
    LABORAL Nº 8 DISTRITO JUDICIAL NRO. 2 - ROSARIO') y redacta la autoridad
    con las etiquetas 'JUEZ/A' y 'SECRETARIO / PROSECRETARIO'. Se usa la forma
    del común; si algún juzgado necesita la otra, va en datos["juzgado_header"].
    """
    elementos = _cuerpo_comun(datos)
    elementos += _transcripcion(ARTICULOS_AUD_51)
    elementos.append(_cierre_comun())
    _doc(ruta).build(elementos)
    return ruta


def _bloque_firma():
    """Bloque de firma para la Bus Federal (Ley 22.172), y solo para esa.

    Es la única cédula que se diligencia a mano: la firma el oficial
    notificador y la sella el tribunal receptor, así que necesita el espacio
    impreso. Las otras tres (común, peritos y Art. 51) NO lo llevan — ninguna
    de las cédulas reales del SISFE lo trae, porque se firman digitalmente.
    """
    return [
        Spacer(1, 24),
        Paragraph("_______________________________", ESTILO_FIRMA),
        Paragraph("Firma y sello", ESTILO_FIRMA),
    ]


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


def guardar_cedula_pdf(datos, ruta_carpeta, es_aud51=False, fecha_archivo="", novedad="", es_bus_federal=False, es_peritos=False):
    """Construye un nombre de archivo único y genera el PDF."""
    os.makedirs(ruta_carpeta, exist_ok=True)
    fecha = (fecha_archivo or datos.get("fecha_decreto") or "").replace("/", "-").replace(" ", "_")
    dest = _limpiar_nombre(datos.get("destinatario_nombre") or "COMPLETAR", 28)
    nov = _limpiar_nombre(novedad, 24)

    partes = ["cedula"]
    if es_bus_federal:
        partes.append("BUSFEDERAL")
    if es_peritos:
        partes.append("PERITO")
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
    if es_peritos:
        return generar_pdf_peritos(datos, ruta)
    if es_aud51:
        return generar_pdf_audiencia_51(datos, ruta)
    return generar_pdf_estandar(datos, ruta)
