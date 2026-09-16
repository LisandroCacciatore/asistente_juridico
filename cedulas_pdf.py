# ============================================================
#  CEDULAS_PDF.PY - Genera las cédulas directamente en PDF
# ============================================================

import os
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)

from cedulas import (
    ARTICULOS_AUD_51, ARTICULOS_PERITOS, PERITOS_INTIMACION,
    BUSFEDERAL_CIERRE, BUSFEDERAL_COMO_ACCEDER, BUSFEDERAL_PIE,
    BUSFEDERAL_TRIBUNAL_RECEPTOR,
)


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

# --- Estilos de la Bus Federal: es un formulario, con etiquetas y renglones ---
ESTILO_ROTULO_BUS = ParagraphStyle(
    "rotulobus", fontName="Helvetica-Bold", fontSize=10.5,
    alignment=TA_CENTER, spaceAfter=2, leading=14,
)
ESTILO_CARATULA_BUS = ParagraphStyle(
    "caratulabus", fontName="Helvetica", fontSize=10,
    alignment=TA_CENTER, spaceAfter=0, leading=14,
)
ESTILO_ROTULO = ParagraphStyle(
    "rotulo", fontName="Helvetica-Bold", fontSize=9,
    alignment=TA_LEFT, spaceAfter=0, leading=12,
)
ESTILO_VALOR = ParagraphStyle(
    "valor", fontName="Helvetica", fontSize=9,
    alignment=TA_LEFT, spaceAfter=0, leading=12,
)
ESTILO_NOTA = ParagraphStyle(
    "nota", fontName="Helvetica-Bold", fontSize=10,
    alignment=TA_JUSTIFY, spaceBefore=8, spaceAfter=4, leading=14,
)
ESTILO_PIE = ParagraphStyle(
    "pie", fontName="Helvetica", fontSize=8,
    alignment=TA_CENTER, spaceBefore=8, spaceAfter=0, leading=11,
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


# ============================================================
#  Bus Federal (Ley 22.172)
# ------------------------------------------------------------
#  Es un formulario, no una carta: el modelo es de una cédula real del SISFE
#  (RIVAS C/ ASOCIART ART SA, notificación a una empresa de CABA, 2 páginas).
# ============================================================

# Domicilio de los tribunales para el exhorto. Verificado: Rosario, Balcarce
# 1651 (Mapa Judicial del Poder Judicial de Santa Fe + la cédula real). Para
# otra ciudad va en datos["domicilio_tribunal"]: no se inventa una dirección
# para mandar un exhorto.
_DOMICILIOS_TRIBUNAL = {"ROSARIO": "Balcarce 1651, Rosario"}


def _tribunal_exhortante(datos):
    """Cómo se presenta el tribunal que exhorta."""
    propio = str(datos.get("tribunal_exhortante") or "").strip()
    if propio:
        return _esc(propio).upper()
    ciudad = _esc(datos.get("ciudad", "Rosario")).upper()
    nom = str(datos.get("nominacion") or "").strip()
    juzgado = f"JUZGADO {_fuero_simple(datos)}" + (f" N° {nom}" if nom else "")
    return f"{juzgado} — {ciudad} — PROVINCIA DE SANTA FE"


def _domicilio_tribunal(datos):
    propio = str(datos.get("domicilio_tribunal") or "").strip()
    if propio:
        return _esc(propio)
    return _DOMICILIOS_TRIBUNAL.get(_esc(datos.get("ciudad", "Rosario")).upper(), "")


def _secretaria_txt(datos):
    """'Dra. A / Dr. B' cuando hay secretario y prosecretario."""
    partes = [(datos.get("secretario") or "").strip(),
              (datos.get("prosecretario") or "").strip()]
    return _esc(" / ".join(p for p in partes if p))


def _tabla_campos(filas, titulo="", con_caja=False, gris=False):
    """Tabla de etiqueta + valor, con un renglón abajo de cada fila.

    Es el formato de la Bus Federal: las etiquetas a la izquierda y el valor a
    la derecha, separado por una línea para escribir. Si viene `titulo`, va una
    primera fila que ocupa las dos columnas (el 'PARA EL OFICIAL NOTIFICADOR').
    """
    cuerpo = [[Paragraph(_esc(k), ESTILO_ROTULO), Paragraph(_esc(v), ESTILO_VALOR)]
              for k, v in filas]
    datos_tabla = ([[Paragraph(titulo, ESTILO_ROTULO), ""]] + cuerpo) if titulo else cuerpo

    t = Table(datos_tabla, colWidths=[4.7 * cm, None])
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#444444")),
        # Poco aire: la cédula real entra en dos páginas y con más padding se
        # desborda a una tercera con apenas dos párrafos.
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]
    if titulo:
        estilo += [("SPAN", (0, 0), (1, 0)), ("LINEBELOW", (0, 0), (-1, 0), 0, colors.white)]
    if con_caja:
        estilo += [
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#444444")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
        ]
    if gris:
        estilo.append(("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ededed")))
    t.setStyle(TableStyle(estilo))
    return t


def _resoluciones(texto):
    """Los decretos, uno por párrafo y con la fecha en negrita.

    En la cédula real cada resolución va aparte, encabezada por su fecha
    ('ROSARIO, 21 de Mayo de 2026: …'). Si el texto trae varias se separan; si
    trae una sola, sale como un solo párrafo.
    """
    texto = (texto or "").strip()
    if not texto:
        return []
    # El \b del principio es imprescindible: sin él el patrón también matchea
    # adentro de la palabra ('RIO, 21 de Mayo…' dentro de 'ROSARIO, …') y el
    # texto sale partido letra por letra (R / O / S / A / RIO, …).
    fecha = (r"\b[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{2,25},\s*\d{1,2}\s+de\s+"
             r"[A-Za-zÁÉÍÓÚÑ]+\s*(?:de\s+\d{4})?\s*:")
    salida = []
    for parte in re.split(f"(?={fecha})", texto):
        parte = parte.strip()
        if not parte:
            continue
        m = re.match(f"^({fecha})(.*)$", parte, re.S)
        if m:
            salida.append(Paragraph(f"<b>{_esc(m.group(1))}</b>{_esc(m.group(2))}",
                                    ESTILO_CUERPO))
        else:
            salida.append(Paragraph(_esc(parte), ESTILO_CUERPO))
    return salida


def _bloque_firma_bus_federal():
    """Las dos firmas: el oficial notificador y el tribunal receptor."""
    linea = "_______________________________"
    filas = [
        [Paragraph(linea, ESTILO_FIRMA), Paragraph(linea, ESTILO_FIRMA)],
        [Paragraph("<b>Firma del Oficial Notificador</b>", ESTILO_FIRMA),
         Paragraph("<b>Firma y Sello del Receptor</b>", ESTILO_FIRMA)],
        [Paragraph("", ESTILO_FIRMA),
         Paragraph("(Tribunal Receptor — Ley 22.172)", ESTILO_PIE)],
    ]
    t = Table(filas, colWidths=[7.4 * cm, None])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def generar_pdf_bus_federal(datos, ruta):
    """Cédula Bus Federal (Ley 22.172) para notificar fuera de Santa Fe.

    Sigue el modelo de una cédula real del SISFE (2 páginas): los datos del
    tribunal exhortante y del receptor, la clave de acceso al expediente, la
    carátula, el destinatario con su CUIT, el objeto, y en la segunda página el
    recuadro que completa el oficial notificador con las dos firmas.

    Lo que no venga en los datos sale vacío, con el renglón para completar a
    mano: la clave de acceso la genera el SISFE y el CUIT y el domicilio salen
    del expediente. Antes esta cédula dejaba el destinatario y el domicilio en
    blanco a propósito; ahora se imprimen si están (y si no, se dejan para
    completar, como antes).
    """
    cuij = _esc(datos.get("cuij", ""))
    clave = _esc(datos.get("clave_acceso", ""))
    caratula = _esc(datos.get("caratula", ""))
    dest = _esc(datos.get("destinatario_nombre", "")).upper()
    dom = _esc(datos.get("destinatario_domicilio", ""))
    cuit = _esc(datos.get("destinatario_cuit", ""))

    # 'BETTER CATERING S.A. — CUIT 30-70821868-1', como en la cédula real.
    notificar_a = f"{dest} — CUIT {cuit}" if dest and cuit else dest

    elementos = [
        Paragraph("CÉDULA DE NOTIFICACIÓN - LEY 22.172", ESTILO_ROTULO_BUS),
        Paragraph("(BUS FEDERAL DE JUSTICIA — COMUNICACIÓN ELECTRÓNICA "
                  "INTERJURISDICCIONAL)", ESTILO_ROTULO_BUS),
        Spacer(1, 14),
        _tabla_campos([
            ("TRIBUNAL EXHORTANTE:", _tribunal_exhortante(datos)),
            ("DOMICILIO DEL TRIBUNAL:", _domicilio_tribunal(datos)),
            ("JUEZA:", _esc((datos.get("juez") or "").strip())),
            ("SECRETARÍA:", _secretaria_txt(datos)),
            ("CLAVE DE ACCESO AL EXPEDIENTE:", clave),
            ("TRIBUNAL RECEPTOR:", BUSFEDERAL_TRIBUNAL_RECEPTOR),
            ("DOMICILIO A NOTIFICAR:", dom),
        ]),
        Spacer(1, 16),
        Paragraph("CARÁTULA:", ESTILO_ROTULO_BUS),
        Paragraph(f"&ldquo;{caratula}&rdquo;", ESTILO_CARATULA_BUS),
        Spacer(1, 16),
        _tabla_campos([
            ("CUIJ:", cuij),
            ("NOTIFICAR A:", notificar_a),
            ("DOMICILIO:", dom),
        ]),
        Spacer(1, 16),
        Paragraph("<b>OBJETO DE LA NOTIFICACIÓN:</b>", ESTILO_CAMPO),
        Paragraph("Se hace saber a Ud. que en el juicio de referencia se han "
                  "dictado las siguientes resoluciones:", ESTILO_CUERPO),
    ]

    elementos += _resoluciones(datos.get("texto_decreto", ""))
    # El cierre y el instructivo van juntos: si quedan al final de una página,
    # que bajen los dos enteros y no partidos al medio.
    elementos.append(KeepTogether([
        Paragraph(_esc(BUSFEDERAL_CIERRE), ESTILO_CUERPO),
        Paragraph(_esc(BUSFEDERAL_COMO_ACCEDER.format(cuij=cuij, clave=clave)), ESTILO_NOTA),
    ]))

    # El formulario del oficial notificador es lo último y va entero: es la
    # parte que se imprime, se lleva y se firma. No se fuerza el salto de
    # página (una cédula corta desperdiciaría una hoja): se mantiene junto y
    # cae donde tenga que caer.
    elementos.append(Spacer(1, 18))
    elementos.append(KeepTogether([
        _tabla_campos(
            [
                ("Fecha de diligenciamiento:", "____ / ____ / ______"),
                ("Hora:", "____________"),
                ("Persona que recibe:", "_____________________________"),
                ("Carácter:", "titular / familiar / empleado / otro: ________________"),
                ("DNI de quien recibe:", "___________________"),
                ("Observaciones:", "___________________________________________"),
            ],
            titulo="PARA EL OFICIAL NOTIFICADOR:",
            con_caja=True,
            gris=True,
        ),
        Spacer(1, 26),
        _bloque_firma_bus_federal(),
        Paragraph(_esc(BUSFEDERAL_PIE), ESTILO_PIE),
    ]))

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
