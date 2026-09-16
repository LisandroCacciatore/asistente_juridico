# HANDOFF — Asistente Jurídico (Estudio Segovia)

**Repo:** `https://github.com/LisandroCacciatore/asistente_juridico` (privado)
**Commit de referencia:** `0140f77` — *"Suite de tests + fix carátula multilínea + pendientes en Gherkin"*
**Fecha de este handoff:** 16/09/2026

Este documento es lo que necesita alguien (persona o agente) para retomar el
proyecto sin depender de conversaciones previas.

> ## ⚠ AL DÍA AL 16/09/2026 — leer antes que el resto
>
> Este documento es un repaso al commit `0140f77` y **quedó atrás en dos cosas**:
>
> 1. **Meta Jurídico salió del circuito.** La cédula firmada va **directo al
>    SISFE**. Donde este documento diga que después de firmar se sube a Meta,
>    vale lo nuevo: `sisfe_notificar.py` (buscar por CUIJ → Nueva Cédula →
>    descripción → adjuntar la firmada → Partes → y **el clic en NOTIFICAR es
>    tuyo**). El módulo `meta_juridico.py` queda guardado, sin usar.
> 2. **Las cédulas son otras.** Los 4 tipos (común, peritos, Art. 51 y Bus
>    Federal) quedaron verificados contra cédulas reales del SISFE, y la común +
>    peritos + Art. 51 comparten una sola base.
>
> La fuente de verdad de todo esto es **`SPEC_CIRCUITO_v0.2.md`** (decisiones
> D1–D17 y las fases). Si algo de este handoff la contradice, gana la spec.

Cómo leer las afirmaciones:

- **[CÓDIGO]** — verificado leyendo el repo en el commit indicado
  (`git log`, `git ls-files`, lectura de los archivos).
- **[MEMORIA]** — viene de las conversaciones de desarrollo, no es
  verificable en el repo.
- **[A VERIFICAR]** — no lo pude confirmar; chequear antes de confiar.

## Lectura obligatoria antes de tocar nada

| Archivo | Por qué |
|---------|---------|
| `skills/LEEME_MIGRACION.md` | **[CÓDIGO]** Fuente de verdad de qué skill se migró y qué falta dentro de cada una. Dice 6/6 migradas, 4 con scripts verificados. |
| `PENDIENTES.feature.md` | **[CÓDIGO]** La lista de trabajo vigente, en Gherkin. Son **solo escenarios sin validar**, no dupliques lo ya hecho. |
| `ESTADO_DEL_PROYECTO.md` | **[CÓDIGO]** Mapa del sistema (capas, puertas humanas, qué está validado de verdad). Ojo: es un repaso **al 12/08/2026**, anterior a este commit. |
| `skills/*/SKILL.md` | **[CÓDIGO]** El procedimiento de cada skill. Es lo que Hermes recibe cuando corre una acción. |

No hay `README.md` en la raíz: este archivo cumple ese rol. Tampoco hay
`requirements.txt` (ver §7).

---

## 1. Qué es y qué no es

**[CÓDIGO + MEMORIA]** Sistema **local** para el estudio del Dr. Santiago
Segovia (Rosario, Santa Fe) que:

1. Lee **SISFE** y detecta decretos nuevos (`monitor_playwright.py`).
2. Genera las **cédulas** por reglas (`generar_cedula.py` + `cedulas.py`).
3. **Firma** en FirmAr (`firma.py`), incluyendo firma en lote.
4. **Presenta** en Meta Jurídico (`meta_juridico.py`).
5. Arma documentos del estudio a pedido (**skills**), y deja el mail
   **como borrador** para que el abogado lo mande con un clic.

**Qué NO es:**

- No es un SaaS ni un servicio desplegado: es una instalación por máquina.
- No es un programa que el cliente mantenga: el "secretario" corre y
  genera; el abogado aprueba.
- **[MEMORIA]** No incluye el Nivel 2 (VPS multi-abogado con sesiones
  remotas de portales y puertas humanas remotas). Eso es un proyecto
  aparte, no algo que esté acá a medio hacer.

### Sobre la IA (importante y fácil de malinterpretar)

**[CÓDIGO]** No hay un único "usa IA / no usa IA". Hay dos motores
distintos, y `acciones.py` lo documenta en su cabecera:

| Motor | Qué corre | Cuáles acciones |
|-------|-----------|-----------------|
| **local** — determinista, sin IA | Un script del repo | `cedula`, `cuenta` |
| **secretario** — Hermes interpreta | Hermes con el procedimiento de la skill, en proceso aparte y acotado | `art`, `boletas`, `raeo`, `transferencia` |

El **circuito principal** (monitor → cédula → firma → presentación) es
100% reglas de negocio, sin IA. Las **4 skills del secretario** sí usan
Hermes, y siempre con las puertas humanas intactas: prepara documentos,
**no firma, no presenta, no envía**.

---

## 2. Cómo entra en el día del estudio

**[CÓDIGO]** El dashboard (`asistente_juridico.html`) tiene estas secciones:

- Saludo/métricas derivadas del **estado real** (no valores fijos).
- **Listas para firmar** / **Listas para presentar** / **Presentadas**
  (estas últimas atenuadas, sin acción).
- **Pendientes de clasificar** (lo que el monitor detectó y falta tipificar).
- **Actividad del secretario** (últimas acciones del log).
- **Acciones del secretario**: 6 tarjetas.
- **Mail**: bandeja + borradores, con chip del adjunto.

### Las 6 acciones del panel y las 6 skills

**[CÓDIGO]** Las tarjetas del HTML (`onclick="accion('...')"`), el mapa
`ACCIONES` del propio HTML, y el dispatcher `ejecutar()` de `acciones.py`
coinciden en **seis** acciones. Cuatro corren Hermes; dos no:

| Acción | Skill | Motor | Corre |
|--------|-------|-------|-------|
| `cedula` | `cedula-sisfe` | local | `cedula_desde_texto.py` + `generar_cedula.py` |
| `cuenta` | `apertura-cuenta-judicial-banco-municipal` | local | `skills/.../apertura_cuenta_judicial.py` (Playwright) |
| `art` | `cliente-art-nuevo` | **Hermes** | — |
| `boletas` | `oficio-incumplimiento-boletas` | **Hermes** | — |
| `raeo` | `oficio-raeo` | **Hermes** | — |
| `transferencia` | `transferencia-de-capital` | **Hermes** | — |

Las 4 del motor secretario son exactamente las que `PENDIENTES.feature.md`
llama "las 4 skills del secretario" (`_SKILLS_SECRETARIO` en `acciones.py`,
línea 177).

### La regla del mail

**[CÓDIGO]** `mail_gmail.py` línea 9: *"Regla del secretario: SIEMPRE
borradores, nunca envío directo."* No existe función de envío, y el
servidor no expone ningún camino para mandar: el dashboard muestra
"Abrir en Gmail" y el envío es un acto del abogado.

---

## 3. Inventario de archivos

**[CÓDIGO]** Salida real de `git ls-files` en `0140f77`: **59 archivos**.
No es una lista de memoria.

### Núcleo del dashboard

| Archivo | Qué hace |
|---------|----------|
| `servidor.py` | FastAPI. Sirve el HTML y orquesta firma/subida/acciones en jobs con pausa humana por HTTP. 12 rutas (§3.1). |
| `asistente_juridico.html` | Dashboard de un solo archivo (~1.400 líneas). Funciona con servidor o en modo demo offline. |
| `Iniciar_Asistente.bat` | Arranque en un clic. |

### Generación de cédulas (sin IA)

| Archivo | Qué hace |
|---------|----------|
| `generar_cedula.py` | Arma la cédula y la registra en el estado. |
| `cedula_desde_texto.py` | Reglas puras sobre texto: `es_sentencia`, `recortar_sentencia`, `extraer_caratula/cuij/fecha/juzgado`, `nombre_archivo_santiago`. |
| `cedulas.py`, `cedulas_pdf.py` | Clasificación por reglas y armado del PDF. |
| `expediente_utils.py` | Rutas de expediente. **LEGACY**: sus claves se importan a nivel de módulo (si faltan, crashea todo). |
| `extraccion_decretos.py` | Extracción de decretos. |

### Portales

| Archivo | Qué hace |
|---------|----------|
| `monitor_playwright.py` | Lee SISFE, filtra (mero trámite, Cajas, "Notifíquese"), genera pendientes. Modo continuo con horario laboral. |
| `firma.py` | FirmAr: `firmar()` y `firmar_lote()`, con `_adjuntar_pdf`, `_descargar_firmado`, `_volver_a_firmar_documento`. |
| `meta_juridico.py` | Meta Jurídico: buscar expediente, adjuntar, subir. |
| `_navegador.py` | Chrome con perfil persistente + anti-huérfanos. |
| `config_portales.py` | URLs y selectores. Sin credenciales. |

### Estado y configuración

| Archivo | Qué hace |
|---------|----------|
| `estado.py` | Registro de cédulas/pendientes + log de acciones. Usa un `RLock` en `_mutar()`. |
| `config.example.py` | Plantilla de `config.py`. **Fuente de verdad de las claves** (§4). |
| `reset_registros.py` | Vacía los registros. |

### El secretario

| Archivo | Qué hace |
|---------|----------|
| `acciones.py` | Motor de las 6 acciones: motor local + motor secretario (Hermes). |
| `mail_gmail.py` | Capa de Gmail: borradores con adjunto. Subcomandos `search`, `read`, `draft`, `drafts`, `cuenta`. |

### Skills

**[CÓDIGO]** 6 skills migradas. Las sueltas son un `.md`; las que tienen
script propio son una carpeta con `SKILL.md` + `scripts/`.

```
skills/LEEME_MIGRACION.md          ← estado de la migración (leer primero)
skills/juzgados_rosario.json       ← 44 juzgados (ver §4, no lo lee nadie)
skills/cedula-sisfe.md
skills/oficio-raeo.md
skills/oficio-incumplimiento-boletas.md
skills/transferencia-de-capital.md
skills/apertura-cuenta-judicial-banco-municipal/
    SKILL.md + scripts/apertura_cuenta_judicial.py
skills/cliente-art-nuevo/
    SKILL.md
    assets/    ANEXO_I_…, ANEXO_II_…, ANEXO_III_…  (PDFs oficiales)
    references/ poder-especial, relato-de-hechos, convenio-honorarios,
                formularios-srt, telegrama  (5 archivos)
    scripts/   fill_srt_form.py
scripts/generar_oficio_raeo.py
scripts/generar_oficios_boletas.py
scripts/generar_transferencia.py
```

### Tests

**[CÓDIGO]** Existen y corren sin portal (creados en `0140f77`):

```
tests/README.md
tests/test_estado.py               (198 líneas)
tests/test_cedula_desde_texto.py   (157 líneas)
```

Cubren: ciclo de vida de la cédula, borrado del PDF al presentar (y que no
borra el de otra), log de acciones, concurrencia del `RLock`, y el parseo
de carátula/CUIJ/fecha/sentencia.

**[CÓDIGO]** Verificado al escribir este handoff:
`python -m pytest tests/ -q` → **33 pruebas, 33 pasan, en 0,46 s**, sin
portal ni login de nadie.

### Andamiaje de desarrollo (`dev/`)

**[CÓDIGO]** Versionado, pero **no es producto**: sirve para regenerar
previews y capturas.

| Archivo | Qué es |
|---------|--------|
| `dev/gen_rail_preview.js`, `dev/rail_preview.html` | Preview del riel de estados. |
| `dev/test_rail.js` | Verificación numérica del riel. Es la única prueba que existía antes de `tests/`. |
| `dev/shot.py` | Captura full-page (local o HTTP). |
| `dev/datos_cedula_demo.json`, `dev/datos_raeo_demo.json` | Datos de prueba para las acciones. |
| ~~`dev/exponer_skills_hermes.py`~~ | Era el mecanismo viejo para exponer skills a Hermes. **Borrado** (ver §7). |

### Otros

`ESTADO_DEL_PROYECTO.md`, `PENDIENTES.feature.md`,
`INSTRUCCIONES_PLAYWRIGHT.md`, `package.json` (resto de scaffold, sin uso),
`bloque_firma_lote.html` y `bloque_pendientes_clasificar.html` (snippets;
ver §7), `prueba_tecnica.json` y `gonzalez_prueba.json` (datos ficticios
de prueba).

### No versionado (a propósito)

`config.py`, `estado.json`, `cedulas_procesadas.json`,
`estado_expedientes.json`, `log_acciones.jsonl`, `cedulas_temp/`,
`chrome_profile_sisfe/`, `chrome_profile_portales/`, `.hermes/`.
Ver §8.

**Local, sin versionar:** `ADDONS.md` (roadmap de add-ons y precios,
13/09/2026) existe en la máquina de Lisandro pero **no está en el repo**.
Si se quiere que viaje, hay que commitearlo aparte.

### 3.1 Rutas del servidor

**[CÓDIGO]** `servidor.py`:

| Método | Ruta |
|--------|------|
| GET | `/`, `/api/cedulas`, `/api/log`, `/api/estado/{job_id}` |
| GET | `/api/mail/bandeja`, `/api/mail/borradores` |
| POST | `/api/generar_desde_pendiente`, `/api/firmar`, `/api/firmar_lote`, `/api/subir` |
| POST | `/api/continuar/{job_id}`, `/api/skill/{accion}` |

En `servidor.py:276` está la ruta real del motor de acciones
(`POST /api/skill/{accion}`) y en `servidor.py:249` está
`GET /api/estado/{job_id}`.

---

## 4. Configuración por máquina

**[CÓDIGO]** `config.py` **no está en el repo**. La plantilla es
`config.example.py`, y es la fuente de verdad de qué claves importa el
código: **no dupliques la lista acá, leé ese archivo**. Su cabecera ya
advierte: *"Todas las claves que el código importa están acá. Si falta
una, el sistema crashea al importar"*.

Cómo se usa:

```bash
copy config.example.py config.py
# y completar config.py con los datos reales
```

Grupos de claves, según `config.example.py`:

| Grupo | Claves |
|-------|--------|
| SISFE | `SISFE_USUARIO` (matrícula) |
| Registros | `ARCHIVO_REGISTRO`, `ARCHIVO_ESTADO`, `CARPETA_EXP_DIGITAL` |
| Modo continuo | `INTERVALO_MINUTOS`, `HORARIO_INICIO`, `HORARIO_FIN`, `DIAS_HABILES` |
| Cédulas | `CARPETA_CEDULAS_TEMP`, `FORMATO_SALIDA` |
| LEGACY (obligatorias) | `RUTA_ESTUDIO`, `RAMAS`, `CLASIFICACION` |
| Juzgados | `JUZGADOS` (clave `"FUERO N"`, ej. `"LABORAL 3"`) |
| Domicilios | `DOMICILIOS_ART`, `DESTINATARIOS_PROVINCIA_1ER_DECRETO` |

Cosas que se malinterpretan seguido:

1. **No existe ninguna clave de contraseña.** La plantilla dice, textual:
   *"Tu número de matrícula (solo eso; la contraseña se ingresa a mano)"*.
   Las contraseñas de los portales las escribe el abogado en el navegador.
2. **Las claves LEGACY no son opcionales.** `expediente_utils.py` las
   importa a nivel de módulo: si faltan, crashea **todo** el pipeline,
   aunque las cédulas nuevas no las usen.
3. **`JUZGADOS` viene vacío en la plantilla y hay una lista de 44 juzgados
   en `skills/juzgados_rosario.json`… que ningún `.py` lee.** O sea: para
   que la cédula salga con juez y secretario, hay que **copiar la lista a
   mano** en `config.py`. Es una duplicación real de la fuente de verdad
   (§7).
4. **`DIAS_NOVEDADES = "10"` no está en `config.py`**: está hardcodeado en
   `monitor_playwright.py:58`. Para cambiarlo hay que editar ese archivo.
5. **Hermes y Gmail son estado por máquina**, no config del repo: el token
   OAuth de la casilla vive fuera del repo (`~/AppData/Local/hermes/…`).
   Si falta o venció, el dashboard lo dice en castellano
   (`_error_mail()` en `servidor.py:291` traduce `invalid_grant` y
   "No hay token" a un mensaje accionable).

---

## 5. Decisiones de diseño

**[MEMORIA]** Salvo donde digo [CÓDIGO], son decisiones deliberadas.

### Las puertas humanas no se automatizan

| Dónde | Qué hace el abogado | Por qué |
|-------|---------------------|---------|
| SISFE | reCAPTCHA + contraseña | Acceso matriculado; el script no puede saltarlo |
| FirmAr | CUIL + contraseña + OTP + PIN + clic en FIRMAR | Es su firma digital, con su responsabilidad civil |
| Meta Jurídico | Login + código por mail (2FA) | 2FA por diseño |
| Meta Jurídico | Clic final en "Presentar" | Acto irreversible |

Entre esas puertas el sistema automatiza todo lo que puede: adjuntar en
FirmAr, descargar el firmado, buscar el expediente, adjuntar el archivo.

**Sobre el login de SISFE, para que no se lea como contradicción:** la
contraseña y el reCAPTCHA son **siempre** del abogado. Lo que persiste es
la *sesión* en el perfil de Chrome, así que en la práctica se loguea una
vez y el monitor trabaja con esa sesión hasta que el portal la vence; ahí
el monitor vuelve a pedir el login. El sistema no guarda ni automatiza la
credencial nunca.

### El mail siempre queda en borrador

**[CÓDIGO]** Decisión + regla escrita en el código y reflejada en la UI
("Abrir en Gmail", con la nota de que el envío es del abogado).

### Las skills son texto, y el procedimiento viaja en el pedido

**[CÓDIGO]** Las skills viven en `skills/` como texto (fuente de verdad
única). `acciones.py` lee el `SKILL.md` y lo mete **dentro** del pedido a
Hermes (`--query-file`, que no interpreta nada de shell) en lugar de
depender de que Hermes tenga la skill instalada. Así el procedimiento se
edita en el repo y no hay dos copias.

### La ejecución de Hermes está acotada

**[CÓDIGO]** `acciones.py:246` corre:
`hermes chat --query-file <pedido> -Q --in <repo> --max-turns 30
--run-budget 600`, con timeout de 700 s y **muerte del árbol completo de
procesos** (`taskkill /F /T /PID`) si se pasa. En Windows es crítico: si
se mata solo el padre, los nietos (node, Chrome de Playwright) sobreviven
y el job queda colgado.

### Perfiles de Chrome separados

**[MEMORIA]** `chrome_profile_sisfe` y `chrome_profile_portales` van
aparte del Chrome personal. Mezclarlos junta la sesión de firma con la
navegación personal y se pierde la aislación.

### `config.py` fuera del repo

**[MEMORIA]** Aunque no tenga contraseñas, tiene matrícula y estructura
de carpetas del estudio. Se prefirió no publicarlo.

---

## 6. Estado real, tramo por tramo

**[CÓDIGO]** ✅ = hay evidencia de corrida real contra el portal.
⚠️ = funciona la lógica, falta la corrida real. ❌ = no está.

| Tramo | Estado | Evidencia / por qué |
|-------|--------|---------------------|
| Generación de cédulas (reglas, multi-destinatario, clasificación) | ✅ | `ESTADO_DEL_PROYECTO.md` §4 + `tests/test_cedula_desde_texto.py` |
| Persistencia y ciclo de vida (`estado.py`) | ✅ | `ESTADO_DEL_PROYECTO.md` §4 + `tests/test_estado.py` |
| **Firma en FirmAr — cédula individual** | ✅ | `ESTADO_DEL_PROYECTO.md` §4: *"circuito real completo… Login → adjuntar → PIN+firmar → descarga automática. Funcionó de punta a punta"*, corrido por Santiago con la cédula `PRUEBA TECNICA` (`prueba_tecnica.json`). `ADDONS.md` lo repite. |
| **Firma en lote (`firmar_lote`)** | ❌ | Existe (`firma.py:139`, `/api/firmar_lote`) pero **toda la evidencia es contra dummies, nunca contra FirmAr real** (`PENDIENTES.feature.md`). |
| Búsqueda en Meta Jurídico | ⚠️ | Reescrita con la grabación real; probada con dummies que replican los dos casos. **Falta la confirmación en el portal real** (`ESTADO_DEL_PROYECTO.md` §4). |
| **Subida/presentación completa en Meta Jurídico** | ❌ | `ESTADO_DEL_PROYECTO.md` §5.1: *"es el único eslabón sin probar en el portal de verdad"*. Sin esto, el circuito principal no está cerrado. |
| Monitor de SISFE | ⚠️ | Estructura lista, pero los selectores del login (`#circunscripcion`, `#colegio`) están marcados `⬅ VALIDAR` (`PENDIENTES.feature.md`). |
| Modo continuo del monitor | ⚠️ | La lógica de horario se probó aislada (4 casos); nunca una corrida sostenida de una jornada. |
| Skill `raeo` (oficio RAEO vía Hermes) | ✅ (caso ficticio) | Corrida en la sesión de desarrollo: generó PDF de 3 páginas + Word + **borrador de Gmail con el Word adjunto**, y la bandeja de enviados quedó **vacía**. Evidencia en carpeta temporal, no versionada. |
| Skills `art`, `boletas`, `transferencia` | ⚠️ | Registradas y cableadas; no hay corrida real registrada. |
| Capa de mail (código) | ✅ | `mail_gmail.py` sin función de envío; `/api/mail/bandeja` y `/api/mail/borradores` responden. |
| Capa de mail **contra la casilla del estudio** | ❌ | Se probó contra **una casilla de Gmail de prueba**, no la del estudio. Falta autorizar la casilla real en la máquina de Santiago. |
| Tests sin portal | ✅ | `tests/` existe: `python -m pytest tests/ -q` → **33/33 en 0,46 s**, sin portal ni login. |
| Formularios SRT de `cliente-art-nuevo` | ✅ | Los **4** Anexos oficiales vigentes (Res. SRT 5/2026) presentes, con el mapeo de campos verificado (36/36, 37/37, 34/34 y 27/27). El **Anexo IV se agregó el 16/09/2026**, junto con el arreglo del bug que hacía que el PDF saliera vacío al abrirlo. |
| Dashboard (riel, listas, acciones, mail) | ✅ | Renderizado y verificado por captura; los GET traen datos reales. |

### Lo que falta para decir "funciona para el estudio"

En orden de impacto (`PENDIENTES.feature.md` prioriza los dos primeros):

1. **Presentación real en Meta Jurídico, de punta a punta** con un caso que
   exista de verdad en el portal. Es el tramo que cierra el circuito.
2. **Firma en lote con documentos reales** (dos cédulas en una sola sesión
   de FirmAr).
3. **Validar los selectores de SISFE** en el portal real y sacarles el
   `⬅ VALIDAR`.
4. **Autorizar la casilla de Gmail del estudio** en la máquina de Santiago.
5. **Corrida sostenida del monitor** durante una jornada.

---

## 7. Deuda técnica conocida

**[CÓDIGO]** Todo esto es verificable en el repo:

1. ✅ **`dev/exponer_skills_hermes.py` — BORRADO.** Generaba `.hermes/skills/`
   para que Hermes tuviera las skills instaladas, pero `acciones.py` ya no
   depende de eso: pasa el procedimiento dentro del pedido. Queda la carpeta
   `.hermes/` local (ignorada por git) por si alguien la regeneró a mano.
2. ✅ **La Feature de tests de `PENDIENTES.feature.md` — CORREGIDA.** Decía
   *"Suite de pruebas automatizada (no existe todavía)"* y que el único test
   era `dev/test_rail.js`. Ahora está marcada como hecha en `0140f77`, con
   el texto original conservado como registro.
3. **Los juzgados están duplicados.** `skills/juzgados_rosario.json` (44) y
   `config.JUZGADOS` son la misma información, y **ningún código lee el
   JSON**: se mantiene a mano en `config.py`. Van a divergir.
4. **Los snippets `bloque_firma_lote.html` y
   `bloque_pendientes_clasificar.html` traen instrucciones de "pegá esto
   en tu HTML"** y el dashboard ya tiene esas funciones adentro. Son una
   segunda versión de la misma UI: **[A VERIFICAR]** si todavía se usan
   para algo o son huérfanos.
5. ✅ **`requirements.txt` — AGREGADO.** Ya no hace falta leer este documento para
   instalar: `python -m pip install -r requirements.txt`. Además
   `preparar_maquina.py` crea el `config.py` con la matrícula y avisa si falta
   instalar algo o si Hermes no está en el PATH.
6. **`package.json`** es resto de un scaffold de Node/Playwright, sin uso
   aparente.
7. **`_error_mail()` traduce bien los errores de Gmail**, pero ese camino
   nunca se probó con un token realmente vencido (solo se leyó el código).

---

## 8. Seguridad y datos

**Nunca se suben al repo** (y `.gitignore` lo cubre): `config.py`,
`estado.json`, `estado_expedientes.json`, `cedulas_procesadas.json`,
`log_acciones.jsonl`, `cedulas_temp/`, `PDFs_decretos/`,
`ExpedientesDigitales/`, `chrome_profile_sisfe/`,
`chrome_profile_portales/`, y `.hermes/`.

Verificación antes de commitear:

```bash
git status --short          # que no aparezca nada de la lista de arriba
git ls-files | grep -iE "config\.py|estado\.json|log_acciones|chrome_profile"
```

**[CÓDIGO]** En este commit la verificación da limpio: `config.py`,
`estado.json` y `log_acciones.jsonl` existen en disco y **no** están
trackeados.

Reglas que se sostienen:

- **Las contraseñas de los portales no se guardan en el código ni se pasan
  por ningún chat**: las escribe el abogado en el navegador. (Por eso no
  hay clave de contraseña en `config.example.py`.)
- **El token OAuth de Gmail vive fuera del repo**, en el perfil de Hermes
  de esa máquina, y es de una sola casilla.
- **Los datos de prueba del repo son ficticios a propósito**: `prueba_tecnica.json`
  y `gonzalez_prueba.json` dicen "PRUEBA TÉCNICA" / "ART EJEMPLO" y su
  texto aclara que no son decretos reales y no deben presentarse. Usalos
  como molde, no como datos reales.
- **Los tests no tocan `estado.json` real**: usan `monkeypatch` para
  redirigir los archivos a una carpeta temporal (`tests/README.md`).

---

## 9. El flujo del abogado

**[MEMORIA + CÓDIGO]** Lo que ve Santiago:

1. Se loguea en SISFE (contraseña + reCAPTCHA). Es su acto; la sesión
   después persiste en el perfil de Chrome.
2. El monitor lee SISFE y trae los decretos nuevos fuera del horario
   laboral no hace nada.
3. El dashboard muestra los decretos en **Pendientes de clasificar**.
4. Confirma o cambia el tipo sugerido.
5. El sistema genera la cédula y la pone en **Listas para firmar**.
6. Abre FirmAr, se loguea, y el sistema **adjunta el PDF**; él pone PIN y
   firma. Puede firmar varias en una ventana (**firmar en lote**).
7. El sistema **descarga el firmado** y la cédula pasa a **Listas para presentar**.
8. Abre Meta Jurídico, se loguea (2FA), y el sistema busca el expediente y
   adjunta el archivo.
9. Él revisa y aprieta **Presentar**.
10. La cédula queda **Presentada** y el PDF temporal se borra.
11. Todo queda en `log_acciones.jsonl` y se ve en **Actividad del secretario**.

Para las **acciones del secretario** (oficios, transferencia, alta de ART,
cédula pegada a mano):

1. Pide la acción desde el panel de **Acciones**.
2. Si la acción abre un portal (cuenta judicial), el dashboard pausa y le
   pide que se loguee; después aprieta **"Ya está, continuar"**.
3. El secretario arma los documentos (puede tardar minutos).
4. Deja los archivos en una carpeta temporal y **el mail como borrador**.
5. Él abre Gmail, revisa y **envía con un clic**. El sistema nunca manda.

---

## 10. Cómo arrancar

**[CÓDIGO]** Las dependencias están en `requirements.txt`:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium      # el navegador propio de Playwright
```

Después, en una máquina nueva:

```bash
python preparar_maquina.py --matricula <TU MATRÍCULA>   # crea config.py
python servidor.py                                      # levanta en 127.0.0.1:8000
# abrir http://localhost:8000 EN CHROME (no en el pane de Hermes: ese webview
# bloquea los POST y los botones no funcionan)
```

Para correr los tests, sin portales ni login:

```bash
python -m pytest tests/ -v
```

**[MEMORIA]** Hermes tiene que estar instalado en la máquina para las 4
acciones del motor secretario (`acciones.py` lo llama como
`hermes chat …`). **[A VERIFICAR]** el comando de instalación actual y los
flags vigentes: los que usa el código están citados en §5, pero conviene
confirmarlos contra la versión instalada.

---

## 11. Lo que no pude verificar

- Si el **token de Gmail del estudio** está autorizado en la máquina de
  Santiago (acá solo se probó con una casilla de prueba).
- Si el **perfil de Chrome** tiene una sesión viva de SISFE.
- La **lista real de `JUZGADOS`** en la `config.py` de Santiago, y si
  coincide con `skills/juzgados_rosario.json`.
- El **comando y los flags vigentes de Hermes** (los del código están en §5).
- La **versión de Python** objetivo (hay `requirements.txt`, pero ningún
  `.python-version`; se probó con 3.11).
- Si `bloque_firma_lote.html` y `bloque_pendientes_clasificar.html` siguen
  teniendo algún uso.
- Si `package.json` es basura reciclable.
- **[MEMORIA]** El `ADDONS.md` local menciona sprints, precios y add-ons
  (bot de Telegram, Docker, backup). Eso es **roadmap**, no estado del
  repo: nada de eso está implementado acá.

## 12. Notas para quien siga

- **No dupliques trabajo ya hecho:** la migración de skills está completa
  (`LEEME_MIGRACION.md`) y el dashboard con mail y panel de acciones ya
  está hecho. `PENDIENTES.feature.md` es solo lo que falta validar.
- **Para agregar una skill:** `skills/<nombre>/SKILL.md` (o
  `skills/<nombre>.md`) + registrarla en `_SKILLS_SECRETARIO` o en el
  dispatcher de `acciones.py`, y la tarjeta en `ACCIONES` del HTML.
- **Para cambiar firma o presentación:** `firma.py` / `meta_juridico.py`.
- **Para cambiar selectores de portales:** `config_portales.py` (y
  `monitor_playwright.py` para SISFE).
- **Antes de dar algo por bueno, corré `python -m pytest tests/ -v`**: es
  lo único verificable sin portal.

---

*Escrito el 16/09/2026 contra el commit `0140f77` de `main`. Todo cambio
posterior a esa fecha no está reflejado acá.*
