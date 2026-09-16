---
name: cliente-art-nuevo
description: Genera el paquete inicial de documentos para un cliente nuevo de casos de ART (Aseguradora de Riesgos del Trabajo) del estudio jurídico de Santiago Segovia — accidentes de trabajo, enfermedades profesionales y divergencias de incapacidad. Usar siempre que Santiago diga que tiene un cliente nuevo de ART, un caso de accidente laboral o enfermedad profesional, o pida armar el "poder especial", el "convenio de honorarios" / "pacto de cuota litis", un "relato de los hechos", un "formulario SRT" (Anexo I, II, III o IV) o un "telegrama" para un caso de ART, aunque no mencione todos los documentos a la vez. También usar si pide "arrancar un expediente", "cargar un cliente nuevo" o "preparar la documentación inicial" en el contexto de ART/SRT.
---

# Cliente nuevo de ART

Este flujo cubre lo que Santiago hace cada vez que entra un cliente nuevo por un caso de ART. El paquete estándar tiene 5 documentos:

1. Poder especial
2. Relato de los hechos (presentación corta a la SRT)
3. Cuerpo del telegrama de intimación a la ART (solo el texto, no el formulario completo)
4. Formulario SRT correspondiente (Anexo I, II, III o IV)
5. Pacto de cuota litis / convenio de honorarios

Todo se genera como .docx y se convierte a PDF, con el texto justificado y los títulos centrados (así es como Santiago quiere siempre sus escritos).

No inventes datos. Si falta un dato, dejalo como placeholder entre corchetes (p. ej. `[FECHA DEL ACCIDENTE]`) y avisale a Santiago al final qué quedó pendiente de completar, en vez de asumir un valor.

## Paso 1: reunir los datos del caso

Preguntale a Santiago (o extraé de lo que ya te haya pasado, incluida la documental si la adjuntó) lo siguiente. No hace falta preguntar todo de una — si ya tenés varios datos por el contexto, solo pedí lo que falte:

- **Tipo de caso**: accidente de trabajo, enfermedad profesional, o divergencia en la determinación de la incapacidad (este último es para un caso ya en trámite donde se discute el % de incapacidad, no un cliente recién llegado — confirmá cuál es antes de seguir, porque determina qué modelo de poder y qué Anexo SRT usar).
- **Datos del cliente**: nombre completo, DNI, CUIL, estado civil, domicilio, localidad.
- **Datos del empleador**: razón social, CUIT, tareas que realizaba, antigüedad.
- **Datos de la ART/aseguradora**: nombre, domicilio (para el telegrama, si hace falta).
- **Datos del hecho**:
  - Si es accidente: fecha, lugar, hora, mecánica del accidente, si es in itinere, si hubo denuncia policial.
  - Si es enfermedad profesional: fecha en que empezaron los síntomas, diagnóstico, tareas que generaron la dolencia.
- **Honorarios**: el estudio siempre pacta 20% de cuota litis + 5% adicional si interviene perito de parte, salvo que Santiago indique un % distinto para este cliente puntual.
- **El telegrama siempre se incluye** (solo el cuerpo, salvo que Santiago diga que la ART ya fue notificada y no hace falta — confirmá si tenés dudas).

## Paso 2: elegir los modelos correctos

- **Poder especial**: hay dos variantes según el tipo de caso — ver `references/poder-especial.md`. Usar la de accidente laboral o la de enfermedad profesional según corresponda. Ojo con la fecha: nunca lleva el día, y el mes solo se completa si Santiago te lo pide expresamente estando entre el 1 y el 10 del mes en curso (el detalle completo está en esa referencia).
- **Relato de los hechos**: hay dos variantes (accidente / enfermedad) — ver `references/relato-de-hechos.md`.
- **Pacto de cuota litis / convenio de honorarios**: un solo modelo adaptado a reclamos de ART — ver `references/convenio-honorarios.md`.
- **Formulario SRT**: hay 4 Anexos oficiales (Res. SRT 5/2026) y hay que elegir el que corresponde al tipo de caso — ver `references/formularios-srt.md` para la tabla de campos de cada uno:
  - Anexo I – Divergencia en la determinación de la incapacidad
  - Anexo II – Rechazo de accidente de trabajo
  - Anexo III – Rechazo de enfermedad profesional
  - Anexo IV – Prestaciones (reingreso al tratamiento, divergencia con el alta médica otorgada, divergencia con las prestaciones)
- **Telegrama**: por defecto, solo el cuerpo de texto (no la tabla oficial de destinatario/remitente), adaptado a accidente o enfermedad — ver `references/telegrama.md`.

## Paso 3: generar los documentos

Para el poder especial, el relato de los hechos, el pacto de cuota litis y el cuerpo del telegrama, generá archivos .docx usando la skill de docx del sistema (buscala e invocala antes de armar el archivo). Reglas de formato:

- Título del documento centrado (p. ej. "PODER ESPECIAL", "RELATO DE LOS HECHOS", "CONVENIO DE HONORARIOS", "TELEGRAMA").
- Cuerpo del texto justificado.
- Mantené el lenguaje formal y las fórmulas jurídicas tal como están en los modelos de referencia — no las resumas ni las simplifiques, salvo el párrafo del hecho concreto, que se redacta a medida con los datos del caso.

Para el **formulario SRT**, NO lo generes como .docx ni recrees una tabla: es un PDF oficial editable, y hay que rellenarlo sobre ese mismo PDF con `scripts/fill_srt_form.py` (ver `references/formularios-srt.md` para el detalle de cómo armar los datos y qué claves usar). Ese script ya produce el PDF final directamente.

Nombrá los archivos así: `[APELLIDO CLIENTE] - Poder Especial.docx`, `[APELLIDO CLIENTE] - Relato de los Hechos.docx`, `[APELLIDO CLIENTE] - Convenio Honorarios.docx`, `[APELLIDO CLIENTE] - Telegrama.docx` (más el PDF del formulario SRT que ya sale de `fill_srt_form.py`).

## Paso 4: convertir a PDF y guardar en la carpeta del cliente

Santiago quiere los 5 documentos como PDF, guardados directamente en su carpeta de trabajo — no simplemente entregados en el chat. Hacé esto:

1. Convertí a PDF el poder, el relato de los hechos, el convenio de honorarios y el telegrama (usá `soffice.py --headless --convert-to pdf`, como indica la skill de docx). El formulario SRT ya nace como PDF en el paso anterior, no hace falta convertirlo.
2. En la carpeta conectada "ESTUDIO JURIDICO", andá a la subcarpeta `1) ART`. Ahí cada cliente tiene su propia carpeta nombrada en mayúsculas como `APELLIDO NOMBRE` (mirá los nombres de las carpetas existentes para copiar el mismo estilo). Si la carpeta del cliente todavía no existe, creala con ese mismo formato de nombre.
3. Guardá ahí los 5 PDF: `[APELLIDO CLIENTE] - Poder Especial.pdf`, `[APELLIDO CLIENTE] - Relato de los Hechos.pdf`, `[APELLIDO CLIENTE] - Convenio Honorarios.pdf`, `[APELLIDO CLIENTE] - Formulario SRT Anexo [N].pdf`, `[APELLIDO CLIENTE] - Telegrama.pdf`.
4. Los .docx intermedios no van a la carpeta del cliente — son solo un paso para llegar al PDF. Borralos o dejalos en tu carpeta de trabajo temporal, no en "ESTUDIO JURIDICO". Fijate bien de copiar únicamente los archivos de este cliente — no copies de más ni le mezcles archivos de otro caso que tengas abierto en la misma carpeta de trabajo temporal.

Si no tenés acceso a la carpeta "ESTUDIO JURIDICO" en esa sesión, pedísela a Santiago antes de este paso en vez de asumir una ruta.

## Paso 5: entrega

Confirmale a Santiago en una sola frase dónde quedaron guardados los PDF (carpeta del cliente dentro de `1) ART`) y qué datos quedaron como placeholder sin completar, si los hay. No hace falta un resumen largo de todo lo que se generó — Santiago ya sabe lo que pidió.

La documental del caso (recibos de sueldo, estudios médicos, DNI, etc.) no la generás vos — Santiago la adjunta aparte. Si te la pasa, usala solo para sacar datos (fechas, diagnósticos, domicilios) que completen los documentos de arriba. No hace falta que la guardes en la carpeta del cliente vos mismo, salvo que Santiago te lo pida explícitamente.
