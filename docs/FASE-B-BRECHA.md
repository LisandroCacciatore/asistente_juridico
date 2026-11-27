# Fase B — Brecha técnica

Estado: **épicas 1 a 3 construidas y con tests; 4 a 9 en pausa.** Lo que sigue
describe el diseño completo; al final está la constancia de qué está hecho.

## Decisión del estudio — 26/11/2026

Santiago confirmó: **cada persona instala el asistente en su propia PC** y
trabaja con lo suyo (su SISFE, su FirmAr, su token), igual que hoy en la máquina
del estudio.

- **No hay portal central de sincronización.**
- **No hay carpeta compartida.**
- **No hay escritorio remoto.**
- Revisable más adelante, **sólo si Santiago pide ver el estado de los tres en un
  solo lugar**.

### Qué significa para las épicas

| Épicas | Estado |
|---|---|
| 1 · Autenticación | ✅ hecha |
| 2 · Lista cerrada | ✅ hecha |
| 3 · Cola persistente | ✅ hecha (integración incluida) |
| **4 a 9** | ⏸️ **en pausa por decisión del estudio** |
| Sincronización central | ❌ **descartada por ahora** |

Lo construido **no se borra**: las épicas 1 a 3 son independientes del modelo de
instalación y sirven igual con un asistente por PC.

### Qué cambia para la Fase A

El portal **no desaparece**: queda para quien lo use en la máquina del estudio y
sigue leyendo el `estado.json` local de esa máquina.

```
Santiago (máquina del estudio)  -> asistente + portal + su estado.json
Jr (su PC)                      -> asistente propio + su estado.json
Socio (su PC)                   -> asistente propio + su estado.json
```

No hay vista consolidada. Cada instalación ve lo suyo. El portal **no** lee los
estados de las otras PCs, y no hay que construirlo salvo que Santiago lo pida.

## Épica 0 — estado de las decisiones

| Decisión | Estado | Efecto |
|---|---|---|
| **Quién puede pedir firmar y presentar** | ✅ **Cerrada**: sólo el dueño de la cédula. El administrador ve pero **no pide en nombre de otro** | Épica 8: el botón no aparece en cédulas ajenas, ni para el admin |
| **Dónde vive el portal** | ✅ **Cerrada**: en la máquina del estudio, expuesto con Tailscale. **VPS descartado** | Épica 9: portal y asistente comparten la cola local; no hace falta canal de red |
| **Dónde está el token de cada firmante** | 🟡 **DISEÑO PROPUESTO, pendiente de Santiago**: cada uno tiene el suyo (FirmAr). El asistente sólo firma por quien está físicamente en la máquina del estudio; Jr y el Socio firman en su máquina y suben el PDF al portal | Épica 4 **no se implementa** hasta que Santiago lo confirme y la cola esté integrada |
| **Qué pasa cuando un trabajo se traba** | 🟡 **PROPUESTA, pendiente de Santiago**: panel visible + correo al dueño; el administrador lo ve en el panel. **No es decisión tomada** | Épica 3 y 8 avanzan sobre la propuesta, sin darla por cerrada |

Las dos abiertas se preguntan antes de empezar la épica 4. Las cerradas no se
vuelven a discutir.

**Aviso sobre el estado de las decisiones:** una propuesta de quien revisa **no
es** una decisión de Santiago. La fila marcada 🟡 sigue siendo propuesta hasta
que él responda; la épica 3 puede implementarla, pero no se da por cerrada ni se
presenta como acordada.

## Constancia de avance

| Épica | Estado | Evidencia |
|---|---|---|
| 1 · Autenticación del asistente | ✅ **Implementada** (rama `faseb/epica-1-auth`) | 12 tests en `tests/test_faseb_auth_asistente.py`; suite **496** en verde |

**Qué se encontró en la épica 1:** el escenario "pedido desde una página web
ajena" **ya estaba cubierto** por el middleware `_proteger_csrf` de `servidor.py`
(rechaza con 403 si el `Origin` no coincide con el `Host`). Lo que faltaba era el
**token compartido**, que ahora:

- se lee de `config.py` (`TOKEN_ASISTENTE`, fuera del repo);
- se exige en los `POST` de acción (`/api/firmar`, `/api/firmar_lote`,
  `/api/skill/`, `/api/continuar/`), no en las lecturas;
- responde **401** con `{"ok": false, "error": "Credencial invalida"}` —nunca
  repite el token— y deja el rechazo en el log;
- se inyecta en el HTML del dashboard al servir la página, y el dashboard lo
  manda en cada `fetch`. Un sitio de otro origen no puede leer ese HTML.

**Alcance real del token (corregido):** protege del **navegador y de otros
hosts**, no de un proceso local. `GET /` entrega el token sin credencial, así que
cualquier proceso del mismo usuario puede leerlo —igual que puede leer
`config.py`—. Un proceso local malicioso queda **fuera de alcance**: para eso
haría falta otra cosa (usuario de SO distinto, o pedir el token en el arranque).

**Cierre del DNS rebinding:** `_proteger_csrf` comparaba `Origin` contra `Host`;
un dominio que resuelve a `127.0.0.1` manda ambos iguales y pasaba. Ahora hay
`HOSTS_PERMITIDOS` (`127.0.0.1`, `localhost`, `::1`, más los de
`config.HOSTS_ASISTENTE` para Tailscale) y un middleware `_validar_host` que
responde **403** a cualquier otro host, también en `GET /`.

**POST cubiertos:** se exige token en **todos** los POST salvo `POSTS_SIN_TOKEN`
(hoy vacío). Los POST actuales: `/api/sesion`, `/api/generar_desde_pendiente`,
`/api/firmar`, `/api/firmar_lote`, `/api/destinatarios`,
`/api/continuar/{job_id}`, `/api/skill/{accion}`.

**Modo compatible:** si `TOKEN_ASISTENTE` está vacío, el servidor no exige nada
y **avisa al arrancar** (consola y log). La épica **no está cerrada** hasta
activarlo:

1. Generar el valor sin imprimirlo.
2. Guardarlo en `config.py` (`TOKEN_ASISTENTE = "..."`).
3. Reiniciar el asistente.
4. Verificar: un POST sin token responde 401 y el dashboard sigue funcionando.

Sin datos de clientes: no hay nombres, CUIJ ni rutas de expedientes.

---

## 1. Qué es la Fase B

Hoy hay dos mundos que no se hablan:

| Pieza | Dónde corre | Qué hace |
|---|---|---|
| `servidor.py` (agente local) | Máquina del estudio | Genera, **firma** (FirmAr vía Playwright) y **presenta** en SISFE |
| `portal/` | Servidor del portal | Ve novedades, recibe el PDF firmado, permisos y auditoría |

La Fase B es que el portal pueda **pedir** esos trabajos: que un abogado
disponga desde el navegador "firmá estas cédulas" o "presentá esta", y que el
trabajo se ejecute en la máquina del estudio, con trazabilidad.

## 2. Restricción dura

**El agente debe quedar en la máquina del estudio.** Necesita:

- los perfiles de Chrome con las sesiones de SISFE y FirmAr de cada persona
  (`sesion.perfil_de`),
- el token / 2FA de firma, que es físico o personal.

Eso no se puede mover a un servidor en la nube. Consecuencia arquitectónica:
el portal puede vivir en otro lado, pero **el agente siempre es local**, y hoy
escucha en `127.0.0.1:8000`.

## 3. Qué existe hoy (base sobre la que se apoyaría)

```
POST /api/firmar              un documento
POST /api/firmar_lote         varios, una sola ventana de FirmAr
POST /api/skill/{accion}      acciones del secretario (incluye presentar)
GET  /api/estado/{job_id}     estado del trabajo
POST /api/continuar/{job_id}  destraba la pausa humana (token / 2FA)
```

Más: `JOBS` en memoria, `threading.Event` para la pausa, `perfil_en_uso` para
no abrir dos Chrome con el mismo perfil, y `verificar_cadena` para D25.

## 4. Reglas de diseño (no negociables)

1. **Lista cerrada de acciones.** El portal solo puede pedir dos cosas:
   `firmar_lote` (con una lista de ids de cédula) y `presentar` (un id). Nada
   de acciones libres ni de pasar nombres de función: si no está en la lista,
   no existe.
2. **La identidad la verifica el agente contra su propia configuración.** El
   portal manda un `persona_id`; el agente **no lo usa como verdad**: lo
   resuelve contra `config.PERSONAS`, toma el perfil de Chrome de esa persona y
   aplica `verificar_cadena` sobre cada cédula. Si no coincide, frena el
   trabajo entero. El portal no puede "declarar" una identidad que el agente no
   reconozca.
3. **Confirmación humana final en la máquina del estudio.** La pausa de
   FirmAr y el token **se destraban en la máquina donde corre Playwright**, no
   desde el portal. El portal puede mostrar "esperando confirmación", pero el
   acto lo hace una persona frente a esa máquina. Esto es lo que impide que un
   portal comprometido firme solo.
4. **Autenticación del agente, primero.** Antes de cualquier otra cosa: el
   agente tiene que poder distinguir un pedido del portal de cualquier otro
   proceso. Hoy no valida nada y asume localhost.

## 5. Brechas, en el orden en que hay que atacarlas

| # | Brecha | Detalle | Días |
|---|---|---|---|
| 1 | **Autenticación del agente** | `servidor.py` no valida origen ni credencial: cualquier proceso local puede pedir una presentación. Token compartido con HMAC del cuerpo, o mTLS | 0,5–1 |
| 2 | **Canal portal → agente** | El agente está detrás de una IP privada. Recomendado: el agente hace *polling* saliente al portal y retira trabajos. Alternativa: Tailscale entre portal y agente | 1–2 |
| 3 | **Identidad por trabajo** | `identidad_para_el_acto()` es global al proceso ("la de la jornada"). Cada trabajo tiene que llevar su `persona_id` explícito y el agente resolverlo contra su config | 1 |
| 4 | **Cola persistente** | `JOBS` es un dict en memoria: un reinicio del agente pierde el trabajo y la pausa. Estados en disco: `pendiente`, `corriendo`, `esperando_humano`, `listo`, `error` | 1–2 |
| 5 | **Un perfil a la vez** | `perfil_en_uso` impide dos Chrome del mismo perfil, pero no hay cola: dos pedidos simultáneos se pisan. Encolar por perfil, no por persona | 1 |
| 6 | **La pausa dirigida** | Hoy el botón "continuar" vive en el dashboard local y no valida quién lo aprieta. Tiene que saber a quién espera y rechazar a cualquier otro | 1–2 |
| 7 | **Estado compartido** | El portal lee `estado.json`, que escribe el agente. En máquinas distintas no ve la firma en tiempo real: el portal consulta al agente, o el estado se muda a una base común | 1 |
| 8 | **Idempotencia** | Dos clics pueden encolar dos presentaciones. Hoy solo protege `estado != generada`, y se evalúa después de encolar. Lock por cédula antes de encolar | 0,5 |
| 9 | **UI y auditoría del portal** | Botones "firmar" y "presentar", estado del trabajo en vivo, y que el pedido y el resultado queden en `auditoria` | 1–2 |

**Total estimado: ~1 semana de desarrollo**, más las pruebas con SISFE real
que necesitan a las personas con sus tokens, en una ventana acordada.

## 6. Lo que la Fase B no resuelve

**El acto de firmar.** El token y el 2FA son de cada firmante. La Fase B
automatiza el orden, la cola y la trazabilidad; no reemplaza a la persona
frente a la máquina. Es un flujo **asistido**, no desatendido. Cualquier
promesa de "firma automática" sin token es falsa.

## 7. Precondiciones

1. **Decisión de hosting.** Si el portal va a un servidor y el agente queda
   local, el canal es *polling* saliente. Si algún día el estudio acepta un
   servidor propio con acceso a los Chrome, cambia.
2. **Un solo servidor manda.** `servidor.py` y `portal/servidor_portal.py`
   exponen endpoints solapados (`/api/cedulas`, `/api/log`, `/api/sesion`).
   Antes de sumar un tercer camino hay que decidir cuál es el dueño de cada
   dato.
3. **Cola y pausa rediseñadas.** Son el corazón de la fase. Sin eso, lo demás
   es cosmético.

## 8. Fuera de alcance

- Bot de WhatsApp y criterios de urgencia (postergados por decisión).
- Instancia propia de n8n (depende de la decisión de hosting).
- Validación criptográfica de la firma (pyHanko), que es un tema aparte del
  portal y no del agente.

## Pendientes de Santiago (no decididos)

Ninguno de los dos está decidido. Quedan como preguntas abiertas.

1. **El correo cuando un trabajo se traba.** Sin portal central, no hay un solo
   lugar que avise: hay que definir **quién manda el correo desde cada PC** (la
   propia persona, o una casilla del estudio). Hoy el trabajo trabado se ve en el
   panel de esa máquina, y nada más.
2. **Una vista consolidada de los tres.** No se construye. Queda como posibilidad
   si Santiago pide ver el estado de los tres en un solo lugar; en ese momento se
   retoma el diseño de sincronización, que hoy está descartado.
