# Portal del estudio — Pasos 1a y 1b (base, login y servidor)

> **Estado:** Pasos 1a y 1b. Ya existen `portal/db.py`, `portal/auth.py`,
> `portal/permisos.py`, `portal/servidor_portal.py`, `portal_admin.py` e
> `Iniciar_Portal.bat`: base SQLite, login/sesiones, permisos, servidor HTTP
> y panel mínimo. La fuente de verdad del circuito sigue siendo
> `SPEC_CIRCUITO_v0.2.md` (D18–D25 y Fase 10b).

## Qué es el portal

El portal es el panel que se sirve desde el **hub** (Fase 10b): login real
(D23), estado/log centralizados (D21) y anti-duplicado central (D22). No
reemplaza al servidor local ni a Chrome: los perfiles de Chrome, las
sesiones de los portales, la firma y la generación de PDF siguen en cada
máquina (D21). El hub es un **almacén**, no el lugar donde se opera.

## Qué deja preparado el Paso 0

| Archivo | Para qué |
|---|---|
| `config.example.py` | `persona_id` estable por persona + claves `PORTAL_*` |
| `requirements.txt` | `argon2-cffi`, `python-multipart` y `filelock` |
| `.gitignore` | `portal.db`, `portal_uploads/` y secretos del portal |
| `reset_registros.py` | Vacía los registros **conservando los pendientes** |
| `tests/test_reset_registros.py` | Prueba de que los pendientes sobreviven |
| `docs/PORTAL.md` | Este documento |

## Configuración: `persona_id`

Cada entrada de `PERSONAS` en `config.example.py` tiene ahora un
`persona_id` (slug) **estable**:

| Nombre visible | `persona_id` |
|---|---|
| Santiago | `santiago` |
| Jr | `jr` |
| Socio | `socio` |

El `persona_id` es la clave con la que la base del portal y el log
identifican a la persona. **No se cambia** aunque cambie el nombre que se
muestra: si "Socio" pasa a tener nombre real, se actualizan la clave de
`PERSONAS` y el nombre, pero el `persona_id` sigue siendo `socio`. Así los
registros viejos no quedan huérfanos.

## Configuración: claves `PORTAL_*`

Todas viven en `config.py` (que no se sube). `config.example.py` trae los
valores de ejemplo.

| Clave | Default | Qué es |
|---|---|---|
| `PORTAL_DB` | `<carpeta>/portal.db` | Base SQLite del hub |
| `PORTAL_UPLOADS` | `<carpeta>/portal_uploads` | Carpeta de PDFs subidos |
| `PORTAL_HOST` | `127.0.0.1` | Siempre loopback; se expone con Tailscale Serve |
| `PORTAL_PUERTO` | `8100` | Puerto; Tailscale Serve apunta acá (no toca el 8000 del `.bat`) |
| `PORTAL_SECRETO` | `CAMBIAR-EN-CONFIG-PY` | Clave para firmar la cookie de sesión |
| `PORTAL_COOKIE_SEGURA` | `False` | En producción con Tailscale Serve: `True` |
| `PORTAL_SESION_HORAS` | `12` | Vencimiento de la sesión por inactividad |
| `PORTAL_ORIGENES` | `[]` | Mismo origen por defecto; agregar solo si hace falta |
| `PORTAL_MAX_SUBIDA_MB` | `25` | Tope de tamaño de cada PDF |
| `PORTAL_HASH` | `argon2` | Algoritmo de hash de contraseñas |
| `PORTAL_ADMINISTRADORES` | `[]` | `persona_id` que pueden administrar por HTTP; vacío = nadie (la consola sigue siendo la vía normal) |

`PORTAL_SECRETO` es obligatorio: el portal tiene que **rechazar** el
placeholder si sigue igual. Se genera con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Exposición: Tailscale Serve, no `0.0.0.0`

El portal escucha **siempre en `127.0.0.1`**. No se abre a `0.0.0.0` en
una PC con datos de clientes. Para entrar desde otra máquina se pone
**Tailscale Serve** (o un proxy con HTTPS) delante, apuntando a
**`127.0.0.1:8100`**: Tailscale termina el TLS y reenvía al portal.

En producción, con Tailscale Serve, `PORTAL_COOKIE_SEGURA = True` para
que la cookie de sesión solo viaje por HTTPS. En local queda `False`.

`PORTAL_ORIGENES` arranca en `[]` (mismo origen). Solo se agrega un
origen si el panel se sirve desde otro dominio.

## Hash de contraseñas: argon2 verificado en Python 3.14

Verificado el 02/11/2026 en un venv limpio con **Python 3.14.6**:

```
argon2-cffi 25.1.0  ->  instala OK (argon2-cffi-bindings 26.1.0, cffi 2.1.1)
PasswordHasher().hash("...")  ->  $argon2id$v=19$m=65536,t=3,p=4
verify  ->  True
```

Por eso `requirements.txt` usa `argon2-cffi` y `PORTAL_HASH = "argon2"`.

**Alternativa documentada (bcrypt):** si en alguna máquina argon2 no
instala (por ejemplo, una arquitectura sin wheel), el plan es:

1. `pip install bcrypt`
2. Poner `PORTAL_HASH = "bcrypt"` en `config.py`
3. Cambiar el import del hasher en el portal (Paso 1). El contrato de la
   base no cambia: se guarda el hash completo, con su prefijo, y se
   verifica con la librería que corresponda.

No se instaló bcrypt en esta verificación porque no hizo falta.

## Datos y secretos que no se suben

`.gitignore` cubre:

- `portal.db` (y `-journal`, `-wal`, `-shm`): datos de causas.
- `portal_uploads/`: PDFs subidos.
- `portal_secret*` y `.env`: secretos sueltos. El secreto real va en
  `config.py`, que ya estaba ignorado.

Regla: el hub guarda **datos**, no sesiones ni credenciales de portales
(D21). Los perfiles de Chrome y las contraseñas de SISFE/FirmAr no salen
de cada máquina.

## `reset_registros.py`: conserva los pendientes

`estado.json` mezcla dos cosas:

- `cedulas`: cédulas ya generadas (se pueden regenerar).
- `pendientes`: decretos detectados que esperan que una persona elija el
  tipo de cédula. **Eso no se regenera solo.**

El reset vacía `cedulas` y **conserva `pendientes`**. Los otros dos
registros (`cedulas_procesadas.json`, `estado_expedientes.json`) quedan
como dict vacío `{}`, que es lo que espera el monitor. No crea archivos
que no existían.

Antes de tocar nada pide confirmación (`s/N`) y avisa que hay que cerrar
la consola, el portal y el monitor. `estado.json` se escribe con
`estado._mutar` (RLock + FileLock + `os.replace`), así que no pisa a un
proceso que esté corriendo.

```bash
python reset_registros.py
```

## Paso 1a: base, login y administración

| Archivo | Qué hace |
|---|---|
| `portal/db.py` | Base SQLite: personas, credenciales, sesiones, estado, log, ficha, documentos y presentaciones |
| `portal/auth.py` | Hash de contraseñas, login, sesiones y cookie firmada |
| `portal_admin.py` | Consola para crear la base, sembrar personas y manejar claves |

### Qué guarda la base

- **Personas e identidades**: `persona_id` estable, nombre, mail, matrícula
  y si está activa.
- **Credenciales**: el hash completo (argon2id o bcrypt), nunca la clave.
- **Sesiones**: solo el sha256 del token, con vencimiento y datos de la
  máquina. Una copia de `portal.db` no sirve para entrar.
- **Estado, log y ficha**: las tres cosas que se centralizan (D21).
- **Documentos**: metadata de los PDF subidos (ruta, sha256, tamaño).
- **Presentaciones**: el anti-duplicado central (D22); una cédula no se
  puede marcar presentada dos veces.

No se guardan `firma`, `perfil` ni rutas de Chrome: eso es de cada máquina
(D21).

### Poner la base en marcha

```bash
# 1. Crear la base y sembrar PERSONAS de config.py
python portal_admin.py init

# 2. Ver quién quedó cargado
python portal_admin.py listar

# 3. Poner la clave de una persona (la pide por consola, no por parámetro)
python portal_admin.py password santiago
```

Otros comandos: `sembrar`, `crear`, `activar`, `desactivar` y
`sesiones-borrar`. `desactivar` también cierra las sesiones abiertas.

`PORTAL_SECRETO` tiene que estar configurado: `auth.py` rechaza el
placeholder. La cookie se firma con HMAC-SHA256 y lleva `HttpOnly`,
`SameSite=Lax` y `Secure` según `PORTAL_COOKIE_SEGURA`.

## Paso 1b: servidor, permisos y panel

| Archivo | Qué hace |
|---|---|
| `portal/permisos.py` | Persona activa, acciones permitidas y regla de la cadena (D25) |
| `portal/servidor_portal.py` | FastAPI: login, estado, log, ficha, documentos y panel mínimo |
| `Iniciar_Portal.bat` | Prepara la base, arranca el servidor en 8100 y abre el navegador |

### Arrancar

```bash
# Opción 1: desde la consola (deja el log a la vista)
python -m portal.servidor_portal

# Opción 2: doble clic en Iniciar_Portal.bat
```

El `.bat` hace `python portal_admin.py init` antes de arrancar (es
idempotente: no borra claves ni reactiva personas) y, si ya hay algo
escuchando en `127.0.0.1:8100`, no levanta un segundo servidor: solo abre
el panel. El servidor escucha **siempre en loopback**; para otra máquina se
usa Tailscale Serve delante.

`python -m portal.servidor_portal` (y no `python portal/servidor_portal.py`)
es a propósito: el módulo usa imports del paquete `portal`.

### Endpoints

Todos los que no son login/salud piden la cookie de sesión. Los errores
salen como `{"ok": false, "error": "..."}`.

El portal **no escribe cédulas**: las rutas de escritura de estado, cédulas
y log se sacaron en el commit 2. Lo que queda por HTTP es lectura, sesión,
ficha, documentos y administración.

| Método y ruta | Tipo | Para qué |
|---|---|---|
| `GET /` | lectura | Login (o redirige a `/panel` si ya hay sesión) |
| `POST /login` | sesión | Abre sesión, firma la cookie y audita (`login` / `login_fallido`) |
| `POST /logout` | sesión | Cierra la sesión en la base, borra la cookie y audita (`logout`) |
| `GET /panel` | lectura | Panel HTML mínimo (solo consulta) |
| `GET /api/sesion` | lectura | Quién está autenticado |
| `GET /api/salud` | lectura | Chequeo sin login |
| `GET /api/estado` | lectura | Lee estado + versión |
| `GET /api/cedulas` | lectura | Lista cédulas (filtro `?estado=`) |
| `GET /api/cedulas/{id}` | lectura | Una cédula |
| `GET /api/log` | lectura | Últimas entradas (`?limite=`) |
| `GET /api/ficha/{cuij}` | lectura | Lee la ficha |
| `PUT /api/ficha/{cuij}` | escritura | Mezcla claves en la ficha |
| `GET /api/documentos` | lectura | Lista documentos (`?cuij=`) |
| `POST /api/documentos` | escritura | Sube un PDF (multipart, tope `PORTAL_MAX_SUBIDA_MB`) |
| `GET /api/documentos/{id}` | lectura | Sirve el PDF (inline, solo si está dentro de `PORTAL_UPLOADS`) |
| `GET /api/personas` | lectura | Personas activas, sin hash |
| `GET /api/admin/personas` | admin | Lista todas (solo `PORTAL_ADMINISTRADORES`) |
| `POST /api/admin/personas` | admin | Crea persona |
| `PUT /api/admin/personas/{id}` | admin | Actualiza persona |
| `POST /api/admin/personas/{id}/password` | admin | Cambia clave |
| `POST /api/admin/personas/{id}/desactivar` | admin | Desactiva y cierra sesiones |
| `POST /api/admin/sesiones-borrar` | admin | Borra todas las sesiones |

Borrados en el commit 2: `PUT /api/estado`, `PUT /api/cedulas/{id}`,
`POST /api/cedulas/{id}/cadena`, `POST /api/cedulas/{id}/presentar` y
`POST /api/log`. Responden 404/405.

### Auditoría y log de cédulas

Son dos registros distintos:

- **`auditoria`** (tabla de `portal.db`): quién entró y quién salió. Las
  filas las escribe `db.registrar_auditoria(persona_id, accion, ip, detalle)`
  desde `login` y `logout`. El `detalle` se recorta a 80 caracteres.
- **`log_acciones` / `log_acciones.jsonl`**: solo actos sobre cédulas.
  `db.agregar_log` escribe la tabla y el servidor deja el helper
  `_registrar_log(persona, request, accion, ...)` (commit 4), con
  `identidad` y `operador` = nombre de la persona de la sesión.

### La cadena (D25)

La identidad de una cédula queda en `identidad_cadena` (el **nombre** de la
persona, ej. `"Santiago"`). La regla vive en `portal/db.py`:
`guardar_cedula`, `sincronizar_estado`, `fijar_cadena_cedula` y
`presentar_cedula` conservan la cadena ya fijada y rechazan un pedido que
intente cambiarla (`ConflictoCadena`, D25). `presentar_cedula` chequea la
cadena dentro de la misma transacción que inserta la presentación, y la PK
de `presentaciones` frena el duplicado (D22).

El operador puede ser distinto de la identidad (D18); lo que no se puede es
mezclar. El control cruzado fuerte sigue siendo el login del portal.

### Seguridad del servidor

- **Cookie**: `HttpOnly`, `SameSite=Lax`, `Secure` según
  `PORTAL_COOKIE_SEGURA`; el token en claro no se guarda (solo su sha256).
- **CSRF**: en POST/PUT/PATCH/DELETE, si el navegador manda `Origin`, tiene
  que coincidir con el `Host` o con un origen de `PORTAL_ORIGENES`. Los
  pedidos sin `Origin` (scripts locales) pasan.
- **CORS**: por defecto `PORTAL_ORIGENES = []` (mismo origen). Si se abre a
  otro dominio, se agrega ahí y se usa `allow_credentials=True`.
- **Subidas**: solo PDF, nombre saneado (sin rutas), tope de tamaño y
  descarga restringida a `PORTAL_UPLOADS` (si la metadata apunta afuera,
  responde 403).
- **Nunca `0.0.0.0`**: el bind es `PORTAL_HOST` (loopback). La exposición
  remota es Tailscale Serve/HTTPS.

### Panel mínimo

`/` y `/panel` sirven un HTML sin dependencias externas: login, resumen,
tabla de cédulas (solo lectura), búsqueda de ficha por CUIJ, notas,
documentos y los últimos movimientos. Es un panel de trabajo, no la UI
final: alcanza para validar el contrato y consultar el hub.

## Cómo verificar

```bash
python -m pytest tests/ -q
```

Los tests del portal son `tests/test_portal_db.py`,
`tests/test_portal_auth.py`, `tests/test_portal_admin.py`,
`tests/test_portal_permisos.py` y `tests/test_portal_servidor.py`. Los del
Paso 0 siguen en `tests/test_reset_registros.py` y el del lock reentrante
en `tests/test_estado_atomico.py`.

## Qué NO hace el Paso 1b

- No conecta el pipeline local (generar/firmar/notificar) con el hub: eso
  es el paso siguiente. El contrato HTTP ya está.
- No automatiza Tailscale Serve: está documentado, pero se configura aparte.
- No tiene roles: todos los que entran operan; administrar por HTTP es una
  lista explícita (`PORTAL_ADMINISTRADORES`) y la consola sigue siendo la
  vía normal.
- No resuelve la firma en lote, la casilla de mail por persona ni el
  monitor con identidad personal (Fase 10a, pendientes).
- No toca `config.py` (es por máquina y no se sube).
