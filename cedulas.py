# ============================================================
#  CEDULAS.PY - Generador de cédulas en .docx
# ============================================================

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os
import re
from datetime import datetime

# Artículos del CPL que se transcriben en cédulas de audiencia Art. 51
ARTICULOS_AUD_51 = """ARTICULO 51. (Conforme Ley 13039) Audiencia de trámite. Contestada la demanda y, en su caso, la reconvención o vencido el término para hacerlo, el juez proveerá la prueba ofrecida y fijará de oficio una audiencia que deberá realizarse en un plazo no mayor de treinta días. Las partes deberán comparecer personalmente para lo cual, además de la notificación en el domicilio procesal, se las citará en el real, con una anticipación no menor de tres días, bajo apercibimiento de que la inasistencia injustificada será sancionada con una multa que graduará prudencialmente el juez, sin perjuicio de otros que en su caso correspondan. Tratándose de personas de existencia ideal, podrán ser representadas por los directores, socios, gerentes o empleados superiores con poder suficiente y debidamente instruidos sobre los hechos debatidos a los fines de asegurar el cumplimiento del objetivo de la audiencia. La citación a la audiencia de trámite se realizará con la prevención de que, en casos excepcionales de imposibilidad material de concurrir a la misma, las personas físicas deberán hacerse representar en la conciliación por apoderado especial con instrucciones y mandato suficientes. Las notificaciones correspondientes se efectuarán con transcripción de este párrafo. El juez deberá tomar personalmente bajo sanción de nulidad la audiencia de trámite; la que ajustará al siguiente ordenamiento: I - Conciliación: a) El juez intentará conciliar a las partes, no significando prejuzgamiento las apreciaciones que pudiere formular en las tratativas correspondientes. b) La conciliación podrá promoverse en forma total o parcial respecto de las pretensiones deducidas y estará dirigida hacia los siguientes fines: 1. Lograr el acuerdo de las partes. Si ello se consigue, se concretarán las bases del acuerdo de manera que no afecten los derechos irrenunciables establecidos por las leyes. 2. Simplificar las cuestiones litigiosas. 3. Aclarar errores materiales. 4. Reducir la actividad probatoria en relación a los hechos, tendiendo a la economía del proceso. c) Obtenido un acuerdo entre las partes sobre cualquiera de los aspectos señalados, se hará constar en el acta de la audiencia, debiendo ser homologado por el juez en resolución fundada. La homologación producirá el efecto de cosa juzgada. II - Continuación del Debate: a) Si la conciliación hubiera sido parcial el trámite proseguirá respecto de los puntos no avenidos, sin perjuicio del procedimiento de pronto pago que establece este Código. b) Si no hubiere conciliación, continuará el procedimiento del juicio en la misma audiencia. III - Cuestión de Puro Derecho: Si la cuestión fuere de puro derecho, así se declarará por decisión inapelable, sin perjuicio de los recursos que correspondan contra la sentencia. En estos casos, las partes podrán alegar oralmente en el mismo acto, de cuyo contenido quedará constancia en acta, o presentar un memorial escrito dentro de los cinco días. La sentencia se dictará dentro de los diez días siguientes a la celebración de la audiencia o, en su caso, de la presentación del memorial o de vencido el plazo para su presentación. IV.- Actividad Probatoria: La prueba que hubiere sido ofrecida para su producción anticipada, de acuerdo a la facultad de los incisos "f" de los Artículos 39 y 47, deberá proveerse en ocasión de la demanda o contestación. Sin perjuicio de ello, podrá ofrecerse, reiterarse o ampliarse su contenido en esta oportunidad. Cuando hubiere hechos controvertidos o de demostración necesaria en la cuestión principal, el término de producción de la prueba será de cuarenta días. Se recibirá la confesional de ambas partes y el reconocimiento de documental por parte del actor. Las partes ofrecerán de inmediato y por su orden toda la prueba de que intenten valerse y que no corresponda ofrecer o no haya sido ofrecida en la demanda, en la contestación y en la reconvención y su contestación. El juez proveerá en el mismo acto. Cuando alguna diligencia hubiere de realizarse fuera de la Provincia o la naturaleza de la cuestión en debate lo justificara, el juez, por resolución fundada podrá ampliar el plazo hasta un máximo de veinte días más.

ARTÍCULO 52 - Casos de incomparecencia. I.- Regla General: La incomparecencia de una o ambas partes a la audiencia de trámite no suspenderá, en ningún caso, la realización de la misma, salvo acuerdo en sentido contrario presentado hasta el día anterior al fijado para su realización. No se podrá suspender la audiencia por este motivo más de una vez. II.- Apoderados: En ningún caso la ausencia de la parte dispensa a su apoderado de concurrir a la audiencia ni de realizar los actos procesales concernientes a la misma, salvo el supuesto contemplado en el párrafo anterior. Si el ofrecimiento de prueba fuera realizado por un abogado o procurador que patrocinó al litigante ausente en alguno de sus escritos anteriores, se tendrá por válido si fuera ratificado por el mismo hasta el tercer día hábil posterior a la audiencia. Dicha ratificación es independiente al hecho que finalmente se justifique o no su ausencia. III.- Justificación de Ausencia: En caso de que una o ambas partes justificaren su inasistencia a la audiencia hasta el tercer día hábil posterior a su realización, el juez fijará una nueva fecha de audiencia, dentro del período de prueba, al solo efecto de la conciliación y de rendir la confesional del impedido, si esta prueba se hubiere ofrecido oportunamente. En caso contrario, se aplicarán los apercibimientos previstos en este Código para el ausente.

ARTICULO 66. Además de la notificación a su apoderado en el domicilio legal, el absolvente será citado en su domicilio real, con una anticipación no menor de tres días al acto y con apercibimiento de que si faltare sin justa causa será tenido por confeso sobre los hechos expuestos en la demanda o su contestación, salvo prueba en contrario.

ARTICULO 71. (Conforme Ley 13039) Reconocimiento o negativa. Los documentos acompañados por las partes en la demanda, en la contestación, o en la reconvención y su contestación, deberán ser reconocidos o negados en su autenticidad o recepción, en las siguientes oportunidades procesales: a) para los documentos acompañados con la demanda, en el escrito de responde; b) para los documentos acompañados al interponer excepciones, al tiempo de contestarlas; c) para los documentos acompañados en la contestación de la demanda o reconvención, en la audiencia de trámite; d) para los documentos que se presentaren con posterioridad a la audiencia, ya sean de fecha posterior a la misma o que hubieran llegado a conocimiento de las partes después de su celebración, en la forma que establezca el juez o tribunal en ejercicio de sus facultades. En todos los casos, bajo apercibimiento de tenerlos por reconocidos o recibidos."""


def set_font(run, bold=False, size=10):
    """Configura fuente Arial en un run."""
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.bold = bold
    r = run._r
    rPr = r.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), 'Arial')
    rFonts.set(qn('w:hAnsi'), 'Arial')
    rPr.insert(0, rFonts)


def agregar_parrafo(doc, texto, centrado=False, bold=False, size=10, espacio_antes=0, espacio_despues=0):
    """Agrega un párrafo al documento con formato."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if centrado else WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(espacio_antes)
    p.paragraph_format.space_after = Pt(espacio_despues)
    run = p.add_run(texto)
    set_font(run, bold=bold, size=size)
    return p


def es_decreto_audiencia_51(texto_decreto):
    """Detecta si el decreto fija audiencia Art. 51 CPL."""
    texto_lower = texto_decreto.lower()
    indicadores = [
        "art. 51", "artículo 51", "articulo 51",
        "audiencia de trámite", "audiencia de tramite",
        "fija fecha de audiencia", "se fija audiencia",
        "ley 7.945", "ley 7945"
    ]
    return any(ind in texto_lower for ind in indicadores)


def es_decreto_sin_notificacion(texto_decreto, titulo=""):
    """
    Detecta decretos de mero trámite que NO generan cédula.
    Retorna True si el decreto NO debe notificarse.

    `titulo` es el texto corto de la tabla de movimientos de SISFE
    (ej. "AGREGUESE", "TENGASE PRESENTE"). Las reglas originales son
    "por título": se revisa primero ahí, sin el umbral de palabras
    que sí aplica al contenido completo del decreto (que suele traer
    de arrastre la carátula y el encabezado, empujando el conteo de
    palabras por encima de cualquier umbral razonable).
    """
    texto_lower = texto_decreto.lower().strip()
    titulo_lower = (titulo or "").lower().strip()
    combinado = f"{texto_lower} {titulo_lower}"

    # Si en cualquiera de los dos se ordena expresamente notificar -> SÍ genera cédula
    if any(f in combinado for f in ["notifíquese", "notifiquese", "notificar por cédula", "notificar por cedula"]):
        return False

    # Patrones de decretos que no se notifican
    sin_notif = [
        "téngase presente",
        "tengase presente",
        "agréguese",
        "agregúese",
        "agreguese",
        "acompañe",
        "acompanie",
        "oficiese",
        "ofíciese",
        "pase a fallo",
        "por recibido",
        "autos para resolver",
        "autos para sentencia",
        "pase a despacho",
        "estese",
        "reserve",
        "reserve en secretaría",
        "reserve en secretaria",
        "glósese",
        "glosese",
        "fóliese",
        "foliese",
        "hágase saber",  # solo si es el único contenido
        "tómese nota",
        "tomese nota",
        "por constituido",
        "por desistido",
        "archívese",
        "archivese",
    ]

    # 1) Chequeo por TÍTULO — es corto por naturaleza, no necesita umbral.
    if titulo_lower:
        for frase in sin_notif:
            if frase in titulo_lower:
                return True

    # 2) Chequeo por CONTENIDO completo, solo si el decreto es corto
    #    (menos de 15 palabras) — evita filtrar de más un decreto largo
    #    y sustantivo que solo menciona una de estas frases de pasada.
    palabras = texto_lower.split()
    if len(palabras) < 15:
        for frase in sin_notif:
            if frase in texto_lower:
                return True

    # Decretos que empiezan con téngase presente o agréguese y tienen poco más
    for frase in ["téngase presente", "tengase presente", "agréguese", "agregúese", "agreguese"]:
        if texto_lower.startswith(frase) and len(palabras) < 25:
            return True


    return False


def es_primer_decreto(texto_decreto):
    """
    Detecta si es el primer decreto (traslado de demanda).
    Se reconoce por las fórmulas de citación/emplazamiento a contestar demanda.
    """
    texto_lower = texto_decreto.lower()
    indicadores = [
        "cítese y emplácese",
        "citese y emplacese",
        "comparezca a estar a derecho",
        "córrase traslado",
        "corrase traslado",
        "para que conteste demanda",
        "a contestar la demanda",
        "por iniciada la acción",
        "téngase por demandado",
        "tengase por demandado",
    ]
    return any(ind in texto_lower for ind in indicadores)


def domicilio_para_demandada(caratula):
    """
    Busca en la carátula la ART/demandada y devuelve su domicilio.
    Devuelve cadena vacía si no la encuentra (para completar a mano).
    """
    from config import DOMICILIOS_ART
    import unicodedata

    # Normalizar: mayúsculas sin acentos
    car = unicodedata.normalize('NFKD', caratula.upper())
    car = "".join(c for c in car if not unicodedata.combining(c))

    for clave, domicilio in DOMICILIOS_ART.items():
        clave_norm = unicodedata.normalize('NFKD', clave.upper())
        clave_norm = "".join(c for c in clave_norm if not unicodedata.combining(c))
        if clave_norm in car:
            return domicilio
    return ""


def es_bus_federal(texto_decreto, novedad="", domicilio_destinatario=""):
    """
    Detecta si corresponde el modelo de cédula Bus Federal (Ley 22.172):
      - el decreto menciona BUS FEDERAL, o
      - el destinatario tiene domicilio fuera de la Provincia de Santa Fe.
    """
    t = (texto_decreto + " " + novedad).lower()
    if "bus federal" in t or "bus-federal" in t or "ley 22.172" in t or "ley 22172" in t:
        return True

    dom = (domicilio_destinatario or "").upper()
    if not dom:
        return False

    # Si el domicilio menciona Santa Fe o Rosario, es local
    if "SANTA FE" in dom or "ROSARIO" in dom:
        return False

    fuera = [
        "CABA", "CIUDAD AUTÓNOMA", "CIUDAD AUTONOMA", "BUENOS AIRES",
        "CÓRDOBA", "CORDOBA", "MENDOZA", "ENTRE RÍOS", "ENTRE RIOS",
        "CORRIENTES", "CHACO", "TUCUMÁN", "TUCUMAN", "SALTA CAPITAL",
        "NEUQUÉN", "NEUQUEN", "RÍO NEGRO", "RIO NEGRO", "LA PAMPA",
        "SAN LUIS", "SAN JUAN", "JUJUY", "MISIONES", "FORMOSA",
        "SANTIAGO DEL ESTERO", "CATAMARCA", "LA RIOJA", "CHUBUT",
        "SANTA CRUZ", "TIERRA DEL FUEGO",
    ]
    return any(p in dom for p in fuera)


def es_caja(nombre_parte):
    """Detecta si la parte es una Caja (Forense o de Seguridad Social de Abogados)."""
    n = nombre_parte.upper()
    return "CAJA FORENSE" in n or "CAJA DE SEG" in n or "CAJA DE SEGURIDAD" in n


def notifica_a_cajas(texto_decreto, novedad=""):
    """
    Las Cajas se notifican solo en auto regulatorio de honorarios
    y en sentencia homologatoria.
    """
    t = (texto_decreto + " " + novedad).lower()
    indicadores = [
        "auto regulatorio",
        "regúlanse", "regulanse",
        "regúlase", "regulase",
        "honorarios",
        "homolog",          # homológase / homologación / homologatoria
    ]
    return any(i in t for i in indicadores)


def determinar_destinatarios(texto_decreto, partes_expediente):
    """
    Determina a quiénes se debe notificar según el contenido del decreto.
    Retorna lista de destinatarios del expediente que deben ser cedulizados.
    """
    texto_lower = texto_decreto.lower()
    destinatarios = []

    for parte in partes_expediente:
        nombre_lower = parte["nombre"].lower()
        rol = parte.get("rol", "").lower()

        # Primer decreto / traslado / citación → demandada y su letrado
        if any(p in texto_lower for p in ["cítese", "citese", "emplácese", "emplazase", "traslado"]):
            if "demandad" in rol or "letrado demandad" in rol:
                destinatarios.append(parte)

        # Peritos → solo al perito mencionado
        elif "perito" in texto_lower:
            if "perito" in rol:
                # Verificar si menciona la especialidad del perito
                if "médico" in texto_lower and "médico" in rol:
                    destinatarios.append(parte)
                elif "contador" in texto_lower and "contador" in rol:
                    destinatarios.append(parte)
                elif "psicólogo" in texto_lower and "psicólogo" in rol:
                    destinatarios.append(parte)
                elif "perito" in rol:  # perito genérico
                    destinatarios.append(parte)

        # Audiencia Art. 51 → todas las partes principales
        elif es_decreto_audiencia_51(texto_decreto):
            if any(r in rol for r in ["demandad", "actor", "letrado"]):
                destinatarios.append(parte)

        # Homologación / honorarios → cajas y letrados
        elif any(p in texto_lower for p in ["homolog", "honorario", "regúlanse", "regulanse"]):
            if any(r in rol for r in ["caja forense", "caja de seguridad", "letrado", "cassf"]):
                destinatarios.append(parte)

        # Por defecto: notificar a demandada y letrados
        else:
            if any(r in rol for r in ["demandad", "letrado demandad"]):
                destinatarios.append(parte)

    # Si no se identificó ninguno, notificar a todos
    if not destinatarios:
        destinatarios = partes_expediente

    return destinatarios


def generar_cedula_estandar(datos):
    """
    Genera una cédula estándar (Modelo Racca).
    datos = {
        'juzgado': str,
        'nominacion': str,
        'ciudad': str,
        'juez': str,
        'secretario': str,
        'caratula': str,
        'cuij': str,
        'texto_decreto': str,
        'fecha_decreto': str,
        'destinatario_nombre': str,
        'destinatario_domicilio': str,
    }
    """
    doc = Document()

    # Márgenes
    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(3)
    section.right_margin = Cm(2)

    # Encabezado
    agregar_parrafo(doc, "CÉDULA", centrado=True, bold=True, size=14, espacio_despues=6)

    juzgado_texto = f"JUZGADO DE PRIMERA INSTANCIA DE DISTRITO EN LO LABORAL DE LA\n{datos['nominacion']} NOMINACIÓN DE {datos['ciudad'].upper()}"
    agregar_parrafo(doc, juzgado_texto, centrado=True, bold=True, size=11, espacio_despues=12)

    # Destinatario
    agregar_parrafo(doc, f"Señor/a: {datos['destinatario_nombre'].upper()}", bold=True, size=10, espacio_despues=2)
    agregar_parrafo(doc, f"Domicilio: {datos['destinatario_domicilio']}", size=10, espacio_despues=12)

    # Cuerpo
    juez_txt = datos.get('juez', '').upper() or "________________"
    sec_txt = datos.get('secretario', '').upper() or "________________"
    nom_txt = datos.get('nominacion', '') or "____"
    cuerpo = (
        f"Hago saber a Ud. que en el juicio seguido ante el JUZGADO LABORAL DE LA "
        f"{nom_txt} NOMINACIÓN DE LA CIUDAD DE {datos['ciudad'].upper()}, "
        f"a cargo del/la DR./DRA. {juez_txt}, SECRETARIO/A DR./DRA. {sec_txt}, "
        f"dentro de los autos caratulados: \"{datos['caratula']}\" "
        f"CUIJ {datos['cuij']} se ha dictado lo siguiente: "
        f"{datos['ciudad'].upper()}, {datos['fecha_decreto']} "
        f"{datos['texto_decreto']}"
    )
    agregar_parrafo(doc, cuerpo, size=10, espacio_despues=18)

    # Cierre
    agregar_parrafo(
        doc,
        "En consecuencia queda usted debidamente notificado/a del decreto que antecede.",
        size=10, espacio_despues=24
    )

    # Firma
    agregar_parrafo(doc, "Rosario, _____ de ______________ de 20____", size=10, espacio_despues=36)
    agregar_parrafo(doc, "_______________________________", centrado=True, size=10)
    agregar_parrafo(doc, "Firma y sello", centrado=True, size=10)

    return doc


def generar_cedula_audiencia_51(datos):
    """
    Genera una cédula de audiencia Art. 51 CPL con transcripción de artículos.
    Basado en el modelo Quaranta.
    """
    doc = Document()

    # Márgenes
    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(3)
    section.right_margin = Cm(2)

    # Encabezado con dos columnas (juzgado izq, cédula judicial der)
    tabla_enc = doc.add_table(rows=1, cols=2)
    tabla_enc.style = 'Table Grid'
    # Quitar bordes
    for cell in tabla_enc.rows[0].cells:
        for side in ['top', 'bottom', 'left', 'right']:
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()

    celda_izq = tabla_enc.rows[0].cells[0]
    celda_der = tabla_enc.rows[0].cells[1]

    p_izq = celda_izq.paragraphs[0]
    p_izq.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r_izq = p_izq.add_run(f"JUZGADO DEL TRABAJO\n{datos['nominacion']} NOMINACIÓN\n{datos.get('direccion_juzgado', '')}")
    set_font(r_izq, bold=True, size=10)

    p_der = celda_der.paragraphs[0]
    p_der.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_der = p_der.add_run("CEDULA JUDICIAL")
    set_font(r_der, bold=True, size=10)

    doc.add_paragraph()

    # Fecha y ciudad
    agregar_parrafo(doc, f"{datos['ciudad']}, {datos['fecha_decreto']}.-", size=10, espacio_despues=6)

    # Destinatario
    agregar_parrafo(doc, f"SEÑOR/A: {datos['destinatario_nombre'].upper()}.-", bold=True, size=10, espacio_despues=2)
    agregar_parrafo(doc, f"DOMICILIO: {datos['destinatario_domicilio']}.-", size=10, espacio_despues=12)

    # Hago saber
    juez_txt = datos.get('juez', '').upper() or "________________"
    sec_txt = datos.get('secretario', '').upper() or "________________"
    nom_txt = datos.get('nominacion', '') or "____"
    agregar_parrafo(
        doc,
        f"Hago saber a Ud. que en el juicio seguido por ante el Juzgado del Trabajo de la "
        f"{nom_txt} Nominación de la ciudad de {datos['ciudad']}, a cargo de la/el DRA./DR. "
        f"{juez_txt}, PROSECRETARIA/O de la/el DRA./DR. {sec_txt}.",
        size=10, espacio_despues=6
    )

    # Datos del expediente (con líneas para completar si faltan)
    agregar_parrafo(doc, f"Por: {datos.get('actor', '') or '________________'}.", size=10, espacio_despues=2)
    agregar_parrafo(doc, f"Contra: {datos.get('demandado', '') or '________________'}.", size=10, espacio_despues=2)
    agregar_parrafo(doc, f"Sobre: {datos.get('objeto', '') or 'ACCIDENTES DEL TRABAJO'}.", size=10, espacio_despues=2)
    agregar_parrafo(doc, f"Expte. N°: {datos['cuij']}.", size=10, espacio_despues=12)

    # Decreto
    agregar_parrafo(doc, "Se ha dictado lo siguiente:", size=10, espacio_despues=6)

    p_decreto = doc.add_paragraph()
    p_decreto.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r_decreto = p_decreto.add_run(f'"{datos["texto_decreto"]}".-')
    set_font(r_decreto, size=10)

    doc.add_paragraph()

    # Cierre con fecha de audiencia
    fecha_aud = datos.get('fecha_audiencia', '___/___/20____')
    hora_aud = datos.get('hora_audiencia', '__:__ hs.')
    cierre = (
        f"En consecuencia queda Ud. debidamente notificado/a del/os decreto/s que antecede/n, "
        f"por el/los cual/es se le hace saber que el día {fecha_aud} a las {hora_aud} "
        f"se celebrará la audiencia a los fines del Art. 51 CPL (Ley 7945 modif. por Ley 13.039), "
        f"es decir, para conciliación, reconocimiento de la documental, absolución de posiciones "
        f"y exhibición de los recaudos legales intimados en la demanda, a la que la demandada deberá "
        f"comparecer muñida de su Documento Nacional de Identidad y de los instrumentos que acrediten "
        f"la representación que inviste para ABSOLVER POSICIONES y RECONOCER DOCUMENTAL, todo bajo los "
        f"apercibimientos de que si faltare sin justa causa previa y debidamente acreditada será tenido "
        f"por confeso de los hechos expuestos en la demanda y por reconocidos los documentos detallados "
        f"en la misma (art. 66 y 71 Ley 7945).\nAsimismo, se lo intima para que en la referida audiencia "
        f"del Art. 51 CPL presente DOCUMENTAL INTIMATIVA detallada en la demanda; todo ello bajo los "
        f"apercibimientos contenidos en los arts. 51, 52 y 66 CPL.-"
    )
    agregar_parrafo(doc, cierre, size=10, espacio_despues=12)

    # Transcripción de artículos
    agregar_parrafo(doc, ARTICULOS_AUD_51, size=9, espacio_despues=18)

    # Cierre final
    agregar_parrafo(doc, "Sin más, lo saludo atte.-", size=10, espacio_despues=24)
    agregar_parrafo(doc, "_______________________________", centrado=True, size=10)
    agregar_parrafo(doc, "Firma y sello", centrado=True, size=10)

    return doc


def guardar_cedula(doc, ruta_carpeta, cuij, destinatario, fecha):
    """Guarda la cédula en la carpeta correcta con nombre descriptivo."""
    os.makedirs(ruta_carpeta, exist_ok=True)
    fecha_str = fecha.replace("/", "-").replace(" ", "_")
    dest_str = destinatario.replace(" ", "_").replace("/", "-")[:30]
    nombre = f"cedula_{fecha_str}_{dest_str}.docx"
    ruta_completa = os.path.join(ruta_carpeta, nombre)
    doc.save(ruta_completa)
    return ruta_completa


def procesar_decreto(datos_decreto, datos_expediente, ruta_destino):
    """
    Función principal. Recibe datos del decreto y el expediente,
    determina si genera cédula y de qué tipo, y la guarda.
    Retorna lista de rutas de archivos generados.
    """
    texto = datos_decreto.get("texto", "")
    archivos_generados = []

    # 1) ¿El decreto genera cédula?
    if es_decreto_sin_notificacion(texto):
        print(f"  → Decreto de mero trámite, no genera cédula.")
        return []

    # 2) ¿Qué tipo de cédula?
    # Solo usar el modelo de audiencia 51 si además se detectó la fecha/hora,
    # de lo contrario saldría con datos vacíos.
    es_aud51 = (
        es_decreto_audiencia_51(texto)
        and datos_decreto.get("fecha_audiencia")
        and datos_decreto.get("hora_audiencia")
    )

    # 3) ¿A quién se notifica?
    partes = datos_expediente.get("partes", [])
    caratula = datos_expediente.get("caratula", "")
    novedad = datos_decreto.get("novedad", "")

    # CASO ESPECIAL: decreto que ordena notificar por Bus Federal.
    # El destinatario y su domicilio no están en SISFE -> una sola cédula en blanco.
    bus_fed_decreto = es_bus_federal(texto, novedad)
    if bus_fed_decreto:
        print("  → Bus Federal: destinatario y domicilio quedan en blanco para completar")
        destinatarios = [{"nombre": "", "domicilio": "", "rol": "bus federal"}]

    # CASO ESPECIAL: primer decreto (traslado de demanda)
    elif es_primer_decreto(texto):
        from config import DESTINATARIOS_PROVINCIA_1ER_DECRETO
        import unicodedata
        car_norm = unicodedata.normalize('NFKD', caratula.upper())
        car_norm = "".join(c for c in car_norm if not unicodedata.combining(c))

        # Si la demandada es la Provincia de Santa Fe -> Gobernador + Fiscalía de Estado
        if "PROVINCIA DE SANTA FE" in car_norm:
            destinatarios = list(DESTINATARIOS_PROVINCIA_1ER_DECRETO)
        else:
            # ART demandada: una sola cédula con su domicilio (o en blanco)
            dom = domicilio_para_demandada(caratula)
            # El nombre de la ART se saca de la carátula (después de "c/")
            m = re.search(r'[Cc]/\s*(.+?)\s+[Ss]/', caratula)
            nombre_art = m.group(1).strip() if m else "PARTE DEMANDADA"
            destinatarios = [{"nombre": nombre_art, "domicilio": dom, "rol": "demandada"}]
    else:
        # Cualquier otro decreto notificable: una cédula por cada parte
        # del expediente (representantes, cajas, etc.), sin domicilio.
        if partes:
            destinatarios = list(partes)
            # Las Cajas solo se notifican en honorarios / homologación
            if not notifica_a_cajas(texto, novedad):
                antes = len(destinatarios)
                destinatarios = [p for p in destinatarios if not es_caja(p.get("nombre", ""))]
                omitidas = antes - len(destinatarios)
                if omitidas:
                    print(f"  → Cajas omitidas ({omitidas}): el decreto no regula honorarios ni homologa")
        else:
            # Sin lista de partes: cédula con destinatario en blanco para completar
            destinatarios = [{"nombre": "", "domicilio": "", "rol": ""}]

    if not destinatarios:
        print(f"  → No se identificaron destinatarios.")
        return []

    # 4) Generar una cédula por destinatario
    # Extraer actor / demandado / objeto de la carátula
    actor = demandado = objeto = ""
    mc = re.search(r'^(.*?)\s+[Cc]/\s*(.*?)\s+[Ss]/\s*(.*)$', caratula)
    if mc:
        actor = mc.group(1).strip()
        demandado = mc.group(2).strip()
        objeto = mc.group(3).strip()

    # Fecha del decreto: preferir la que trae el propio PDF
    fecha_dec = datos_decreto.get("fecha_decreto_texto") or datos_decreto.get("fecha", "")

    for parte in destinatarios:
        datos = {
            "juzgado": datos_expediente.get("juzgado", ""),
            "nominacion": datos_expediente.get("nominacion", ""),
            "ciudad": datos_expediente.get("ciudad", "Rosario"),
            "juez": datos_expediente.get("juez", ""),
            "secretario": datos_expediente.get("secretario", ""),
            "cargo_juez": datos_expediente.get("cargo_juez", "JUEZ"),
            "cargo_secretario": datos_expediente.get("cargo_secretario", "SECRETARIO"),
            "caratula": caratula,
            "cuij": datos_expediente.get("cuij", ""),
            "actor": actor,
            "demandado": demandado,
            "objeto": objeto,
            "direccion_juzgado": datos_expediente.get("direccion_juzgado", ""),
            "texto_decreto": texto,
            "fecha_decreto": fecha_dec,
            "fecha_audiencia": datos_decreto.get("fecha_audiencia", ""),
            "hora_audiencia": datos_decreto.get("hora_audiencia", ""),
            "destinatario_nombre": parte.get("nombre", ""),
            "destinatario_domicilio": parte.get("domicilio", ""),
        }

        try:
            from config import FORMATO_SALIDA
        except ImportError:
            FORMATO_SALIDA = "docx"

        if FORMATO_SALIDA.lower() == "pdf":
            from cedulas_pdf import guardar_cedula_pdf
            # Bus Federal: por decreto, o por domicilio fuera de Santa Fe
            usar_bus_fed = bus_fed_decreto or es_bus_federal(
                "", "", parte.get("domicilio", "")
            )
            ruta = guardar_cedula_pdf(
                datos, ruta_destino,
                es_aud51=bool(es_aud51),
                fecha_archivo=datos_decreto.get("fecha", ""),
                novedad=novedad,
                es_bus_federal=usar_bus_fed,
            )
        else:
            doc = generar_cedula_audiencia_51(datos) if es_aud51 else generar_cedula_estandar(datos)
            ruta = guardar_cedula(
                doc, ruta_destino,
                datos_expediente.get("cuij", "sin_cuij"),
                parte.get("nombre", "destinatario"),
                fecha_dec or datetime.now().strftime("%d-%m-%Y"),
            )

        archivos_generados.append(ruta)
        print(f"  ✓ Cédula generada: {ruta}")

    return archivos_generados
