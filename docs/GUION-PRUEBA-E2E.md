# Guion de prueba de punta a punta — Fase A

Para hacer solo, sin datos de clientes y **sin presentar nada en SISFE**.

---

## Antes de empezar

- **Asistente** (dashboard de la máquina): `Iniciar_Asistente.bat`. Es el que navega SISFE.
- **Portal**: `Iniciar_Portal.bat` → `http://127.0.0.1:8100`.
- **Token de firma** a mano: el paso de FirmAr lo pide.
- Tiempo estimado: 15 minutos.

> **El guion termina antes de "Presentar".** Ese botón carga la cédula en el SISFE
> de verdad, sobre un expediente real. No se aprieta como parte de esta prueba.

---

## El dato que ordena los pasos

**La firma del asistente marca la cédula como "firmada" por sí sola.**
Está en `servidor.py` (`POST /api/firmar` → `estado.marcar_firmada`, y lo mismo en
`firmar_lote`). Y el portal **solo acepta cédulas en estado "generada"**
(`POST /api/portal/cedulas/{id}/subir` responde 409 si ya está firmada).

Consecuencia: si firmás con el **botón** del asistente, la cédula pasa a
"firmada" y **el portal rechaza el PDF**. Son dos caminos alternativos, no
consecutivos:

| Camino | Quién firma | Quién recibe el PDF |
|---|---|---|
| **A** (este guion) | FirmAr **por fuera** del asistente | el **portal** |
| **B** | el asistente (botón *Firmar*) | nadie: el asistente ya guarda el firmado |

En el camino A la cédula sigue "generada" hasta que subís el PDF al portal, y
ahí queda "firmada" con la ruta que guarda el portal — que es la que el
asistente va a usar si algún día presentás.

---

## Tramo 1 — Asistente: traer la novedad

| | |
|---|---|
| **Dónde** | Dashboard del asistente |
| **Qué hacés** | Pedir novedades / actualizar |
| **Qué deberías ver** | Una o más novedades con su decreto |
| **¿Toca SISFE?** | **Sí, sólo lectura.** Navega y descarga. No modifica nada |

## Tramo 2 — Asistente: generar la cédula

| | |
|---|---|
| **Dónde** | Dashboard, sobre la novedad |
| **Qué hacés** | Generar la cédula |
| **Qué deberías ver** | La cédula en estado **"generada"**, con su PDF |
| **¿Toca SISFE?** | No |

Anotá el **id de la cédula** que muestra el panel: lo vas a buscar en el portal.

## Tramo 3 — Firmar con FirmAr (por fuera del asistente)

| | |
|---|---|
| **Dónde** | FirmAr, con tu token |
| **Qué hacés** | Abrir el PDF **generado** (no el que el asistente llama "firmado"), firmarlo y descargarlo |
| **Qué deberías ver** | Un PDF nuevo, firmado, con más peso que el original |
| **¿Toca SISFE?** | No |
| **Ojo** | **No uses el botón "Firmar" del asistente.** Si lo usás, la cédula pasa a "firmada" y el portal la rechaza |

## Tramo 4 — Portal: subir el firmado

| | |
|---|---|
| **Dónde** | `http://127.0.0.1:8100`, con tu usuario |
| **Qué hacés** | Buscar la cédula por su id → *Subir firmado* → elegir el PDF que descargaste de FirmAr |
| **Qué deberías ver** | La fila pasa a **"firmada"** y aparece **"Descargar firmado"**. Si algo falla, el mensaje sale en la misma página, arriba de la tabla |
| **¿Toca SISFE?** | No |

Si aparece `La cédula no está en estado 'generada'`, firmaste con el asistente:
volvé al Tramo 2 con otra cédula.

## Tramo 5 — Portal: descargar

| | |
|---|---|
| **Dónde** | Misma fila, enlace *Descargar firmado* |
| **Qué hacés** | Descargar |
| **Qué deberías ver** | Un PDF que abre bien y **es el firmado**, no el original |
| **¿Toca SISFE?** | No |

## Tramo 6 — Asistente: confirmar que la ve firmada

| | |
|---|---|
| **Dónde** | Dashboard del asistente |
| **Qué hacés** | Refrescar y mirar esa cédula |
| **Qué deberías ver** | Estado **"firmada"**, y el archivo asociado es el que subiste por el portal |
| **¿Toca SISFE?** | No |

**No aprietes "Presentar".** El guion termina acá.

---

## Qué toca SISFE de verdad

| Acción | SISFE |
|---|---|
| Traer novedades | **Sí — lectura** |
| Generar cédula | No |
| Firmar con FirmAr | No (es otro portal) |
| Subir al portal | No |
| Descargar del portal | No |
| **Presentar (`notificar_sisfe`)** | **Sí — escritura real** |

---

## Si algún día se quiere probar la presentación

**No hay modo de prueba ni dry-run** en el presentador: `notificar_sisfe` carga
el documento y tilda las partes en el expediente. Verificado en el código, no es
suposición.

Opciones, de la más segura a la menos:

1. **No presentar.** Ya está cubierto por tests el camino crítico: que el
   asistente tome `ruta_firmada` y **nunca** `ruta_pdf` cuando no hay firma
   (`acciones.py`: si no hay firmado, corta con "firmala primero").
2. **Un expediente del propio estudio**, donde una cédula de prueba sea
   inocua. Lo decide Santiago, no el sistema: no hay nada en el código que
   distinga un expediente de prueba de uno real.
3. **Una causa de cliente**: no.

---

## Si algo falla

| Mensaje | Causa |
|---|---|
| `La cédula no está en estado 'generada'` | Se firmó con el asistente; usar otra cédula y firmar por fuera |
| `El PDF no tiene una firma digital válida` | El PDF no se firmó, o FirmAr no terminó de guardarlo |
| `El CUIJ de la cédula no aparece en el texto del PDF` | El PDF es un escaneo sin capa de texto |
| `El archivo no empieza con la cabecera PDF (%PDF-)` | Se subió otra cosa, o el archivo se corrompió al copiarlo |
| `No existe la cédula '<id>'` | El id no coincide, o esa cédula no es de tu identidad |
