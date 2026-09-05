---
name: "oficio-raeo"
description: "Genera el oficio al RAEO (Registro de Accidentes y Enfermedades Ocupacionales) y su escrito cargo \"ACOMPAÑA OFICIO AL RAEO PARA SU DILIGENCIAMIENTO\" en UN solo PDF (oficio en pág. 1-2, escrito cargo en pág. 3), a partir de la demanda o el expediente completo que sube Santiago. Si además detecta que el expediente está radicado en el Juzgado de 1ra Inst. en lo Laboral de la 5ta Nominación de Rosario (Laboral N°5), genera también el oficio SOLO (sin el escrito cargo) en archivo Word y arma un borrador en el Gmail de Santiago dirigido a laboral5ros@justiciasantafe.gov.ar con asunto, cuerpo y el Word adjunto. Usar siempre que Santiago suba una demanda o expediente de ART/accidente y pida \"el oficio al RAEO\", \"hacer el oficio al RAEO\", \"acompañar oficio al RAEO\", \"oficio al registro de accidentes\", \"el escrito cargo del RAEO\", aunque no diga la palabra skill."
---

# Oficio al RAEO

Genera, para un caso de ART/accidente de trabajo, el **oficio al RAEO** (Registro de Procesos Universales y de Accidentes y Enfermedades Ocupacionales) junto con su **escrito cargo** ("ACOMPAÑA OFICIO AL RAEO PARA SU DILIGENCIAMIENTO"), en **UN solo PDF** de 3 páginas:

- **Págs. 1-2 — OFICIO al RAEO** (formulario con datos del trabajador, accidente, reclamo, responsables y proceso).
- **Pág. 3 — ESCRITO CARGO** dirigido al Juez.

Ese es el orden del modelo firmado de Santiago; no invertir ni mezclar el texto de una parte en la página de la otra.

Formato fijo (preferencia de Santiago, ya lo hace el script — no cambiar): **cuerpo justificado, títulos centrados**.

**Regla Laboral N°5 (entrega extra):** si el expediente está radicado en el **Juzgado de Primera Instancia de Distrito en lo Laboral de la 5ta Nominación de Rosario** (Laboral N°5), además del PDF hay que generar:
1. El **oficio SOLO** (sin el escrito cargo) en **archivo Word (.docx)** editable.
2. Un **borrador en el Gmail de Santiago** dirigido a **laboral5ros@justiciasantafe.gov.ar**, con asunto, cuerpo y el Word adjunto.

Esto es porque el propio escrito cargo dice "se acompañó en formato editable vía mail a la casilla de correo del juzgado": Laboral N°5 pide el oficio editable por mail. Los demás juzgados no requieren esta entrega extra (solo el PDF).

## Insumo

Santiago sube la **demanda** o el **expediente completo** (PDF). De ahí se extraen todos los datos del oficio. No inventar datos: si algún campo no aparece en la documentación, dejarlo como placeholder entre corchetes (ej. `[ANTIGÜEDAD]`) y avisar al final qué quedó pendiente, o juntar todo lo faltante en una sola pregunta con AskUserQuestion antes de generar. Si Santiago pega los datos en el chat en vez de subir un archivo, usar eso.

## Paso 1 — Extraer los datos del caso

Leer la demanda/expediente y armar un `datos.json` con estos campos (claves exactas que espera el script):

**I - Trabajador:** `apellido`, `nombres`, `actividad` (puesto/tarea), `antiguedad`, `edad`, `doc_tipo` (por defecto "DNI"), `doc_nro` (con puntos), `estado_civil`, `domicilio`, `localidad`.

**II - Accidente/enfermedad:** `fecha_accidente`, `localidad_ocurrio`, `circunstancias` (relato breve del hecho, en minúscula inicial y terminado en punto, como en el modelo), `lesion` (lesión o enfermedad denunciada).

**III - Reclamo:** `concepto` (objeto de la demanda, ej. "Indemnización Leyes 24.557 y 26.773"), `porcentaje_incapacidad` (ej. "4%"), `monto_reclamado` (ej. "$5.342.400").

**IV - Responsables:** `empleador_nombre` (la ART demandada, ej. "PREVENCIÓN ART S.A."), `empleador_domicilio`, `empleador_localidad`, `ramo` (por defecto "ASEGURADORA DE RIESGOS DEL TRABAJO" si la demandada es una ART), `otros_responsables` (empleador real con CUIT, si lo hay; si no, dejar vacío).

**V - Proceso:** `expediente_nro` (CUIJ, formato `21-XXXXXXXX-X`), `caratula` (formato "ACTOR C/ DEMANDADO S/ OBJETO", **sin** el número), `vinculo_actor` (por defecto "Es la misma persona"), `profesionales` (por defecto "SANTIAGO AGUSTÍN SEGOVIA"), `accion` (por defecto "Especial (Ley 27.348)"), `juzgado` (como figura en el expediente, ej. "Juzg. 1ra. Inst. Laboral 5ta. Nom."), `juzgado_localidad` (ej. "Rosario"), `nominacion` (ordinal para el escrito, ej. "5ª" o "1ª"), `fecha_iniciacion`, `observaciones` (ej. "Expte. SRT N° 133585/25.").

**Escrito cargo:** `juzgado_desc` (descripción larga; si se omite, el script la arma como "Juzgado de Primera Instancia de Distrito en lo Laboral de la {nominacion} Nominación de {juzgado_localidad}"), `abogado` (por defecto "Santiago A. Segovia").

Verificación clave: `caratula` y `expediente_nro` deben coincidir con la demanda. El escrito cargo pega el número al final de la carátula automáticamente.

## Paso 2 — Detectar si es Laboral N°5 de Rosario

Determinar si el expediente está radicado en el **Juzgado de 1ra Instancia en lo Laboral de la 5ta Nominación de Rosario**. Pistas en la demanda/expediente: "Laboral 5", "5ta. Nom." / "5ª Nominación" del fuero Laboral, localidad Rosario. (Para referencia, ese juzgado es de la Jueza **Rina Graciela Brisighelli**, Secretaría de **Lorena Betina Spizzirri**.)

- Si **es Laboral N°5 de Rosario** → generar PDF + Word + borrador de Gmail (Pasos 3 y 4 con `--word` y Paso 5).
- Si **no** → generar solo el PDF (Paso 4 sin `--word`); saltear el Paso 5.

Ante la duda sobre el juzgado, preguntarle a Santiago antes de decidir.

## Paso 3 — Escribir el script y armar datos.json

Guardar el script `generar_oficio_raeo.py` (abajo, al final) en la carpeta de trabajo y crear `datos.json` con los campos del Paso 1. Instalar dependencias si faltan:

```bash
pip install reportlab python-docx pypdf --break-system-packages -q
```

## Paso 4 — Generar los archivos

```bash
python3 generar_oficio_raeo.py datos.json CARPETA_SALIDA        # solo PDF (juzgado común)
python3 generar_oficio_raeo.py datos.json CARPETA_SALIDA --word # PDF + Word (Laboral N°5)
```

Produce:
- `OFICIO_RAEO_{APELLIDO}_{CUIJ}.pdf` → **el PDF** (oficio pág. 1-2 + escrito cargo pág. 3). Es el que se presenta en el expediente.
- `OFICIO_RAEO_{APELLIDO}_{CUIJ}.docx` (solo con `--word`) → **el oficio editable**, sin el escrito cargo. Es el que va adjunto al mail del juzgado.

Antes de entregar, revisar rápido el PDF (que tenga 3 páginas y que la carátula/CUIJ sean los correctos).

## Paso 5 — Borrador de Gmail (SOLO si es Laboral N°5)

Crear un borrador en el Gmail de Santiago (queda en su cuenta, no se envía) con el tool de Gmail `create_draft`:

- `to`: `["laboral5ros@justiciasantafe.gov.ar"]`
- `subject`: `Oficio al RAEO en formato editable — {CARÁTULA} — CUIJ {expediente_nro}`
- `body` (cuerpo, tono formal de Santiago):

  > Estimados:
  >
  > En los autos caratulados "{caratula} {expediente_nro}", en trámite ante ese Juzgado, se acompaña en formato editable (archivo Word adjunto) el oficio al RAEO presentado en el día de la fecha, a fin de su diligenciamiento.
  >
  > Sin otro particular, saludo a Uds. muy atentamente.
  >
  > Santiago A. Segovia — Abogado

- `attachments`: un elemento con `filename` = el nombre del `.docx`, `mimeType` = `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, y `content` = el `.docx` codificado en **base64**. Para obtener el base64:

  ```bash
  base64 -w0 CARPETA_SALIDA/OFICIO_RAEO_{APELLIDO}_{CUIJ}.docx
  ```

**Fallback del adjunto:** el tool de Gmail a veces no acepta adjuntos. Si `create_draft` falla al pasar `attachments`, reintentar creando el borrador **sin** el adjunto (mismo to/subject/body) y avisarle a Santiago que adjunte el Word manualmente antes de enviar (el Word igual se le entrega con `present_files`).

## Paso 6 — Entregar

Presentar con `present_files`:
- Siempre: el **PDF** (oficio + escrito cargo).
- Si Laboral N°5: además el **Word** del oficio, y avisar en una línea que el **borrador ya quedó armado en su Gmail** para laboral5ros@justiciasantafe.gov.ar (revisar y enviar), indicando si el adjunto entró o si hay que sumarlo a mano.

Resumen de una sola línea (actor y CUIJ). No transcribir el contenido en el chat — Santiago lo revisa en el archivo. Si Santiago corrige el **texto** de un modelo (no los datos del caso), avisarle que conviene actualizar esta skill.

---

## Script: generar_oficio_raeo.py

Guardar tal cual y ejecutar: `python3 generar_oficio_raeo.py datos.json CARPETA_SALIDA [--word]`.

```python
# -*- coding: utf-8 -*-
# ============================================================
#  GENERAR_OFICIO_RAEO.PY  — Estudio Jurídico Segovia
#  UN PDF: págs. 1-2 OFICIO al RAEO (formulario) + pág. 3 ESCRITO CARGO.
#  Con --word: además un .docx SOLO del oficio (editable para el mail al juzgado).
#  Formato: cuerpo justificado, títulos centrados.
#  Uso: python3 generar_oficio_raeo.py datos.json CARPETA_SALIDA [--word]
#  Requiere: reportlab (PDF); python-docx (solo con --word).
# ============================================================
import os, re, sys, json

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

ESTILO_TITULO = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=11,
    alignment=TA_CENTER, spaceAfter=4, leading=14)
ESTILO_SECCION = ParagraphStyle("seccion", fontName="Helvetica-Bold", fontSize=10.5,
    alignment=TA_LEFT, spaceBefore=10, spaceAfter=4, leading=14)
ESTILO_CAMPO = ParagraphStyle("campo", fontName="Helvetica", fontSize=10.5,
    alignment=TA_LEFT, spaceAfter=2, leading=15)
ESTILO_CUERPO = ParagraphStyle("cuerpo", fontName="Helvetica", fontSize=10.5,
    alignment=TA_JUSTIFY, spaceAfter=8, leading=15)
ESTILO_CUERPO_ESCRITO = ParagraphStyle("cuerpo_escrito", fontName="Helvetica", fontSize=11,
    alignment=TA_JUSTIFY, spaceAfter=12, leading=17)


def _esc(t):
    if t is None:
        return ""
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _g(d, k, default=""):
    v = d.get(k)
    return v if v not in (None, "") else default


def _doc(ruta):
    return SimpleDocTemplate(ruta, pagesize=A4,
        leftMargin=2.5 * cm, rightMargin=2.5 * cm, topMargin=2.5 * cm, bottomMargin=2.5 * cm,
        title="Oficio al RAEO", author="Estudio Jurídico Segovia")


def _caratula_completa(d):
    car = _g(d, "caratula")
    expte = _g(d, "expediente_nro")
    if expte and expte not in car:
        return f"{car} {expte}".strip()
    return car


def _juzgado_desc(d):
    jd = _g(d, "juzgado_desc")
    if jd:
        return jd
    nom = _g(d, "nominacion", "____")
    ciudad = _g(d, "juzgado_localidad") or _g(d, "localidad", "Rosario")
    return f"Juzgado de Primera Instancia de Distrito en lo Laboral de la {nom} Nominación de {ciudad}"


def _campo(label, valor):
    return Paragraph(f"{_esc(label)}: {_esc(valor)}", ESTILO_CAMPO)


def elementos_oficio(d):
    e = []
    e.append(Paragraph("REGISTRO DE PROCESOS UNIVERSALES", ESTILO_TITULO))
    e.append(Paragraph("Y DE ACCIDENTES Y ENFERMEDADES", ESTILO_TITULO))
    e.append(Paragraph("OCUPACIONALES", ESTILO_TITULO))
    e.append(Spacer(1, 14))

    e.append(Paragraph("Señor", ESTILO_CAMPO))
    e.append(Paragraph("Nro.: ……………………………………", ESTILO_CAMPO))
    e.append(Paragraph("Funcionario a cargo del", ESTILO_CAMPO))
    e.append(Paragraph("Registro de Procesos Universales y de", ESTILO_CAMPO))
    e.append(Paragraph("Accidentes y Enfermedades Ocupacionales", ESTILO_CAMPO))
    e.append(Paragraph("Fecha: ………………………………", ESTILO_CAMPO))
    e.append(Paragraph("S / D", ESTILO_CAMPO))
    e.append(Spacer(1, 10))

    e.append(Paragraph(
        "Quien suscribe informa a Ud. que se han iniciado las siguientes actuaciones "
        "sobre accidentes y enfermedades ocupacionales:", ESTILO_CUERPO))

    e.append(Paragraph("I - Datos del trabajador accidentado o enfermo", ESTILO_SECCION))
    e.append(_campo("Apellido", _g(d, "apellido")))
    e.append(_campo("Nombres", _g(d, "nombres")))
    e.append(_campo("Actividad", _g(d, "actividad")))
    e.append(_campo("Antigüedad en ese empleo", _g(d, "antiguedad")))
    e.append(_campo("Edad", _g(d, "edad")))
    e.append(Paragraph(
        f"Doc. Tipo: {_esc(_g(d, 'doc_tipo', 'DNI'))}&nbsp;&nbsp;Nro.: {_esc(_g(d, 'doc_nro'))}"
        f"&nbsp;&nbsp;Estado Civil: {_esc(_g(d, 'estado_civil'))}", ESTILO_CAMPO))
    e.append(Paragraph(
        f"Domicilio: {_esc(_g(d, 'domicilio'))}&nbsp;&nbsp;Localidad: {_esc(_g(d, 'localidad'))}",
        ESTILO_CAMPO))

    e.append(Paragraph("II - Datos del accidente y/o enfermedad", ESTILO_SECCION))
    e.append(Paragraph(
        f"Fecha: {_esc(_g(d, 'fecha_accidente'))}&nbsp;&nbsp;"
        f"Localidad donde ocurrió: {_esc(_g(d, 'localidad_ocurrio'))}", ESTILO_CAMPO))
    e.append(Paragraph(
        f"Circunstancias de lugar y modo del accidente y/o enfermedad: "
        f"{_esc(_g(d, 'circunstancias'))}", ESTILO_CUERPO))
    e.append(Paragraph(
        f"Lesión y/o enfermedad denunciada: {_esc(_g(d, 'lesion'))}", ESTILO_CAMPO))

    e.append(Paragraph("III - Datos del reclamo", ESTILO_SECCION))
    e.append(_campo("Concepto reclamado (objeto de la demanda)", _g(d, "concepto")))
    e.append(_campo("Porcentaje de Incapacidad reclamada", _g(d, "porcentaje_incapacidad")))
    e.append(_campo("Monto reclamado", _g(d, "monto_reclamado")))

    e.append(Paragraph("IV - Datos de los responsables demandados", ESTILO_SECCION))
    e.append(_campo("Nombres del empleador y/o responsables", _g(d, "empleador_nombre")))
    e.append(Paragraph(
        f"Domicilio: {_esc(_g(d, 'empleador_domicilio'))}&nbsp;&nbsp;"
        f"Localidad: {_esc(_g(d, 'empleador_localidad'))}", ESTILO_CAMPO))
    e.append(_campo("Ramo o actividad", _g(d, "ramo")))
    if _g(d, "otros_responsables"):
        e.append(_campo("Otros responsables o demandados", _g(d, "otros_responsables")))

    e.append(Paragraph("V - Datos del Proceso", ESTILO_SECCION))
    e.append(_campo("Expediente Nro.", _g(d, "expediente_nro")))
    e.append(_campo("Carátula", _g(d, "caratula")))
    e.append(_campo("Vínculo del Actor con el accidentado", _g(d, "vinculo_actor", "Es la misma persona")))
    e.append(_campo("Profesionales del actor", _g(d, "profesionales", "SANTIAGO AGUSTÍN SEGOVIA")))
    e.append(_campo("Acción interpuesta", _g(d, "accion", "Especial (Ley 27.348)")))
    e.append(Paragraph(
        f"Juzgado: {_esc(_g(d, 'juzgado'))}&nbsp;&nbsp;"
        f"Localidad: {_esc(_g(d, 'juzgado_localidad') or _g(d, 'localidad', 'Rosario'))}", ESTILO_CAMPO))
    e.append(_campo("Fecha de iniciación de la causa", _g(d, "fecha_iniciacion")))
    if _g(d, "observaciones"):
        e.append(_campo("Observaciones", _g(d, "observaciones")))

    e.append(Spacer(1, 40))
    e.append(Paragraph("FIRMA Y SELLO DEL PROFESIONAL", ESTILO_CAMPO))
    return e


def elementos_escrito(d):
    abogado = _g(d, "abogado", "Santiago A. Segovia")
    return [
        Paragraph("ACOMPAÑA OFICIO AL RAEO PARA SU DILIGENCIAMIENTO", ESTILO_TITULO),
        Spacer(1, 16),
        Paragraph("<b>Sr. Juez:</b>", ESTILO_CUERPO_ESCRITO),
        Paragraph(
            f"{_esc(abogado)}, abogado por la parte actora, en la representación acreditada "
            f"dentro de los autos caratulados: &ldquo;<b>{_esc(_caratula_completa(d))}</b>&rdquo;, "
            f"en trámite ante el {_esc(_juzgado_desc(d))}, ante V.S. me presento y digo:",
            ESTILO_CUERPO_ESCRITO),
        Paragraph(
            "Que vengo por la presente a acompañar oficio para ser diligenciado al RAEO, "
            "asimismo, se acompañó en formato editable vía mail a la casilla de correo del "
            "juzgado.", ESTILO_CUERPO_ESCRITO),
        Paragraph("Por lo expuesto a V.S. solicito:", ESTILO_CUERPO_ESCRITO),
        Paragraph("1) Tenga por acompañado proyecto de oficio al RAEO.", ESTILO_CUERPO_ESCRITO),
        Paragraph("2) Se disponga su rúbrica y libramiento.", ESTILO_CUERPO_ESCRITO),
        Spacer(1, 10),
        Paragraph("Proveer de conformidad,", ESTILO_CUERPO_ESCRITO),
        Paragraph("<b>Y SERÁ JUSTICIA.</b>", ESTILO_CUERPO_ESCRITO),
    ]


def generar_pdf(d, ruta):
    elementos = elementos_oficio(d) + [PageBreak()] + elementos_escrito(d)
    _doc(ruta).build(elementos)
    return ruta


def generar_docx_oficio(d, ruta):
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    base = doc.styles["Normal"]
    base.font.name = "Times New Roman"
    base.font.size = Pt(11)

    def par(texto="", bold=False, center=False, justify=False, space_before=0):
        p = doc.add_paragraph()
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif justify:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf = p.paragraph_format
        pf.space_after = Pt(2)
        pf.space_before = Pt(space_before)
        if texto:
            r = p.add_run(texto)
            r.bold = bold
        return p

    def campo(label, valor):
        par(f"{label}: {valor}")

    par("REGISTRO DE PROCESOS UNIVERSALES", bold=True, center=True)
    par("Y DE ACCIDENTES Y ENFERMEDADES", bold=True, center=True)
    par("OCUPACIONALES", bold=True, center=True)
    par()
    par("Señor")
    par("Nro.: ……………………………………")
    par("Funcionario a cargo del")
    par("Registro de Procesos Universales y de")
    par("Accidentes y Enfermedades Ocupacionales")
    par("Fecha: ………………………………")
    par("S / D")
    par()
    par("Quien suscribe informa a Ud. que se han iniciado las siguientes actuaciones sobre "
        "accidentes y enfermedades ocupacionales:", justify=True)

    par("I - Datos del trabajador accidentado o enfermo", bold=True, space_before=8)
    campo("Apellido", _g(d, "apellido"))
    campo("Nombres", _g(d, "nombres"))
    campo("Actividad", _g(d, "actividad"))
    campo("Antigüedad en ese empleo", _g(d, "antiguedad"))
    campo("Edad", _g(d, "edad"))
    campo("Doc. Tipo", f"{_g(d, 'doc_tipo', 'DNI')}   Nro.: {_g(d, 'doc_nro')}   "
          f"Estado Civil: {_g(d, 'estado_civil')}")
    campo("Domicilio", f"{_g(d, 'domicilio')}   Localidad: {_g(d, 'localidad')}")

    par("II - Datos del accidente y/o enfermedad", bold=True, space_before=8)
    campo("Fecha", f"{_g(d, 'fecha_accidente')}   Localidad donde ocurrió: {_g(d, 'localidad_ocurrio')}")
    par(f"Circunstancias de lugar y modo del accidente y/o enfermedad: {_g(d, 'circunstancias')}",
        justify=True)
    campo("Lesión y/o enfermedad denunciada", _g(d, "lesion"))

    par("III - Datos del reclamo", bold=True, space_before=8)
    campo("Concepto reclamado (objeto de la demanda)", _g(d, "concepto"))
    campo("Porcentaje de Incapacidad reclamada", _g(d, "porcentaje_incapacidad"))
    campo("Monto reclamado", _g(d, "monto_reclamado"))

    par("IV - Datos de los responsables demandados", bold=True, space_before=8)
    campo("Nombres del empleador y/o responsables", _g(d, "empleador_nombre"))
    campo("Domicilio", f"{_g(d, 'empleador_domicilio')}   Localidad: {_g(d, 'empleador_localidad')}")
    campo("Ramo o actividad", _g(d, "ramo"))
    if _g(d, "otros_responsables"):
        campo("Otros responsables o demandados", _g(d, "otros_responsables"))

    par("V - Datos del Proceso", bold=True, space_before=8)
    campo("Expediente Nro.", _g(d, "expediente_nro"))
    campo("Carátula", _g(d, "caratula"))
    campo("Vínculo del Actor con el accidentado", _g(d, "vinculo_actor", "Es la misma persona"))
    campo("Profesionales del actor", _g(d, "profesionales", "SANTIAGO AGUSTÍN SEGOVIA"))
    campo("Acción interpuesta", _g(d, "accion", "Especial (Ley 27.348)"))
    campo("Juzgado", f"{_g(d, 'juzgado')}   Localidad: "
          f"{_g(d, 'juzgado_localidad') or _g(d, 'localidad', 'Rosario')}")
    campo("Fecha de iniciación de la causa", _g(d, "fecha_iniciacion"))
    if _g(d, "observaciones"):
        campo("Observaciones", _g(d, "observaciones"))

    par()
    par()
    par("FIRMA Y SELLO DEL PROFESIONAL")

    doc.save(ruta)
    return ruta


def _apellido(d):
    ap = _g(d, "apellido")
    if ap:
        return ap.upper().replace(" ", "-")
    m = re.match(r"^\s*([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", _g(d, "caratula"))
    return m.group(1).upper() if m else "ACTOR"


def _cuij(d):
    return re.sub(r"[^0-9-]", "", _g(d, "expediente_nro")) or "SINCUIJ"


def main():
    if len(sys.argv) < 3:
        print("Uso: python3 generar_oficio_raeo.py datos.json CARPETA_SALIDA [--word]")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)
    carpeta = sys.argv[2]
    os.makedirs(carpeta, exist_ok=True)
    hacer_word = "--word" in sys.argv[3:]

    base = f"OFICIO_RAEO_{_apellido(d)}_{_cuij(d)}"
    ruta_pdf = os.path.join(carpeta, base + ".pdf")
    generar_pdf(d, ruta_pdf)
    print("PDF (oficio + escrito cargo):\n ", ruta_pdf)

    if hacer_word:
        ruta_docx = os.path.join(carpeta, base + ".docx")
        generar_docx_oficio(d, ruta_docx)
        print("Word (solo oficio):\n ", ruta_docx)


if __name__ == "__main__":
    main()
```

