# Estado del proyecto — Asistente Jurídico (Estudio Segovia)

> **Este documento es un MAPA, no la fuente de verdad.**
> La fuente de verdad es **`SPEC_CIRCUITO_v0.2.md`** (las decisiones cerradas
> D1–D26 y los criterios de aceptación por fase), y **la lista de pendientes son
> sus `- [ ]`**.
>
> **Reescrito el 24/09/2026.** La versión anterior era del *12/08/2026* y su
> "próximo paso sugerido" era cerrar **Meta Jurídico** — que había salido del
> circuito el 16/09/2026 (spec D1) y cuyo módulo ya no importa nadie. También
> listaba un `PRIMERA_CORRIDA_MONITOR.md` que no existe en el repo y contaba
> 33 tests cuando hoy hay 259. Si algo de acá choca con la spec, manda la spec.

---

## 1. Qué es, en una frase

Un sistema **100% local** (no depende de Claude para operar) que genera cédulas,
las firma en FirmAr y las presenta en el SISFE — automatizando todo lo mecánico
y **frenando siempre** en los actos que tiene que hacer una persona.

---

## 2. Arquitectura (5 capas)

| Capa | Archivos | Rol |
|---|---|---|
| Dashboard | `asistente_juridico.html` | Panel de control. Funciona con servidor (datos reales) o solo (modo demo). |
| Servidor local | `servidor.py` | FastAPI. Orquesta firma y subida en segundo plano, pausa humana por HTTP, y sirve el PDF real de cada cédula (`/api/cedula/<id>/pdf`). |
| Generación (sin IA) | `generar_cedula.py` + `cedulas.py`, `cedulas_pdf.py`, `cedula_desde_texto.py`, `expediente_utils.py`, `extraccion_decretos.py` | Arma el PDF y clasifica el tipo de cédula por reglas. |
| Lectura de SISFE | `monitor_playwright.py` | Detecta decretos nuevos y dispara la generación. |
| Firma | `firma.py` | Automatiza FirmAr hasta donde se puede; dos puertas humanas. Individual y **en lote**. |
| Presentación | `sisfe_notificar.py` | Sube la cédula **firmada** al SISFE: busca por CUIJ, verifica, describe, adjunta y tilda Partes. **No notifica**: el clic final es de Santiago. |
| *(dormido)* | `meta_juridico.py` | Salió del circuito el 16/09/2026 (spec D1). El módulo queda guardado, **no se importa desde ningún lado** (lo congela `tests/test_circuito_sin_meta.py`). |
| Compartido | `_navegador.py`, `estado.py`, `sesion.py`, `acciones.py`, `config.py`, `config_portales.py` | Motor de navegador, registro de cédulas, jornada/identidad, despacho de acciones, configuración. |

---

## 3. Las puertas humanas (no se tocan)

| Dónde | Qué hace la persona | Por qué no se automatiza |
|---|---|---|
| SISFE (lectura y cédula) | reCAPTCHA | Seguridad del acceso matriculado |
| FirmAr | CUIL + contraseña + OTP + PIN + clic en FIRMAR | Es la firma digital, con responsabilidad civil |
| SISFE (cédula) | Clic final en **NOTIFICAR** | Acto irreversible, confirmación de Santiago |
| Gmail | Enviar el borrador | El sistema **nunca** manda: siempre deja borrador |

En el medio, el sistema automatiza lo que puede: adjuntar el PDF en FirmAr,
descargar el firmado, buscar el expediente en el SISFE por CUIJ, verificar que
sea el mismo (carátula + CUIJ), escribir la descripción, adjuntar la cédula
firmada y leer y tildar las Partes.

**Meta Jurídico ya no está en este circuito** (se sacó el 16/09/2026, spec D1).

### Cómo llega la puerta a la persona: hay dos vías, y no son equivalentes

| Vía | Cómo se ve | Cuándo funciona |
|---|---|---|
| **Panel** (HTTP) | el panel muestra el cartel y el botón «Ya está, continuar» destraba el trabajo (`POST /api/continuar/<job_id>`) | siempre |
| **Consola** (`input()`) | el script imprime el pedido y espera un **ENTER en la consola que lo lanzó** | **solo si el servidor tiene consola** |

La puerta de «Subir al SISFE» (`notificar_sisfe`) va **por el panel**:
`sisfe_notificar.subir(..., pausar=pausar)`. La de **apertura de cuenta judicial
(`cuenta`) todavía va por consola**: `skills/apertura-cuenta-judicial-banco-municipal/
scripts/apertura_cuenta_judicial.py` llama a `pausa_humana()`, que es un `input()`
(línea 58), y `acciones.py` lo lanza con `Popen` **sin `stdin=`** (línea 48), así que
el hijo hereda el stdin del servidor.

Consecuencia, verificada el 14/10/2026: si el servidor **no tiene consola** —por
ejemplo si se lo levantó como proceso de fondo, o desde un shell no interactivo—
ese `input()` no espera. Muere en el acto:

```
hijo: esperando ENTER >>> Traceback ...
EOFError: EOF when reading a line
codigo de salida: 1
```

Y el navegador del SISFE no queda abierto: el script abre Chrome con el perfil
`chrome_profile_sisfe`, y en la primera puerta (login pendiente, o un selector
que no encontró) el `input()` lo mata. Se ve como «el SISFE no abre».

Prueba de que **no** se había lanzado: el 14/10 el perfil `chrome_profile_sisfe`
tenía **0 archivos tocados**, con último uso el **16/09/2026**. El script no había
corrido ni una vez ese día.

Para abrirlo a mano (y que el ENTER sí aparezca), en **una consola propia**:

```bash
cd ~/asistente_juridico
python "skills/apertura-cuenta-judicial-banco-municipal/scripts/apertura_cuenta_judicial.py" \
       --cuij 21-00000001-0 --out "$LOCALAPPDATA/Temp/cuenta"
```

---

## 4. Qué está validado, y cómo se sabe

Marcas: **[CÓDIGO]** = verificable en el repo · **[DOC]** = figura como corrida
real en los documentos, sin evidencia en el repo.

| Tramo | Estado | Evidencia |
|---|---|---|
| Dashboard dual (servidor / demo offline) | ✅ [CÓDIGO] | `asistente_juridico.html` |
| Servidor + pausa humana por HTTP | ✅ [CÓDIGO] | `servidor.py`; la pausa se ve en las pruebas de firma y SISFE |
| Persistencia y ciclo de vida | ✅ [CÓDIGO] | `estado.py` + `tests/test_estado.py` |
| Generación de cédulas sin IA (clasificación, multi-destinatario, peritos, Bus Federal) | ✅ [CÓDIGO] | `tests/test_cedula_completa.py`, `tests/test_destinatarios.py` |
| Visor del PDF en el panel | ✅ [CÓDIGO] | `/api/cedula/<id>/pdf` + `tests/test_servidor_pdf.py` (el navegador no elige la ruta) |
| **Firma individual en FirmAr** | ✅ [DOC] | Circuito real completo corrido por Santiago con la cédula `PRUEBA TECNICA` (`prueba_tecnica.json`). |
| **Firma en lote** | ⚠️ | Existe y está wireada (`firma.py`, `/api/firmar_lote`), pero **nunca se corrió contra FirmAr real**: toda la evidencia es contra dummies. |
| **Subir la cédula firmada al SISFE** | ⚠️ | Construido y cubierto por tests contra una pantalla de mentira (incluido el que verifica que **no** aprieta NOTIFICAR). **Falta la pasada en vivo**: los 5 selectores. |
| Monitor de SISFE | ⚠️ | Estructura lista; los selectores del login están marcados `⬅ VALIDAR` porque no se accedió al portal. |
| Corrida sostenida del monitor (una jornada) | ⚠️ | La lógica de horario tiene tests; nunca una corrida real sostenida. |
| Capa de mail (código) | ✅ [CÓDIGO] | `mail_gmail.py` **sin** función de envío; `/api/mail/bandeja` y `/api/mail/borradores`. |
| Capa de mail contra la casilla del estudio | ❌ | Se probó contra una casilla de prueba. Falta autorizar la del estudio. |
| Suite de pruebas | ✅ [CÓDIGO] | `python -m pytest tests/ -q` → **259 passing, 0 skipped** |
| Arranque en un clic y portable | ✅ [DOC] | `Iniciar_Asistente.bat` con rutas dinámicas |

---

## 5. Qué falta

No se repite acá: **son los `- [ ]` de `SPEC_CIRCUITO_v0.2.md`**. En corto:

1. **La pasada en vivo del SISFE** (Fase 6): confirmar 5 selectores.
2. **Firma en lote con documentos reales.**
3. **Selectores del monitor** (10 marcas `⬅ VALIDAR` en el repo).
4. **Corrida sostenida del monitor** una jornada (Fase 8).
5. **Casilla de Gmail del estudio.**
6. **Fase 10b (el hub)**: el contrato del almacén, el anti-duplicado central y
   la ficha del cliente. Hoy `estado.py` no tiene ningún control de duplicados:
   solo deduplica por `id` local.
7. **Decisión pendiente:** elegir la identidad del lote desde el panel.
8. **La puerta de «Apertura de cuenta judicial» sigue en la consola.** Es la única
   acción del SISFE que no se migró al panel: su pausa es un `input()`. Con el
   servidor sin consola esa puerta no se puede contestar (verificado: `EOFError`,
   salida 1) y el SISFE no queda abierto — ver §3. Dos cosas que hacer:
   pasarle el `pausar` del panel igual que `notificar_sisfe`, y **partir el cartel
   en dos y en orden**: primero «voy a abrir el SISFE, apretá continuar», después
   «iniciá sesión y avisame». Hoy dice las dos cosas juntas y al revés: manda a
   iniciar sesión *en la ventana* cuando la ventana recién se abre **después** de
   apretar el botón (`acciones.py`, el `pausar(...)` está antes del `_correr(cmd)`).
9. **El dato de demo de `fernandez_000003` corta el tramo del SISFE.** Su
   `ruta_firmada` es `C:/demo/FIRMADO.pdf`, que **no existe** (`C:/demo/` no
   existe), así que «Subir al SISFE» se frena antes de abrir nada:

   ```
   status : error
   error  : No encuentro el PDF firmado en el disco: C:/demo/FIRMADO.pdf
   ```

   Reproducido el 14/10/2026 contra el endpoint real. Es la **única** cédula que
   hoy ofrece ese botón (las demás no están en estado `firmada`), así que el tramo
   no se puede mostrar de punta a punta. Hacer coherente el dato: o un PDF de
   mentira que exista de verdad, o que la cédula de demo no figure como firmada.

---

## 6. Cómo verificar sin portal

`python -m pytest tests/ -q`. Es lo único que se puede comprobar sin SISFE,
FirmAr ni credenciales. Las pruebas que necesitan Chromium se saltean solas si
no está instalado (`python -m playwright install chromium`); **conviene tenerlo**,
porque entre esas está el blindaje de D17 (que el flujo no apriete NOTIFICAR).

---

## 7. Qué documento manda para qué

| Documento | Para qué sirve | Estado |
|---|---|---|
| `SPEC_CIRCUITO_v0.2.md` | **Fuente de verdad**: decisiones y criterios por fase. **Los pendientes son sus `- [ ]`** | vigente |
| `INSTALACION.md` | Dejar el asistente andando en una **máquina nueva** (la de Santiago, o cualquier otra) | vigente (14/10/2026) |
| `GUION_DEMO.md` | El recorrido para mostrarlo: paso a paso, qué decir, qué no tocar | vigente (14/10/2026) |
| `HANDOFF.md` | Cómo está armado todo, tramo por tramo, y qué no se pudo verificar | vigente (corregido el 24/09/2026) |
| `ESTADO_DEL_PROYECTO.md` | Este mapa | reescrito el 24/09/2026 |
| `PENDIENTES.feature.md` | Registro de qué se pidió y por qué | **snapshot viejo** (commit `beb7f72`, 25 commits atrás): no es la lista de pendientes |
| `ADDONS.md` | Roadmap comercial (bot, Docker, licencias) | roadmap, **no** estado del repo |
| `SPEC_CIRCUITO_v0.1.md` | Revisión previa, con las preguntas abiertas de entonces | histórico |
| `tests/README.md` | Qué se prueba sin portal y qué necesita portal | vigente |

---

## 8. Datos y privacidad (regla del 24/09/2026)

- **El repo está en PRIVADO.** Adentro hay (en el historial de git) datos de
  causas reales: nombres de partes, CUIJ, un DNI, dos CBU y domicilios de
  peritos. El árbol ya se limpió; **el historial no**. Si algún día vuelve a ser
  público, hay que reescribir el historial, no alcanza con el árbol.
- **Nunca se suben** (y `.gitignore` lo cubre): `config.py`, `estado.json`,
  `estado_expedientes.json`, `cedulas_procesadas.json`, `log_acciones.jsonl`,
  `sesion.json`, `cedulas_temp/`, `PDFs_decretos/`, `ExpedientesDigitales/`,
  `chrome_profile_sisfe/`, `chrome_profile_portales/` y `.hermes/`.
- **Los ejemplos del repo son ficticios**: carátulas, CUIJ, CUIT, DNIs, CBU,
  partes y correos. Los abogados del estudio, los jueces y las matrículas sí
  aparecen con su valor real: son la identidad funcional del documento (un
  poder tiene que nombrar a quién se le confiere), no datos de clientes.
