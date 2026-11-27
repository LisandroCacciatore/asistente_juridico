# Fase B local — plan (sin construir)

**Estado (27/11): aprobado con cuatro ajustes, ya aplicados acá.**
Arranque limitado a las épicas 0 y 1, y la 0 **espera el OK de Lisandro** por la
prueba del dashboard con el token activo.

Propuesta de Lisandro (27/11): un asistente y un portal **en la misma PC**, que se
hablan por `127.0.0.1`. Sin canal de red, sin portal central, sin sincronización
entre PCs.

## 1. ¿Es viable?

**Sí, con dos condiciones y tres contradicciones que hay que resolver antes.**

Lo que ya sirve hoy:

- El asistente escucha en `127.0.0.1:8000` y valida `TOKEN_PORTAL`.
- `estado.py` arma las rutas desde `__file__`, así que portal y asistente comparten
  `estado.json` si están en la misma carpeta.
- La pausa de FirmAr ya existe (`pausar()` + `POST /api/continuar/{job_id}`).
- El flujo de presentar ya está en `acciones.ejecutar("notificar_sisfe")`.

## 2. Las tres contradicciones

### 2.1 `ACCIONES_PORTAL` mezcla una ruta con una acción (bug de diseño)

Hoy la lista cerrada es `{"firmar_lote", "presentar"}`. Pero:

```
resolver("firmar_lote")            -> "firmar_lote"
acciones.ejecutar("firmar_lote")   -> AccionError: Acción desconocida
```

Porque `firmar_lote` es un **endpoint propio** (`POST /api/firmar_lote`), no una
acción de `/api/skill`. La épica 2 valida que `firmar_lote` **pase** el filtro,
pero al ejecutarlo falla. El test no lo detectó porque sólo mira el status de la
validación, no la ejecución.

**Propuesta:** que la lista cerrada sea de **acciones de negocio** y haya un solo
punto de entrada para el portal:

```
POST /api/faseb/pedido   { "accion": "traer_novedades" | "generar" | "firmar" | "presentar" }
```

El asistente resuelve la acción a su handler interno. Así la lista cerrada es
legible y no depende de cómo se llame la ruta.

### 2.2 `traer_novedades` no existe como acción disparable

El monitor (`monitor_playwright.py`) corre por su cuenta, con su propio horario.
**No hay endpoint ni acción** para pedirle "traé lo nuevo ahora". Hay que construir
ese disparador; hoy no se puede tocar desde el portal.

### 2.3 El portal no tiene cliente del asistente

El portal nunca le habló al asistente: sólo lee archivos. Para este marco hace
falta un cliente HTTP chico (con `TOKEN_PORTAL`) y manejar errores de red.

## 3. Lista cerrada ampliada

```
ACCIONES_PORTAL = {
    "traer_novedades",   # solo lectura de SISFE
    "generar",           # arma el PDF de la cédula
    "firmar",            # abre FirmAr y pausa
    "presentar",         # sube a SISFE (la más delicada)
}
```

Criterio igual al de la épica 2: si no está en el conjunto, el asistente responde
400 y **no ejecuta nada**. Cada acción declara además:

| Acción | Toca SISFE | Pausa humana | Reversible |
|---|---|---|---|
| `traer_novedades` | lectura | no | sí |
| `generar` | no | no | sí |
| `firmar` | no (FirmAr local) | **sí** (token) | no |
| `presentar` | **escritura** | **sí** (confirmación) | **no** |

### El punto único: `POST /api/faseb/pedido`

Un solo endpoint para todo lo que pide el portal. **La lista cerrada se aplica
adentro**, no antes, y el endpoint exige:

1. **`TOKEN_PORTAL`** (no sirve `TOKEN_ASISTENTE`).
2. **Host permitido** (la validación de DNS rebinding).
3. **Acción en la lista**, o 400 sin ejecutar nada.

Tres tests obligatorios, uno por cada barrera:

| Test | Espera |
|---|---|
| pedido sin token | 401 |
| pedido con `Host` ajeno | 403 |
| acción fuera de la lista | 400 |

### `traer_novedades`: de a uno y con freno

Es la única acción que toca SISFE en lectura, y el monitor hoy corre por horario
propio. Reglas:

- **Un solo trabajo de lectura por vez**: si ya hay uno corriendo, el segundo
  pedido se rechaza (409), no se encola.
- **Tiempo mínimo entre pedidos** (propuesto: 5 minutos). Un pedido antes del
  plazo se rechaza con el tiempo que falta.
- El freno se guarda en disco, para que un reinicio no lo reinicie.

### Reintento tras un trabajo `dudoso`

**Manual, siempre.** La persona revisa en SISFE si la acción ya entró y recién
entonces decide. **Nunca automático.** El sistema no reintenta nada por su
cuenta: sólo marca y avisa.

### Modo ensayo: siempre visible

Mientras el ensayo está activado:

- **Un cartel fijo en pantalla** en el portal, que no se puede tapar ni olvidar.
- **Cada trabajo de ensayo queda en la auditoría** con la marca, incluso los que
  terminaron bien.

El riesgo no es técnico: es que alguien crea que presentó cuando sólo hizo el
ensayo. El cartel y la auditoría existen para que eso no pueda pasar.

## 4. Orden de épicas (de menor a mayor riesgo)

Coincido con tu orden. Cada una es una rama y un PR.

| # | Épica | Qué toca | Prueba que la cubre | Qué puede salir mal | Días |
|---|---|---|---|---|---|
| 0 | Portal en la instalación real | `config.py` real, `portal.db`, cuentas | login, panel, subida de un PDF de prueba | `PORTAL_COOKIE_SEGURA` mal puesto deja el login inservible | 1 |
| 1 | `traer_novedades` | endpoint nuevo + disparador del monitor | doble de `monitor_playwright`, sin SISFE | que el monitor no soporte un disparo puntual | 2 |
| 2 | `generar` | acción + endpoint `/api/generar_desde_pendiente` | cédula generada con datos de prueba | que genere dos veces la misma | 2 |
| 3 | `firmar` desde el portal | cliente del portal + `/api/firmar_lote` + pausa y continuar | pausa simulada, sin FirmAr real | que dos pedidos abran el mismo perfil | 3 |
| 4 | `presentar` | idempotencia, modo ensayo, confirmación | doble de `sisfe_notificar`, nunca SISFE | presentación doble o a medias | 4 |
| 5 | Auditoría unificada | cruce por id de trabajo | pedido y ejecución con el mismo id | registros que no se correlacionan | 2 |

**Total: ~14 días de trabajo de Hermes**, que en calendario son **≈3 semanas**:
la épica 4 necesita una ventana de prueba real con Santiago y Jr, y esa ventana
manda el ritmo, no el código.

**Arranque: sólo épicas 0 y 1.** Nada más hasta que las dos estén revisadas.
Y la épica 0 no empieza hasta que Lisandro confirme la prueba del dashboard con
el token activo.

## 5. Identidad: una persona por PC

Con este marco la identidad deja de ser un problema:

- `config.PERSONAS` de esa PC tiene **una sola persona**.
- El portal tiene **una sola cuenta** (la misma persona).
- El agente resuelve la identidad contra su propia configuración, como ya hace
  (`verificar_cadena`), y no hay forma de pedir por otro porque no existe otro.
- Si una cédula no es de esa identidad, el agente la rechaza.

**Lo que hay que cambiar: nada de código.** La Fase A está construida y
verificada con el bypass de lectura de `es_administrador`, y no se toca lo que
funciona. Para una PC de una sola persona alcanza con configuración:

```python
PORTAL_ADMINISTRADORES = []      # nadie es admin: cada uno ve sólo lo suyo
```

Con la lista vacía, `es_administrador` devuelve `False` para todos y el bypass
nunca se activa. El concepto de administrador sigue existiendo para la máquina
del estudio, donde sí tiene sentido.

## 6. Preguntas para Santiago (propuestas, NO decisiones)

1. **¿Quién confirma "presentar"?** La persona frente a la PC, o el dueño de la
   cédula aunque no esté sentado ahí. *Propuesta: quien está frente a la PC.*
2. **¿Se firma de a una o en lote?** Hoy existe `firmar_lote`. *Propuesta: lote,
   porque es lo que hace hoy a mano.*
3. **¿El modo ensayo queda siempre disponible** o sólo se habilita en la ventana
   de prueba. *Propuesta: siempre disponible, con marca visible en la auditoría.*
4. **Después de un trabajo "dudoso", ¿cuántos reintentos manuales?** *Propuesta:
   uno, y el segundo exige revisar SISFE primero.*
5. **¿La vista conjunta (CSV/resumen) la manda cada PC o la junta Lisandro?**
   *Propuesta: la manda cada PC al Drive del estudio.*

## 7. Rollback documentado

Lisandro arrancó el asistente real con el token activo, pero **todavía no hizo una
lectura ni una firma real**.

Si algo falla:

1. Dejar `TOKEN_ASISTENTE` y `TOKEN_PORTAL` **vacíos** en el `config.py` de esa PC.
2. Reiniciar el asistente.
3. Con los tokens vacíos el servidor no exige credencial y vuelve al
   comportamiento anterior, sin tocar nada más.
4. El backup `config-REAL.bak-20261127-2124` está en `C:\Users\Torso\work\`.

No hay que revertir código: el modo compatible está pensado para eso.

## 8. Lo que NO entra

- Portal central o sincronización entre PCs (descartado por el estudio).
- Que el asistente se mude a la nube.
- Presentar sin confirmación humana.
- Bot de WhatsApp y criterios de urgencia.
