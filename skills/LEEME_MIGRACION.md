# Migración de skills — estado

Fuente: export de la cuenta Claude de Santiago (Downloads/files, 2026-09).
Destino: este repo (skills/ + scripts ejecutables del secretario Hermes).

## Migradas (completas, script embebido verificado)

| Skill | Script | Notas |
|---|---|---|
| oficio-incumplimiento-boletas | scripts/generar_oficios_boletas.py | 3 oficios (Colegio + 2 Cajas) + borradores Gmail |
| oficio-raeo | scripts/generar_oficio_raeo.py | PDF oficio+escrito cargo; +Word/mail si Laboral N°5 |
| transferencia-de-capital | scripts/generar_transferencia.py | 2 opciones (escritos / completo) |

Datos compartidos extraídos: juzgados_rosario.json (44 juzgados: Laboral 1-10,
Civil 1-22, Familia 1-12 — compatible con config.JUZGADOS del formato
"FUERO N" → juez/cargo_juez/secretario/cargo_secretario).

## Incompletas (faltan referencias del export)

- ~~cedula-sisfe~~ → **UNIFICADA al repo** (2026-09): las reglas que
  faltaban se portaron a `cedula_desde_texto.py` (es_sentencia,
  recortar_sentencia, extraer_caratula/cuij/fecha, nombre_archivo_santiago)
  y la skill quedó documentada en skills/cedula-sisfe.md apuntando al motor
  del repo (cedulas_pdf.py + Playwright). Ya no hay dos implementaciones.
- ~~cliente-art-nuevo~~ → **COMPLETA** (2026-09): SKILL.md + 5 references
  (poder-especial, relato-de-hechos, convenio-honorarios, formularios-srt,
  telegrama) + scripts/fill_srt_form.py + **assets/ con los 4 Anexos SRT
  oficiales** descargados de argentina.gob.ar. Verificación automática de los
  mapeos de campos: los PDFs contienen exactamente las claves del FIELD_MAPS
  (36/36, 37/37, 34/34 y 27/27 para el Anexo IV).
  **Anexo IV agregado el 16/09/2026** (era el que faltaba): la Res. SRT 5/2026
  (BORA 29/01/2026, vigente desde el 02/02/2026) establece CUATRO formularios
  obligatorios — I, II, III y IV (IF-2026-09572607-APN-SRT#MCH, "Prestaciones":
  reingreso al tratamiento / divergencia con el alta médica / divergencia con
  las prestaciones). Su mapeo (27 campos) se verificó por geometría —rect de
  cada campo contra la caja de cada texto del formulario— y mirando el render.
  **Bug encontrado y arreglado en fill_srt_form.py**: el script dejaba los
  valores en /V pero no los dibujaba, así que el formulario salía **VACÍO** al
  abrirlo en Chrome o cualquier visor que no regenere los campos (afectaba a
  los 4 anexos, no solo al IV). Ahora aplana por defecto (`--editable` para el
  modo anterior) y además dibuja el punto de la opción elegida en los radios,
  que antes salían todos vacíos. Verificado por render y por conteo de píxeles:
  los 4 anexos muestran los valores y la marca cae en la opción correcta.
- ~~apertura-cuenta-judicial-banco-municipal~~ → **MIGRADA a Playwright**
  (2026-09): skills/apertura-cuenta-judicial-banco-municipal/ con SKILL.md +
  scripts/apertura_cuenta_judicial.py (usa el perfil Chrome del monitor,
  busca por CUIJ, 2 capturas, PDF con reportlab — test de armado PASS).
  Selectores del buscador SISFE ⬅ VALIDAR en vivo. El borrador Gmail lo
  arma la capa secretario (google-workspace) — nunca envía solo.

## Resumen de la migración

6/6 skills de Claude → repo. 4 con scripts ejecutables verificados
(compilan + tests donde aplica), cedula-sisfe unificada al motor del repo,
apertura-cuenta con flujo Playwright listo para validar en vivo. La
dependencia "Claude in Chrome" quedó reemplazada por el Playwright del repo;
el conector de Gmail por google-workspace (integración del secretario, Fase 1).

## Dependencia a reemplazar en la migración

Las skills usan "Claude in Chrome" (ToolSearch/tabs_context_mcp/computer) para
leer SISFE. En el secretario, eso se reemplaza por monitor_playwright.py /
_navegador.py (ya leen SISFE, buscan por CUIJ y leen partes). Gmail
(create_draft) → google-workspace (gws).
