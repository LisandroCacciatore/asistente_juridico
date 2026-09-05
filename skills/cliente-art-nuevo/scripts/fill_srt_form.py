#!/usr/bin/env python3
"""
Rellena uno de los 3 formularios oficiales SRT (Anexo I, II o III) sobre el PDF
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
"""
import argparse
import json
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

ASSETS = Path(__file__).parent.parent / "assets"

ANEXO_FILES = {
    "I": ASSETS / "ANEXO_I_divergencia_incapacidad.pdf",
    "II": ASSETS / "ANEXO_II_rechazo_accidente_trabajo.pdf",
    "III": ASSETS / "ANEXO_III_rechazo_enfermedad_profesional.pdf",
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
}

# NOTA sobre los nombres de estado "Opción1/2/3": pypdf a veces los muestra con
# problemas de encoding en la terminal (p. ej. "Opci髇1") — es solo un problema
# de impresión, el valor real en el PDF es correcto. Si algún radio no marca
# la opción esperada al renderizar, revisá get_fields()[grupo]['/_States_']
# del PDF de ese Anexo en assets/ y ajustá el diccionario correspondiente
# arriba en vez de adivinar.


def fill(anexo: str, data: dict, out_path: str):
    if anexo not in ANEXO_FILES:
        sys.exit(f"Anexo inválido: {anexo}. Usar I, II o III.")
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
    for page in writer.pages:
        writer.update_page_form_field_values(page, all_values)
    writer.set_need_appearances_writer(True)

    with open(out_path, "wb") as f:
        writer.write(f)
    print(f"Escrito: {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--anexo", required=True, choices=["I", "II", "III"])
    ap.add_argument("--data", required=True, help="Ruta a un JSON con {clave_amigable: valor}")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)
    fill(args.anexo, data, args.out)
