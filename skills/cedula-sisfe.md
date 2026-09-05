---
name: "cedula-sisfe"
description: "Genera cédulas de notificación para el fuero laboral de Santa Fe (Poder Judicial de Santa Fe / SISFE) a partir de un decreto o sentencia. En el secretario Hermes, este flujo usa el motor del repo (cedulas_pdf.py + cedula_desde_texto.py) y las partes se leen del SISFE con el Playwright del repo (monitor_playwright.py / _navegador.py). Tipos: audiencia art. 51 CPL, decreto común, ley 22.172 / Bus Federal. Si el texto es una SENTENCIA, se recorta a encabezado + […] + parte resolutiva (regla portada de la skill original). Usar cuando Santiago pegue un decreto/sentencia y pida 'hacer la cédula', 'notificar', 'cédula ley 22.172', 'bus federal', 'audiencia 51', o cuando el monitor deje un pendiente."
---

# Cédulas SISFE — flujo del secretario (migrado al repo)

Esta skill reemplaza a la skill de Claude del mismo nombre. La lógica de
generación ya vivía en el repo (`cedulas.py` + `cedulas_pdf.py` + 
`generar_cedula.py`); esta migración aportó lo que faltaba
(`cedula_desde_texto.py`): el recorte de sentencias, el parseo del texto
pegado y el nombre de archivo de Santiago. **Ya no hay dos implementaciones
de las mismas reglas.**

## Piezas (todo en el repo)

| Pieza | Rol |
|---|---|
| `cedula_desde_texto.py` | NUEVO (migrado): `es_sentencia()`, `recortar_sentencia()`, `extraer_caratula()`, `extraer_cuij()`, `extraer_fecha_decreto()`, `nombre_archivo_santiago()` |
| `cedulas_pdf.py` | Genera los 3 PDF: estándar (común), audiencia 51, Bus Federal |
| `cedulas.py` | Reglas: mero trámite, Cajas, destinatarios, `es_decreto_audiencia_51`, `es_bus_federal` |
| `generar_cedula.py` | `clasificar_por_reglas()` → tipo sugerido; `generar()` → PDF + registro en estado.json |
| `monitor_playwright.py` / `_navegador.py` | Leen SISFE (partes, verificación carátula/CUIJ) — reemplazan a "Claude in Chrome" |
| `skills/juzgados_rosario.json` | Biblioteca de juez/secretario por juzgado (44 de Rosario) — reemplaza a `references/juzgados.md` |

## Flujo

1. **Entrada**: texto de un decreto o sentencia pegado por Santiago, o un
   pendiente del monitor (que ya trae `texto_decreto` estructurado).
2. **Parsear** con `cedula_desde_texto`: carátula, CUIJ, fecha, juzgado.
3. **¿Es sentencia?** `es_sentencia(texto)` → sí: `recortar_sentencia()`
   = encabezado (autos) + `[…]` + parte resolutiva completa. Nunca se
   transcribe una sentencia entera en la cédula.
4. **Tipo sugerido**: `generar_cedula.clasificar_por_reglas(texto)` →
   `aud51` / `bus_federal` / `estandar` (común). Se muestra como sugerencia;
   **Santiago confirma** (decisión humana, con el texto a la vista).
5. **Partes**: desde SISFE con Playwright (pantalla "Nueva Cédula" →
   tabla PARTES), o pegadas por Santiago si no hay sesión. Verificar
   SIEMPRE que carátula + CUIJ coincidan antes de usar las partes.
6. **Destinatarios**: Santiago elige (multiSelect). Domicilio: por defecto
   "DOMICILIO DIGITAL - SISFE" para representantes; domicilio físico para
   peritos (cédula a perito rechaza SISFE/DIGITAL); ART/demandadas/Cajas/
   Provincia desde `juzgados_rosario.json` o el decreto.
7. **Generar**: un PDF por destinatario con `generar_cedula.generar()` y
   nombre `Cédula a {DESTINATARIO} decreto fecha {DD-MM-AA}.pdf`
   (`nombre_archivo_santiago`). Peso < 3 MB (límite SISFE).
8. **Entregar**: los PDF en el dashboard + una línea por cédula.

## Reglas de negocio que NO cambiar (heredadas)

- Formato de PDF: texto justificado, títulos centrados (lo hace el motor).
- Sentencia → recorte con […] (regla de Santiago).
- Avisar (no corregir en silencio) si Santiago corrige el texto de un
  modelo — hay que actualizar la plantilla en el repo.
- El domicilio de la cédula es "DOMICILIO DIGITAL - SISFE" salvo
  excepciones documentadas (peritos: físico obligatorio; Bus Federal:
  destinatario en blanco para completar).

## Pendiente de validación

Validar contra un caso real con Santiago: un decreto común, una audiencia
51, una sentencia (verificar el recorte) y un Bus Federal, comparando con
cédulas que él ya presentó.
