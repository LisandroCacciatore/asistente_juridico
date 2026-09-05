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
  telegrama) + scripts/fill_srt_form.py + **assets/ con los 3 Anexos SRT
  oficiales descargados de argentina.gob.ar**. Verificación automática:
  los 3 PDFs contienen exactamente los campos del FIELD_MAPS del script
  (36/36, 37/37, 34/34) → el mapeo verificado visualmente por Claude es
  compatible con los formularios oficiales vigentes. Test funcional PASS
  (Anexo III rellenado y leído de vuelta). OJO: los formularios SRT se
  actualizan (Res. 5/2026) — validar vigencia con Santiago antes de uso
  real.
- apertura-cuenta-judicial-banco-municipal: sin script (flujo de capturas +
  borrador Gmail). Migrable como flujo; la navegación SISFE pasa al motor
  Playwright del repo.

## Dependencia a reemplazar en la migración

Las skills usan "Claude in Chrome" (ToolSearch/tabs_context_mcp/computer) para
leer SISFE. En el secretario, eso se reemplaza por monitor_playwright.py /
_navegador.py (ya leen SISFE, buscan por CUIJ y leen partes). Gmail
(create_draft) → google-workspace (gws).
