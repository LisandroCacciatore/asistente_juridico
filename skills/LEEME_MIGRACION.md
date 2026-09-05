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

- cedula-sisfe: faltan references/juzgados.md, modelo-aud51.md, modelo-comun.md,
  modelo-ley22172.md, scripts/generar_cedula.py. → El repo YA tiene el
  equivalente en cedulas.py + cedulas_pdf.py (mismos 3 tipos + reglas).
  Decisión: unificar con el repo, no duplicar.
- cliente-art-nuevo: faltan references/poder-especial.md, relato-de-hechos.md,
  convenio-honorarios.md, formularios-srt.md, telegrama.md,
  scripts/fill_srt_form.py. → Material legal NO disponible en el repo.
  Pendiente: pedir a Claude/Santiago o reconstruir con Santiago.
- apertura-cuenta-judicial-banco-municipal: sin script (flujo de capturas +
  borrador Gmail). Migrable como flujo; la navegación SISFE pasa al motor
  Playwright del repo.

## Dependencia a reemplazar en la migración

Las skills usan "Claude in Chrome" (ToolSearch/tabs_context_mcp/computer) para
leer SISFE. En el secretario, eso se reemplaza por monitor_playwright.py /
_navegador.py (ya leen SISFE, buscan por CUIJ y leen partes). Gmail
(create_draft) → google-workspace (gws).
