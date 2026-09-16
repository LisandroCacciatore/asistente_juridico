# Formularios SRT — Anexos I, II, III y IV (Res. SRT N° 5/2026)

Los 4 Anexos son PDF oficiales **editables** (tienen campos de formulario reales, no son imágenes). Los blancos están guardados en `assets/`:

- `assets/ANEXO_I_divergencia_incapacidad.pdf`
- `assets/ANEXO_II_rechazo_accidente_trabajo.pdf`
- `assets/ANEXO_III_rechazo_enfermedad_profesional.pdf`
- `assets/ANEXO_IV_prestaciones.pdf` (IF-2026-09572607-APN-SRT#MCH)

Los **cuatro** son los vigentes y obligatorios desde la Res. SRT 5/2026 (BORA 29/01/2026, vigente desde el 02/02/2026), que sustituyó el punto 19 del Anexo de la Res. 179/15.

**No los recrees como tabla en un .docx.** Usá el script `scripts/fill_srt_form.py`, que rellena el PDF oficial real sobre sus propios campos y conserva el diseño oficial (encabezados azules, logo SRT, paginado, etc.) tal cual lo vería un empleado de la SRT.

## Elegir el Anexo correcto

| Situación | Anexo |
|---|---|
| La ART rechazó (o no respondió) la denuncia de un accidente de trabajo | II — Rechazo de accidente de trabajo |
| La ART rechazó (o no respondió) la denuncia de una enfermedad profesional | III — Rechazo de enfermedad profesional |
| El caso ya fue aceptado por la ART pero se discute el % de incapacidad otorgado | I — Divergencia en la determinación de la incapacidad |
| Se pidió reingreso al tratamiento y la ART no respondió o lo denegó | IV — Prestaciones (motivo de solicitud: **Reingreso**) |
| El trabajador no está de acuerdo con el alta médica otorgada por la ART | IV — Prestaciones (motivo de solicitud: **Alta**) |
| El trabajador está en tratamiento y no está de acuerdo con las prestaciones | IV — Prestaciones (motivo de solicitud: **Prestaciones**) |

Ojo con el Anexo IV: además del bloque de datos, **siempre** hay que cargar `motivo_solicitud` (Alta / Reingreso / Prestaciones) — es lo que distingue los tres trámites. Y su sección "Opción de competencia" lleva la Comisión Médica (`comision_medica_n`), la jurisdicción y el fundamento del domicilio (`fundamento_domicilio`).

## Cómo usar el script

1. Armá un JSON con los datos del caso, usando las claves amigables documentadas en `scripts/fill_srt_form.py` (diccionario `FIELD_MAPS`, una sección por Anexo). No inventes valores para las claves que no tengas — simplemente omitilas del JSON y esos campos quedan en blanco en el PDF final (igual que en los otros documentos, avisale a Santiago al final qué quedó sin completar).
2. Corré:
   ```
   python scripts/fill_srt_form.py --anexo III --data datos_caso.json --out "[APELLIDO CLIENTE] - Formulario SRT Anexo III.pdf"
   ```
   (`--anexo` es `I`, `II`, `III` o `IV` según corresponda; ajustá el nombre del archivo de salida).
3. El resultado ya es el PDF final — no hace falta pasarlo por la conversión docx→PDF del Paso 4, porque nace como PDF. Guardalo directo en la carpeta del cliente.
4. Los campos de Sí/No y de opción múltiple (tipo de contingencia, fundamento de la opción de competencia, etc.) se completan con el texto visible de la opción ("Sí", "No", "Accidente de trabajo", "Domicilio", etc.) — el script traduce eso al estado interno del PDF. Si no tenés el dato para responder una de estas preguntas, no la incluyas en el JSON: queda sin marcar en el formulario, no marques una opción al azar.

## El PDF sale "aplanado" (y por qué)

Por defecto el script **aplana** el formulario: los valores quedan dibujados en la página. Si no, el PDF se ve **vacío** en Chrome y en cualquier visor que no regenere los campos por su cuenta — el dato está adentro (se lee con un lector de formularios) pero no se ve, y así no se puede presentar.

Si necesitás el formulario **editable** para corregir algo a mano, agregá `--editable`, pero revisá el PDF antes de presentarlo: en ese modo algunos visores no muestran los valores.

Las marcas de los círculos (Sí/No, motivo de solicitud, opción de competencia) se dibujan aparte, porque estos formularios traen los círculos sin una marca usable. Sin ese paso el formulario sale con **todos los círculos vacíos**.

## Por qué no alcanza con mirar el nombre de los campos

Algunos campos de estos PDF tienen un nombre interno que no coincide con la pregunta que está al lado (aparentemente un error de quien armó el formulario original). Esto ya está resuelto y documentado dentro de `fill_srt_form.py` — los mapeos fueron verificados rellenando cada campo con su propio nombre y revisando visualmente en qué casillero caía cada uno. No modifiques esos mapeos basándote en lo que "debería" decir el nombre del campo.

## Notas generales

- El campo de "Asistencia Letrada" siempre lleva los datos de Santiago (u otro abogado del estudio que patrocine ese caso puntual) — no del cliente.
- Los campos de texto libre (relato de tareas, diagnóstico, pruebas) se redactan en prosa a partir de lo que Santiago te haya contado del caso, con el mismo nivel de detalle que el relato de los hechos.
- La firma y aclaración del trabajador y del letrado se dejan en blanco — se firman a mano.
- Al entregar, recordale a Santiago que conviene verificar en www.argentina.gob.ar/srt que estos sean los formularios vigentes, por si la SRT los actualiza.
