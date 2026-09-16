#!/usr/bin/env python3
"""
Rellena uno de los 4 formularios oficiales SRT (Anexo I, II, III o IV) sobre el PDF
editable real que provee la SRT (assets/ANEXO_*.pdf), en vez de recrear una tabla.

IMPORTANTE sobre los nombres de campo: varios campos de estos PDF tienen un
nombre interno (/T) que NO coincide con la pregunta visible al lado (parecen
haber sido nombrados copiando el texto de la pregunta siguiente o anterior por
error de quien armó el formulario en origen). Los mapeos de abajo ya están
verificados visualmente (se rellenó cada PDF con el nombre de cada campo como
valor y se lo renderizó a imagen para confirmar en qué casillero cae). No
renombres ni "corrijas" estas claves basándote en lo que parecen decir — están
así a propósito.

Uso:
    python fill_srt_form.py --anexo III --data data.json --out "Cliente - Formulario SRT Anexo III.pdf"

data.json es un diccionario plano {clave_amigable: valor}. Las claves amigables
están documentadas en FIELD_MAPS de abajo, agrupadas por anexo. Cualquier clave
que no venga en data.json se deja en blanco (no se inventan datos).

Para los campos Sí/No y de opción múltiple, el valor esperado en data.json es el
texto visible ("Sí", "No", "Accidente de trabajo", "Domicilio", etc.) — el script
se encarga de traducirlo al estado interno del PDF.

Por defecto el PDF de salida se APLANA (los valores quedan dibujados en la página).
Sin eso, el formulario se ve vacío en Chrome y en cualquier visor que no regenere
el aspecto por su cuenta. Si necesitás el formulario editable para corregir algo a
mano, pasá --editable (y revisá que los valores se vean antes de presentarlo).
"""
import argparse
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

ASSETS = Path(__file__).parent.parent / "assets"

ANEXO_FILES = {
    "I": ASSETS / "ANEXO_I_divergencia_incapacidad.pdf",
    "II": ASSETS / "ANEXO_II_rechazo_accidente_trabajo.pdf",
    "III": ASSETS / "ANEXO_III_rechazo_enfermedad_profesional.pdf",
    "IV": ASSETS / "ANEXO_IV_prestaciones.pdf",
}

# ---------------------------------------------------------------------------
# Mapeo clave amigable -> nombre real del campo en el PDF, por Anexo.
# Los comentarios indican la pregunta visible que ese campo realmente rellena
# (verificado visualmente, no solo por el nombre interno del campo).
# ---------------------------------------------------------------------------

FIELD_MAPS = {
    "III": {  # Rechazo de enfermedad profesional (2 páginas)
        "nombre_trabajador": "Texto13",
        "cuil": "Texto14",
        "letrado_nombre": "Texto10",
        "letrado_cuit_domicilio": "Texto11",
        "letrado_matricula": "Texto12",
        "empleador_nombre_cuit": "Texto6",
        "establecimiento": "Texto7",
        "localidad": "Texto8",
        "provincia": "Texto9",
        "art_denominacion": "Texto4",
        "art_cuit": "Texto5",
        "fecha_denuncia": "Fecha de la denuncia",
        "fecha_baja_laboral": "Fecha de baja laboral",
        "fecha_diagnostico": "Fecha de diagnóstico",
        "sector_area": "SectorÁrea de trabajo",
        "antiguedad_tarea": "Antigüedad en la tarea",
        "anio_ingreso": "Año de ingreso a la empresa",
        "tareas_detalladas": "Detalle de tareas",
        "diagnostico_enfermedad": "Diagnóstico de la enfermedad que denunciás",
        "empleadores_otros_nombre_cuit": "Sí NoNombreRazón Social y CUIT de los empleadores en caso de corresponder",
        "pruebas_origen_laboral": "Pruebas origen laboral",
        "comision_medica_n": "N",
        "jurisdiccion": "Jurisdicción",
        "firma_trabajador": "Firma Trabajador",
        "firma_trabajador_aclaracion": "Aclaración",
        "firma_letrado": "Firma Letrado Patrocinante En caso de corresponder",
        "firma_letrado_aclaracion": "Aclaración_2",
        # radios Sí/No
        "tareas_similares_otro_empleador": ("radio", "Group18", {"Sí": "Opción1", "No": "Opción2"}),
        "denuncio_misma_enfermedad_otro_empleador": ("radio", "Group19", {"Sí": "Opción3", "No": "Opción1"}),
        "recibio_atencion_art": ("radio", "Group20", {"Sí": "Opción2", "No": "Opción1"}),
        "art_dio_alta_medica": ("radio", "Group21", {"Sí": "Opción3", "No": "Opción1"}),
        "atencion_obra_social": ("radio", "Group22", {"Sí": "Opción2", "No": "Opción1"}),
        "fundamento_domicilio": ("radio", "Group25", {
            "Domicilio": "Opción3",
            "Domicilio de efectiva prestación de servicios": "Opción1",
            "Domicilio donde habitualmente reporta": "Opción2",
        }),
        "fecha_firma": "Fecha1_af_date",
    },
    "II": {  # Rechazo de accidente de trabajo (2 páginas)
        "nombre_trabajador": "Texto1",
        "cuil": "CUIL",
        "letrado_nombre": "Nombre y Apellido",
        "letrado_cuit_domicilio": "CUIT - Domicilio electrónico",
        "letrado_matricula": "Matrícula - Jurisdicción",
        "empleador_nombre": "Nombre - Razón Social",
        "empleador_cuit": "CUIT",
        "domicilio_prestacion_servicios": "Domicilio prestación de servicios",
        "localidad": "Localidad",
        "provincia": "Provincia",
        "art_denominacion": "Denominación - Razón Social",
        "art_cuit": "CUIT (En caso de empleadores)",
        # OJO: estos dos están cruzados en el PDF de origen (nombre interno no
        # coincide con la pregunta que realmente rellenan) — verificado visualmente.
        "hechos_y_circunstancias": "Detallá el o los compromisos o diagnósticos derivados de la contingencia",
        "compromisos_diagnosticos": "Detalle compromisos o diagnósticos",
        "fecha_denuncia": "Fecha de denuncia_af_date",
        "fecha_baja_laboral": "Fecha baja laboral_af_date",
        "fecha_ocurrencia": "Fecha ocurrencia_af_date",
        "horario_ingreso_egreso": "Horario de ingreso y egreso al puesto de trabajo",
        "domicilio_lugar_reporta": "Domicilio del lugar donde  presta servicios o donde habitualmente se reporta",
        "domicilio_residencia": "Domicilio de residencia",
        "lugar_accidente": "Lugar del accidente",
        "hora_accidente": "Hora del accidente",
        "fecha_primera_atencion": "Fecha primera atención médica_af_date",
        "pruebas_origen_laboral": "Pruebas origen laboral",
        "comision_medica_n": "N",
        "jurisdiccion": "Jurisdicción",
        "firma_trabajador": "Firma Trabajador",
        "firma_trabajador_aclaracion": "Aclaración",
        "firma_letrado": "Firma Letrado Patrocinante En caso de corresponder",
        "firma_letrado_aclaracion": "Aclaración_2",
        "fecha_firma": "Fecha10_af_date",
        "tipo_contingencia": ("radio", "Group8", {"Accidente de trabajo": "Opción1", "Accidente in itinere": "Opción2"}),
        "denuncia_policial": ("radio", "Group17", {"Sí": "Opción1", "No": "Opción2"}),
        "recibio_atencion_art": ("radio", "Group18", {"Sí": "Opción1", "No": "Opción2"}),
        "atencion_obra_social": ("radio", "Group19", {"Sí": "Opción1", "No": "Opción2"}),
        "estudio_medico_obra_social": ("radio", "Group20", {"Sí": "Opción1", "No": "Opción2"}),
        "fundamento_domicilio": ("radio", "Group3", {
            "Domicilio": "Opción1",
            "Domicilio de efectiva prestación de servicios": "Opción2",
            "Domicilio donde habitualmente reporta": "Opción3",
        }),
    },
    "I": {  # Divergencia en la determinación de la incapacidad (3 páginas)
        "nombre_trabajador": "Texto1",
        "cuil": "CUIL",
        "letrado_nombre": "Nombre y Apellido",
        "letrado_cuit_domicilio": "CUIT / Domcilio electrónico",
        "letrado_matricula": "Matrícula - Jurisdicción",
        "empleador_nombre": "NombreRazón Social",
        "empleador_cuit": "CUIT",
        "establecimiento": "Establecimiento del lugar de efectiva prestación de servicios o donde habitualmente reporta",
        "localidad": "Localidad",
        "provincia": "Provincia",
        "art_denominacion": "DenominaciónRazón Social",
        "art_cuit": "CUIT En caso de empleadores",
        "fecha_denuncia": "Fecha de la denuncia_af_date",
        "fecha_baja_laboral": "Fecha de baja laboral_af_date",
        "fecha_ocurrencia_diagnostico": "Fecha de ocurrencia o diagnóstico_af_date",
        "detalle_accidente_enfermedad": "Detalle accidente o enfermedad profesional",
        "afecciones_diagnosticos": "Detallá la o las afecciones o diagnósticos derivados de la contingencia",
        # OJO: este campo también está mal nombrado en el PDF de origen — en
        # realidad es la respuesta a "Detallá la prueba médica ofrecida
        # tendiente a acreditar la incapacidad", no el párrafo legal fijo.
        "prueba_medica_incapacidad": "Las partes deberán ofrecer en su primera presentación toda la prueba de la que intenten valerse acompañando en",
        "preexistencia_porcentaje": "Porcentaje de incapacidad",
        "preexistencia_region_cuerpo": "Región del cuerpo afectada",
        "preexistencia_prueba_judicial": "Detalle prueba judicial",
        "comision_medica_n": "N°",
        "jurisdiccion": "Jurisdicción",
        "firma_trabajador": "Firma Trabajador",
        "firma_trabajador_aclaracion": "Aclaración",
        "firma_letrado": "Firma Letrado Patrocinante",
        "firma_letrado_aclaracion": "Aclaración_2",
        "fecha_firma": "Fecha_af_date",
        "tipo_contingencia": ("radio", "Group1", {
            "Accidente de trabajo": "Opción1", "Accidente in itinere": "Opción2", "Enfermedad Profesional": "Opción3",
        }),
        "recibio_atencion_art": ("radio", "Group2", {"Sí": "Opción1", "No": "Opción2"}),
        "recibio_alta_medica": ("radio", "Group3", {"Sí": "Opción1", "No": "Opción2"}),
        "atencion_obra_social": ("radio", "Group4", {"Sí": "Opción1", "No": "Opción2"}),
        "estudio_medico_obra_social": ("radio", "Group5", {"Sí": "Opción1", "No": "Opción2"}),
        "preexistencia_incapacidad_previa": ("radio", "Group6", {"Sí": "Opción1", "No": "Opción2"}),
        "preexistencia_tipo_contingencia": ("radio", "Group15", {
            "Accidente de trabajo": "Opción1", "Accidente in itinere": "Opción2", "Enfermedad Profesional": "Opción3",
        }),
        "fundamento_domicilio": ("radio", "Group8", {
            "Domicilio": "Opción1",
            "Domicilio de efectiva prestación de servicios": "Opción2",
            "Domicilio donde habitualmente reporta": "Opción3",
        }),
    },
    "IV": {  # Prestaciones: alta, reingreso o divergencia en las prestaciones (2 páginas)
        # Verificado contra el PDF oficial (anexo_iv_-_prestaciones_editable_ok.pdf,
        # IF-2026-09572607-APN-SRT#MCH, Res. SRT 5/26) por geometría: se comparó el
        # rect de cada campo con la caja de cada texto del formulario, y se miró el
        # render de las dos páginas. OJO: este anexo NO tiene campos de letrado
        # patrocinante (el trámite no lo exige) — si Santiago firma como letrado,
        # va en "firma_trabajador"/"aclaración" o en hoja aparte.
        "nombre_trabajador": "Texto1",
        "cuil": "Texto2",
        "empleador_nombre": "NombreRazón Social",
        "empleador_cuit": "CUIT",
        "establecimiento": "Establecimiento del lugar de efectiva prestación de servicios o donde habitualmente reporta",
        "localidad": "Localidad",
        "provincia": "Provincia",
        "art_denominacion": "DenominaciónRazón Social",
        "art_cuit": "CUIT En caso de empleadores",
        "fecha_denuncia": "Fecha3_af_date",
        "fecha_baja_laboral": "Fecha4_af_date",
        "fecha_ocurrencia_diagnostico": "Fecha5_af_date",
        "fecha_alta_medica": "Fecha6_af_date",
        # OJO: los DOS cuadros grandes están nombrados al revés en el PDF de origen.
        # El campo que se llama "afecciones" es en realidad la respuesta a
        # "Detallá el accidente de trabajo o enfermedad profesional" (es el cuadro
        # que está justo debajo de esa etiqueta), y "Texto7" responde a
        # "Detallá la o las afecciones o diagnósticos...". Verificado por geometría
        # y por render: en este formulario la etiqueta va ARRIBA de su cuadro.
        "detalle_accidente_enfermedad": "Detallá la o las afecciones o diagnósticos por los que requiere prestaciones",
        "afecciones_diagnosticos": "Texto7",
        "detalle_prueba_medica": "Detalle prueba médica",
        "comision_medica_n": "N",
        "jurisdiccion": "Jurisdicción",
        "firma_trabajador": "Firma Trabajador",
        "firma_trabajador_aclaracion": "Aclaración",
        "fecha_firma": "Fecha8_af_date",
        # radios: en cada par, el círculo de la IZQUIERDA es "Sí" y el de la derecha
        # "No" (verificado: las cajas de las palabras están a x≈396 "Sí" y x≈448
        # "No", y los widgets en x≈408 y x≈462 respectivamente).
        "motivo_solicitud": ("radio", "Group5", {
            "Alta": "Opción1", "Reingreso": "Opción2", "Prestaciones": "Opción3",
        }),
        "recibio_atencion_art": ("radio", "Group7", {"Sí": "Opción4", "No": "Opción1"}),
        "art_dio_alta_medica": ("radio", "Group8", {"Sí": "Opción2", "No": "Opción1"}),
        "atencion_obra_social": ("radio", "Group9", {"Sí": "Opción3", "No": "Opción1"}),
        "estudio_medico_obra_social": ("radio", "Group10", {"Sí": "Opción2", "No": "Opción1"}),
        "fundamento_domicilio": ("radio", "Group11", {
            "Domicilio": "Opción1",
            "Domicilio de efectiva prestación de servicios": "Opción2",
            "Domicilio donde habitualmente reporta": "Opción3",
        }),
    },
}

# NOTA sobre los nombres de estado "Opción1/2/3": pypdf a veces los muestra con
# problemas de encoding en la terminal (p. ej. "Opci髇1") — es solo un problema
# de impresión, el valor real en el PDF es correcto. Si algún radio no marca
# la opción esperada al renderizar, revisá get_fields()[grupo]['/_States_']
# del PDF de ese Anexo en assets/ y ajustá el diccionario correspondiente
# arriba en vez de adivinar.


def _marcar_radios(writer, radio_values: dict):
    """Marca el /AS del grupo elegido (lo que mira Acrobat).

    pypdf escribe /V en el grupo pero deja el /AS de cada opción en /Off — los
    widgets de radio no están en /Annots con /FT propio, así que su rama de
    botones los pisa. Esto deja el /AS bien para el visor que sí lo respeta.
    Para el PDF aplanado, además, hay que dibujar el punto (ver _dibujar_puntos).
    """
    acro = writer._root_object["/AcroForm"]
    acro = acro.get_object() if hasattr(acro, "get_object") else acro
    for ref in acro.get("/Fields", []):
        campo = ref.get_object()
        if str(campo.get("/FT")) != "/Btn":
            continue
        elegido = radio_values.get(str(campo.get("/T")))
        if not elegido:
            continue
        kids = campo.get("/Kids")
        kids = kids.get_object() if kids else [ref]
        for k in kids:
            kid = k.get_object() if hasattr(k, "get_object") else k
            ap = kid.get("/AP")
            estado = _estado_elegido(elegido, ap)
            kid[NameObject("/AS")] = NameObject(estado or "/Off")


def _normalizar(texto) -> str:
    return str(texto or "").lstrip("/").strip().lower()


def _num_estado(texto) -> str:
    """Saca el número de un estado tipo "Opción2" (/Off no tiene número).

    Los nombres de estado de estos PDF llegan con el acento mal decodificado
    ("Opci髇2"), así que comparar el texto completo falla siempre. El número, en
    cambio, sobrevive a la decodificación: por eso se compara por número.
    """
    m = re.search(r"(\d+)\s*$", str(texto or ""))
    return m.group(1) if m else ""


def _estado_elegido(elegido: str, ap) -> str:
    """Devuelve el nombre real (el de /AP /N) del estado elegido, o ""."""
    if not ap or not ap.get("/N"):
        return ""
    quiero = _num_estado(elegido)
    for s in ap["/N"].keys():
        if _num_estado(s) and _num_estado(s) == quiero:
            return str(s)
    return ""


def _centros_elegidos(writer, radio_values: dict) -> dict:
    """Ubica el centro de la caja de la opción elegida de cada grupo de radios.

    Se llama ANTES de update_page_form_field_values(): hay que leer los estados
    (/AP /N) del formulario original, porque pypdf reemplaza los aspectos al
    aplanar y después ya no se puede saber qué widget era cada opción.
    Devuelve {indice_de_pagina: [(cx, cy), ...]}.
    """
    acro = writer._root_object["/AcroForm"]
    acro = acro.get_object() if hasattr(acro, "get_object") else acro
    elegido_por_grupo = {}
    for ref in acro.get("/Fields", []):
        campo = ref.get_object()
        if str(campo.get("/FT")) == "/Btn":
            elegido = radio_values.get(str(campo.get("/T")))
            if elegido:
                elegido_por_grupo[str(campo.get("/T"))] = _normalizar(elegido)

    por_pagina = {}
    for i, pagina in enumerate(writer.pages):
        for a in (pagina.get("/Annots") or []):
            an = a.get_object()
            if an.get("/Subtype") != "/Widget" or an.get("/Parent") is None:
                continue
            nombre = str(an["/Parent"].get_object().get("/T"))
            if elegido_por_grupo.get(nombre) is None:
                continue
            ap = an.get("/AP")
            if not _estado_elegido(elegido_por_grupo[nombre], ap):
                continue
            x0, y0, x1, y1 = [float(v) for v in an["/Rect"]]
            por_pagina.setdefault(i, []).append(((x0 + x1) / 2, (y0 + y1) / 2))
    return por_pagina


def _dibujar_puntos(writer, centros_por_pagina: dict):
    """Dibuja el punto negro de la opción elegida de cada grupo de radios.

    Sin esto el formulario aplanado sale con TODOS los círculos vacíos: pypdf
    genera un círculo vacío por opción y no hay forma de que el visor sepa cuál
    está elegido (no queda un aspecto usable ni un /AS que el visor respete).
    El punto se dibuja encima, en el centro de la caja de la opción elegida.
    """
    from pypdf.generic import ContentStream, NumberObject

    def num(v):
        return NumberObject(round(v, 2))

    for i, centros in (centros_por_pagina or {}).items():
        if not centros:
            continue
        pagina = writer.pages[i]

        contenido = ContentStream(pagina.get_contents(), writer)
        for cx, cy in centros:
            r = 4.0                 # radio del punto, dentro del círculo vacío
            k = 0.5523 * r          # constante de Bézier para aproximar un círculo
            contenido.operations.extend([
                ([], b"q"),
                ([num(0), num(0), num(0)], b"rg"),          # negro
                ([num(cx + r), num(cy)], b"m"),
                ([num(cx + r), num(cy + k), num(cx + k), num(cy + r), num(cx), num(cy + r)], b"c"),
                ([num(cx - k), num(cy + r), num(cx - r), num(cy + k), num(cx - r), num(cy)], b"c"),
                ([num(cx - r), num(cy - k), num(cx - k), num(cy - r), num(cx), num(cy - r)], b"c"),
                ([num(cx + k), num(cy - r), num(cx + r), num(cy - k), num(cx + r), num(cy)], b"c"),
                ([], b"f"),
                ([], b"Q"),
            ])
        pagina.replace_contents(contenido)


def fill(anexo: str, data: dict, out_path: str, editable: bool = False):
    if anexo not in ANEXO_FILES:
        sys.exit(f"Anexo inválido: {anexo}. Usar I, II, III o IV.")
    src = ANEXO_FILES[anexo]
    field_map = FIELD_MAPS[anexo]

    text_values = {}
    radio_values = {}
    for key, value in data.items():
        if not value:
            continue
        if key not in field_map:
            print(f"aviso: clave '{key}' no reconocida para el Anexo {anexo}, se ignora", file=sys.stderr)
            continue
        target = field_map[key]
        if isinstance(target, tuple) and target[0] == "radio":
            _, group_name, options = target
            if value not in options:
                print(f"aviso: valor '{value}' no válido para '{key}' (opciones: {list(options)})", file=sys.stderr)
                continue
            radio_values[group_name] = options[value]
        else:
            text_values[target] = value

    reader = PdfReader(str(src))
    writer = PdfWriter()
    writer.append(reader)

    all_values = {**text_values, **radio_values}

    # Los círculos elegidos se ubican ANTES de aplanar: pypdf reemplaza los
    # aspectos, y después ya no se puede saber qué widget era cada opción.
    centros_radios = _centros_elegidos(writer, radio_values)

    # OJO — acá estaba el bug que hacía que el formulario saliera VACÍO:
    # update_page_form_field_values() deja el valor en /V pero no lo dibuja en
    # la página. El PDF "tiene" los datos (se leen con get_fields()) pero no se
    # ven en Chrome ni en ningún visor que no regenere el aspecto por su cuenta
    # (que es lo que pide /NeedAppearances, y no todos los visores lo hacen).
    # Con flatten=True los valores quedan escritos en el contenido de la página
    # y se ven siempre. Por eso el default es aplanar: lo que se presenta es un
    # formulario completo, no un formulario editable a medio llenar.
    for page in writer.pages:
        writer.update_page_form_field_values(
            page, all_values, auto_regenerate=True, flatten=not editable,
        )
    if editable:
        writer.set_need_appearances_writer(True)

    # Después de aplanar: el /AS correcto (para Acrobat) y, si el PDF va
    # aplanado, el punto dibujado de la opción elegida (ver _dibujar_puntos).
    _marcar_radios(writer, radio_values)
    if not editable:
        _dibujar_puntos(writer, centros_radios)

    with open(out_path, "wb") as f:
        writer.write(f)
    print(f"Escrito: {out_path}" + (" (editable: sin aplanar)" if editable else ""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anexo", required=True, choices=["I", "II", "III", "IV"])
    ap.add_argument("--data", required=True, help="Ruta a un JSON con {clave_amigable: valor}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--editable", action="store_true",
                    help="No aplanar: deja el formulario editable (los valores pueden "
                         "no verse en algunos visores, ver la nota de fill())")
    args = ap.parse_args()
    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)
    fill(args.anexo, data, args.out, editable=args.editable)
