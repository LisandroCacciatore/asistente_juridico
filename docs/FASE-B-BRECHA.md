# Fase B — Brecha técnica

Estado: **evaluación, no implementación.** Nada de lo que sigue está construido.
Este documento existe para decidir antes de escribir código.

## Épica 0 — estado de las decisiones

| Decisión | Estado | Efecto |
|---|---|---|
| **Quién puede pedir firmar y presentar** | ✅ **Cerrada**: sólo el dueño de la cédula. El administrador ve pero **no pide en nombre de otro** | Épica 8: el botón no aparece en cédulas ajenas, ni para el admin |
| **Dónde vive el portal** | ✅ **Cerrada**: en la máquina del estudio, expuesto con Tailscale. **VPS descartado** | Épica 9: portal y asistente comparten la cola local; no hace falta canal de red |
| **Dónde está el token de cada firmante** | ⛔ **ABIERTA** | Bloquea la épica 4. Si el token no está en la máquina del estudio, la firma remota cambia de diseño |
| **Qué pasa cuando un trabajo se traba** | ⛔ **ABIERTA** (parcial) | El panel con el estado ya está definido; falta si **además** avisa por correo |

Las dos abiertas se preguntan antes de empezar la épica 4. Las cerradas no se
vuelven a discutir.

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
