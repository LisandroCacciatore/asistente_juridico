---
name: "oficio-incumplimiento-boletas"
description: "Genera los 3 oficios por incumplimiento al pago de boletas colegiales del estudio de Santiago Segovia en PDF (Colegio de Abogados de Rosario, Caja de Seguridad Social de Abogados y Procuradores, y Caja Forense), y además deja 3 borradores de correo en su Gmail —uno a cada organismo— con los autos en el asunto y el PDF respectivo adjunto. A partir de un decreto que Santiago pega, lee los profesionales del expediente en el SISFE vía Claude in Chrome y le pregunta cuáles son los incumplidores a informar (esos mismos se nombran en el cuerpo del mail). Usar siempre que Santiago pegue un decreto y pida \"los oficios por incumplimiento de boletas\", \"oficio al Colegio y las Cajas\", \"oficio por falta de pago de boleta colegial\", \"oficiar a las cajas profesionales\", o cuando un decreto lo intime a acompañar su boleta colegial bajo apercibimiento de correr vista a la Caja de Seguridad Social o al Colegio de Abogados, aunque no diga la palabra skill."
---

# Oficio por incumplimiento al pago de boletas

Genera los **3 oficios informativos por incumplimiento al pago de boletas colegiales** del estudio de Santiago Segovia, en PDF, uno por cada organismo, y **deja 3 borradores de correo en Gmail** (uno por organismo) con el PDF respectivo adjunto:

| # | Organismo (destinatario del oficio) | Correo (destinatario del borrador) |
|---|---|---|
| 1 | COLEGIO DE ABOGADOS - ROSARIO | directorio@colabro.org.ar |
| 2 | CAJA DE SEG. SOCIAL DE ABOGADOS Y PROCURADORES | mesadeentradasrosario@capsantafe.org.ar |
| 3 | CAJA FORENSE - ROSARIO | mesadeentradas@cajaforense.com |

Los tres oficios son idénticos salvo el destinatario. Flujo: decreto pegado → leer profesionales del expediente en el SISFE → preguntar cuáles van en el INFORMAR → generar un PDF por organismo → dejar los 3 borradores con su PDF adjunto (el cuerpo del mail nombra a esos mismos profesionales).

Formato obligatorio de todos los PDF (preferencia fija de Santiago): **texto justificado, títulos centrados**. El script ya lo hace; no cambiar.

## Paso 1 — Parsear el decreto pegado

Del texto que pega Santiago, extraer:

- **Carátula**: formato "ACTOR C/ DEMANDADO S/ OBJETO CUIJ" (ej.: "BARROZO AILEN NEREA C/ PROVINCIA DE SANTA FE S/ ACCIDENTES DEL TRABAJO 21-04255346-5"). Usar la carátula completa tal como va en el encabezado del oficio y como **asunto** de los mails.
- **CUIJ / Nº expediente**: formato `21-XXXXXXXX-X`.
- **Juzgado** y localidad. Escribirlo en el oficio en forma desarrollada, ej.: "Juzgado de 1ra. Instancia de Distrito en lo Laboral de la 5ta. Nominación de Rosario". Si el decreto lo trae abreviado ("Juzg. 1ra. Inst. Laboral 5ta. Nom. ROSARIO"), desarrollarlo.
- **Decreto a transcribir**: es el decreto que ordena oficiar/informar, y va transcripto **textual** dentro del oficio (sección "Asimismo, se transcribe el siguiente decreto: ..."). Copiarlo íntegro y sin corregir la redacción; solo limpiar saltos de línea rotos del copy-paste. Si Santiago pega un decreto que claramente NO es el que ordena oficiar (p. ej. un decreto de audiencia del art. 56, que intima a acompañar boletas pero no dice "Ofíciese"), no volcar ese texto largo: usar el texto estándar `Informativa: Ofíciese a sus efectos, a los organismos mencionados. Autorízase al Dr. Santiago A. Segovia y/o a quien éste designe a la confección y diligenciamiento conforme Art. 25 CPCC.` y avisarle a Santiago que se usó ese, por si prefiere pegar el decreto de "Ofíciese".
- **Fecha**: mes y año para el encabezado ("Rosario, ____ de JULIO de 2026.-"). El día queda en blanco (lo completa Santiago al presentarlo). Si el decreto no trae mes, usar el mes y año corrientes.

## Paso 2 — Obtener los profesionales del expediente desde SISFE

El bloque **INFORMAR** del oficio (y el cuerpo de los mails) nombra a profesionales del expediente. Para saber quiénes intervienen, leer las partes del expediente en el SISFE, igual que en la skill `cedula-sisfe`.

Cargar las herramientas de Claude in Chrome vía ToolSearch (una sola llamada con el set completo: `tabs_context_mcp, navigate, computer, read_page, get_page_text, find, form_input`).

El camino rápido: **buscar por CUIJ → sacar el id interno del href → ir directo a la pantalla "Nueva Cédula" por URL**, que muestra la tabla PARTES con el carácter de cada uno.

1. `tabs_context_mcp{createIfEmpty:true}` y navegar a `https://sisfe.justiciasantafe.gov.ar/buscar-expediente`. Si no hay sesión iniciada, aplicar el fallback de abajo.
2. La página suele abrir ya con la lista de expedientes de Santiago. Buscar la fila del CUIJ del decreto directamente en el texto (`get_page_text`); si no está, expandir "FILTROS DE BÚSQUEDA", cargar el CUIJ completo (ej. `21-04255346-5`) en el campo **CUIJ** con `form_input` y accionar **"Efectuar la búsqueda"**.
3. Con la fila del expediente, usar `find` con "enlace del expediente {CUIJ}": el href tiene la forma `/detalle-expediente/{id}`. **No clickear la fila**: tomar el `{id}` del href.
4. Navegar DIRECTO a `https://sisfe.justiciasantafe.gov.ar/nueva-notificacion-expediente/{id}` — pantalla "Nueva Cédula" con la tabla **PARTES** (Seleccionar / Caracter / Parte / Correo Electrónico).
5. Leer con `get_page_text` y extraer **cada parte con su carácter, nombre y código entre paréntesis** (REPRESENTANTE, AUXILIAR DE JUSTICIA, PERITO, etc.). El código entre paréntesis (ej. `XXI011`, `FE01`, `6372`) es la matrícula/código de caja que va en el INFORMAR — así no hace falta preguntarla. Ignorar como profesionales los AUXILIAR DE JUSTICIA que son las propias cajas (CS01, CF02): esos son los organismos destinatarios, no incumplidores.

**Cómo interactuar con el SISFE**: preferir siempre `get_page_text`, `find`, `form_input` y navegación por URL antes que screenshots y clicks por coordenadas. La app re-renderiza con escala inconsistente; si un click por coordenadas es inevitable, tomar el screenshot inmediatamente antes y verificar el resultado con `get_page_text`.

**Verificación clave**: la pantalla muestra la carátula y el CUIJ arriba — confirmar que coinciden con el decreto pegado ANTES de usar las partes. Si no coinciden, avisar a Santiago antes de seguir.

**Fallback** (sin extensión de Chrome, sin sesión SISFE, o la navegación falla): pedirle a Santiago que pegue una captura de la pantalla con las partes, o que dicte directamente los profesionales y matrículas. No insistir con la navegación más de un par de intentos.

## Paso 3 — Preguntar los profesionales del INFORMAR (AskUserQuestion)

Con la lista de representantes leída del SISFE, hacer **una** pregunta de AskUserQuestion (multiSelect): cuáles profesionales van como incumplidores en el bloque **INFORMAR** del oficio. Una opción por representante, formato "NOMBRE (código) — carácter" (ej.: "GENTILE QUARANTA, LEONARDO EUGENIO (XXI011) — representante"). Incluir la representación de la demandada (p. ej. "FISCALIA DE ESTADO PROVINCIAL (FE01) — representante de la demandada") cuando corresponda.

Esos **mismos** profesionales elegidos se usan también en el cuerpo del mail (Paso 5) — no preguntar por separado. Si el código de algún profesional no vino del SISFE, tomarlo del decreto/conversación o preguntarlo en la misma tanda; si no hay, omitir el paréntesis.

## Paso 4 — Generar los 3 PDF

Armar un JSON de datos con esta forma exacta:

```json
{
  "caratula": "BARROZO AILEN NEREA C/ PROVINCIA DE SANTA FE S/ ACCIDENTES DEL TRABAJO 21-04255346-5",
  "cuij": "21-04255346-5",
  "juzgado": "Juzgado de 1ra. Instancia de Distrito en lo Laboral de la 5ta. Nominación de Rosario",
  "fecha_mes": "JULIO",
  "fecha_anio": "2026",
  "decreto_transcripto": "Informativa: Ofíciese a sus efectos, a los organismos mencionados. Autorízase al Dr. Santiago A. Segovia y/o a quien éste designe a la confección y diligenciamiento conforme Art. 25 CPCC.",
  "profesionales": [
    {"nombre": "GENTILE QUARANTA, LEONARDO EUGENIO", "matricula": "XXI011"},
    {"nombre": "FISCALIA DE ESTADO PROVINCIAL", "matricula": "FE01", "extra": "representante de la demandada en autos"}
  ]
}
```

Notas del JSON:
- `profesionales`: los elegidos en el Paso 3. `matricula` y `extra` son opcionales. El `extra` (ej. "representante de la demandada en autos") se agrega al final del listado; ponerlo en el último profesional.
- El script arma la frase automáticamente: "los Dres. A (mat) y B (mat), extra".

Guardar el script de abajo como `generar_oficios.py` (a un archivo temporal), guardar el JSON, e instalar reportlab si falta:

```bash
python3 -c "import reportlab" 2>/dev/null || pip install reportlab --break-system-packages -q
python3 generar_oficios.py datos.json <carpeta_salida>
```

Genera los 3 PDF nombrados `OFICIO A {ORGANISMO} - {CUIJ}.pdf`, cada uno de una sola página. Verificar que pesen menos de 3 MB.

### Script `generar_oficios.py`

```python
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
```

## Paso 5 — Dejar los 3 borradores en Gmail (con el PDF adjunto)

Para cada organismo, crear un **borrador** (no enviar) con la herramienta de Gmail `create_draft` del conector de Gmail. El conector **sí soporta adjuntos** (probado: se pasa el PDF en base64 y el borrador queda con el archivo). Mapeo fijo organismo → correo y adjunto:

- COLEGIO DE ABOGADOS - ROSARIO → `directorio@colabro.org.ar` (adjuntar "OFICIO A COLEGIO DE ABOGADOS ROSARIO - {CUIJ}.pdf")
- CAJA DE SEG. SOCIAL DE ABOGADOS Y PROCURADORES → `mesadeentradasrosario@capsantafe.org.ar` (adjuntar "OFICIO A CAJA DE SEG. SOC - {CUIJ}.pdf")
- CAJA FORENSE - ROSARIO → `mesadeentradas@cajaforense.com` (adjuntar "OFICIO A CAJA FORENSE - {CUIJ}.pdf")

Para cada borrador:
- `to`: el correo del organismo (uno solo por borrador).
- `subject`: la **carátula/autos** completa (ej. "BARROZO AILEN NEREA C/ PROVINCIA DE SANTA FE S/ ACCIDENTES DEL TRABAJO 21-04255346-5").
- `body`: el texto de abajo, reemplazando `{NOMBRES}` por los **mismos profesionales elegidos para el INFORMAR** (Paso 3). Para personas usar el apellido (de "GENTILE QUARANTA, LEONARDO EUGENIO" → "Gentile Quaranta"); para entidades (Fiscalía de Estado) su nombre. Unir con comas y "y".

```
Estimado/a
Buenos días, vengo por el presente a acompañar oficio dentro de los autos del asunto, solicitando acompañen los dres. {NOMBRES} las correspondientes boletas de aporte inicial. En su defecto, líbrese oficio conforme las facultades conferidas por el art. 25 CPCC a las entidades afectadas a fin de poner en conocimiento dicho incumplimiento.
Solicito se conteste en autos al oficio diligenciado.
Muchas gracias. Saludos cordiales.
```

- `attachments`: un elemento con el PDF correspondiente. Obtener el base64 con `base64 -w0 "<ruta_pdf>"` y pasar `{ "filename": "<nombre.pdf>", "mimeType": "application/pdf", "content": "<base64>" }`. Los PDF pesan pocos KB, muy por debajo del límite de 25 MB.

Verificar con el `id` devuelto (o `list_drafts`) que quedaron los 3 borradores. **No enviarlos**: Santiago los revisa y envía. Si en alguna versión el adjunto fallara, crear igual el borrador con `to`/`subject`/`body`, avisar a Santiago para que adjunte el PDF a mano (queda entregado en el chat por el Paso 6) y no reintentar más de una vez.

## Paso 6 — Entregar

Presentar los 3 PDF con `present_files` y un resumen de una línea por oficio (organismo destinatario) y confirmar que quedaron los 3 borradores en Gmail. No transcribir el contenido en el chat: Santiago los revisa en el archivo y en los borradores.

Si Santiago corrige algo del **texto fijo** del modelo (Art. 25, cuerpo del mail, fórmulas) — no de los datos del caso — avisarle que conviene actualizar la plantilla/script de la skill para las próximas veces.

