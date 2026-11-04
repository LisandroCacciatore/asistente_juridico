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

El portal **no escribe cédulas ni tiene estado propio**: lee `estado.json` y
`log_acciones.jsonl` a través de `portal/hub.py` (solo lectura). Las rutas de
escritura de estado, cédulas y log se sacaron en el commit 2; la ficha y las
tablas viejas se fueron en el commit 4.

| Método y ruta | Tipo | Para qué |
|---|---|---|
| `GET /` | lectura | Login (o redirige a `/panel` si ya hay sesión) |
| `POST /login` | sesión | Abre sesión, firma la cookie y audita (`login` / `login_fallido`) |
| `POST /logout` | sesión | Cierra la sesión en la base, borra la cookie y audita (`logout`) |
| `GET /panel` | lectura | Panel HTML: Novedades y Actividad |
| `GET /cambiar-password` | sesión | Formulario de cambio de contraseña |
| `POST /cambiar-password` | sesión | Cambia la clave (exige la actual, ≥12 y distinta) |
| `GET /api/sesion` | lectura | Quién está autenticado |
| `GET /api/salud` | lectura | Chequeo sin login |
| `GET /api/portal/novedades` | lectura | Cédulas recientes (`?limite=`); pendientes solo para admin |
| `GET /api/portal/actividad` | lectura | Últimos movimientos (`?limite=`) filtrados por identidad |
| `GET /api/cedulas` | lectura | Lista cédulas (filtro `?estado=`) |
| `GET /api/cedulas/{id}` | lectura | Una cédula (404 si no es visible) |
| `GET /api/log` | lectura | Igual que actividad (se mantiene por compatibilidad) |
| `POST /api/portal/cedulas/{id}/subir` | escritura | Sube el PDF **firmado** de la cédula, la marca firmada y loguea `pdf_subido` |
| `GET /api/portal/cedulas/{id}/pdf` | lectura | Sirve el PDF firmado (404 si no existe o no es visible) |
| `GET /api/personas` | lectura | Personas activas, sin hash |
| `GET /api/admin/personas` | admin | Lista todas (solo `PORTAL_ADMINISTRADORES`) |
| `POST /api/admin/personas` | admin | Crea persona |
| `PUT /api/admin/personas/{id}` | admin | Actualiza persona |
| `POST /api/admin/personas/{id}/password` | admin | Cambia clave |
| `POST /api/admin/personas/{id}/desactivar` | admin | Desactiva y cierra sesiones |
| `POST /api/admin/sesiones-borrar` | admin | Borra todas las sesiones |

Borrados: en el commit 2 `PUT /api/estado`, `PUT /api/cedulas/{id}`,
`POST /api/cedulas/{id}/cadena`, `POST /api/cedulas/{id}/presentar` y
`POST /api/log`; en el commit 4a `GET /api/estado` (lo reemplaza
`/api/portal/novedades`) y en el 4b los de ficha. Todos responden 404/405.

### Campos que salen por HTTP

El hub recorta cada cédula a una lista **fija**: `id`, `caratula`, `cuij`,
`estado`, `identidad_cadena`, `tipo`, `fecha_generada`, `fecha_firmada`.
Nunca salen `ruta_pdf`, `ruta_firmada` ni los textos del decreto. Los
pendientes salen con `id`, `caratula`, `cuij`, `tipo_sugerido`,
`fecha_decreto`, y **solo los ve un administrador** (todavía no tienen
identidad).

### Auditoría y log de cédulas

Son dos registros distintos:

- **`auditoria`** (tabla de `portal.db`): quién entró, quién salió y qué hizo
  de administración. La escribe `db.registrar_auditoria(persona_id, accion,
  ip, detalle)`, que recorta los cuatro campos (`persona_id` 80, `accion` 40,
  `ip` 45, `detalle` 80) y les quita caracteres de control. Un logout sin
  sesión no deja fila.
- **`log_acciones.jsonl`** (módulo `estado.py`): solo actos sobre cédulas.
  El servidor los escribe con `_registrar_log(...)`, que delega en
  `estado.registrar_log` con `identidad` = nombre de la persona de la sesión,
  `operador` = su nombre, `usuario="portal"` y `maquina` = IP del cliente.

La IP del cliente sale de `X-Forwarded-For` **solo** cuando la conexión
directa viene de `127.0.0.1` (Tailscale Serve), y se toma la **última**
entrada: la agrega el proxy de confianza, las anteriores las puede inventar
quien llama.

### La cadena (D25)

La identidad de una cédula queda en `identidad_cadena` (el **nombre** de la
persona, ej. `"Santiago"`, nunca el `persona_id`). La regla vive en
`estado.py`; el portal la respeta en `portal/permisos.py`:
`verificar_cadena` compara normalizado (`strip` + `casefold`) contra
`identidad_de(persona)`, y `puede_actuar_como` permite operar cédulas de
otra identidad delegada. El operador puede ser distinto de la identidad
(D18); lo que no se puede es mezclar.

### Subida del PDF firmado

`POST /api/portal/cedulas/{id}/subir` reemplaza la subida genérica. Valida, en
este orden, **antes** de dejar el archivo en su lugar definitivo (se escribe en
un temporal dentro de `PORTAL_UPLOADS` y recién al final se mueve con
`os.replace`):

1. permisos y visibilidad de la cédula (404 si no es visible);
2. **D25**: `verificar_cadena` — hay que poder actuar como la identidad de la
   cédula. **El administrador no es excepción**: sin delegación explícita, 403;
3. la cédula tiene cadena y está en estado `generada` (si no, 400/409);
4. tope de tamaño (`PORTAL_MAX_SUBIDA_MB`, 413);
5. cabecera `%PDF-` (400);
6. `pypdf` la abre y no está cifrada (400);
7. `cuij` y `caratula` del formulario coinciden con los de la cédula,
   comparados normalizados (400);
8. hay al menos un campo `/FT /Sig` cuyo `/V` sea un diccionario de firma con
   `/ByteRange` de 4 enteros y `/Contents` no vacío y no todo en ceros (400);
9. el sha256 no está repetido en otra cédula (409).

Se guarda en `PORTAL_UPLOADS/<id saneado>/<sha256>.pdf` y la cédula se marca
firmada con `estado.marcar_firmada(..., solo_si_generada=True)`, que hace el
chequeo de estado y la escritura **dentro del mismo lock**: si otro proceso ya
la marcó, el archivo recién guardado se borra y la respuesta es 409.

La respuesta trae solo `ok`, `id`, `sha256` y `estado`: **nunca la ruta del
servidor**.

**Alcance de la validación**: es un control contra errores humanos (subir el
PDF equivocado, uno sin firmar, el de otra causa), **no** una validación
criptográfica. No verifica el certificado del firmante ni la integridad del
documento: cualquiera puede fabricar un PDF con un campo de firma bien formado.
La verificación real (por ejemplo con `pyHanko`) queda para una etapa
posterior.

### Bloqueo de login

Los intentos fallidos se cuentan en la tabla `login_intentos` por dos claves:
`id:<identificador normalizado>` (exista o no la persona) y `ip:<ip del
cliente>`. Con **5 fallos en 15 minutos** se bloquea ese identificador;
la IP tiene un umbral más alto (**20**) porque una oficina puede compartir
salida. Mientras está bloqueado, la respuesta es la **misma** que un fallo
normal (`Usuario o contraseña incorrectos.`, 401) y se audita
`login_bloqueado`. Un login correcto borra los intentos de ese identificador.

Un identificador inexistente cuesta lo mismo que uno real: `auth.autenticar`
verifica igual contra un hash falso, así el tiempo de respuesta no delata qué
usuarios existen.

### Cambio obligatorio de contraseña

`credenciales.debe_cambiar` se pone en 1 al crear una persona con clave y al
resetearla (por HTTP o por consola). Mientras esté activo, la sesión solo
puede ir a `/cambiar-password` y a logout: el panel redirige y la API responde
403. La clave nueva tiene que ser **distinta de la anterior** y tener **al
menos 12 caracteres**. Al guardarla se cierran las demás sesiones de esa
persona y se audita `password_cambiada`.

### Token CSRF

El token es un HMAC-SHA256 de `PORTAL_SECRETO` sobre el identificador de la
sesión (el valor de la cookie firmada), recalculado en cada pedido y comparado
en tiempo constante. Los pedidos a `/api/*` que no son GET lo llevan en
`X-CSRF-Token`; se obtiene en `GET /api/sesion` (`csrf`). El chequeo de
`Origin` se mantiene, y el formulario de login usa un token derivado de una
cookie anónima. Un pedido de escritura **sin sesión** no exige token: la falta
de sesión ya lo rechaza con 401.

La consola `portal_admin.py` audita en `auditoria` lo que hace, con
`persona_id="cli"`: `cli_persona_creada`, `cli_persona_desactivada`,
`cli_password_actualizada` y `cli_puede_actuar`.

### Visibilidad

Un administrador (`PORTAL_ADMINISTRADORES`) ve todo. El resto ve solo las
cédulas cuya cadena esté entre sus identidades: la propia y las de
`puede_actuar_como` (columna de `personas`, se fija por consola:
`python portal_admin.py puede-actuar jr Santiago`). Una cédula sin cadena
todavía no es de nadie: solo la ve un administrador. Si una cédula o su PDF
no son visibles, la respuesta es **404**, igual que si no existiera: un 403
confirmaría que está ahí.

### Migración del esquema (commit 4b)

`db.inicializar()` reduce el esquema: si encuentra las tablas viejas
(`estado`, `log_acciones`, `fichas`, `presentaciones`) hace un **backup con
la API de sqlite** —`portal.db.bak-AAAAMMDD-HHMMSS`, no una copia en caliente
con WAL— y después las borra. Quedan `personas`, `credenciales`, `sesiones`,
`documentos` y `auditoria`. Es idempotente: si no hay tablas viejas, no hace
nada ni genera backups de más.

### Seguridad del servidor

- **Cookie**: `HttpOnly`, `SameSite=Lax`, `Secure` según
  `PORTAL_COOKIE_SEGURA`; el token en claro no se guarda (solo su sha256).
- **CSRF**: en POST/PUT/PATCH/DELETE, si el navegador manda `Origin`, tiene
  que coincidir con el `Host` o con un origen de `PORTAL_ORIGENES`. Los
  pedidos sin `Origin` (scripts locales) pasan.
- **CORS**: por defecto `PORTAL_ORIGENES = []` (mismo origen). Si se abre a
  otro dominio, se agrega ahí y se usa `allow_credentials=True`.
- **Subidas**: solo el PDF firmado de una cédula visible y operable (D25); tope
  de tamaño, cabecera PDF, `pypdf` sin cifrado, firma `/Sig` presente, CUIJ y
  carátula coincidentes, y sha256 único. El archivo vive en
  `PORTAL_UPLOADS/<id>/<sha256>.pdf` y la descarga exige que la ruta esté
  dentro de `PORTAL_UPLOADS`.
- **Nunca `0.0.0.0`**: el bind es `PORTAL_HOST` (loopback). La exposición
  remota es Tailscale Serve/HTTPS, y **no antes del commit 6**.

### Panel mínimo

`/` y `/panel` sirven un HTML sin dependencias externas ni JavaScript: login,
resumen, tabla de **Novedades** (cédulas visibles, con pendientes si sos
admin) y tabla de **Actividad** (log filtrado por identidad). Es un panel de
trabajo, no la UI final.

## Cómo verificar

```bash
python -m pytest tests/ -q
```

Los tests del portal son `tests/test_portal_db.py`,
`tests/test_portal_auth.py`, `tests/test_portal_admin.py`,
`tests/test_portal_permisos.py`, `tests/test_portal_hub.py` y
`tests/test_portal_servidor.py`. Los del Paso 0 siguen en
`tests/test_reset_registros.py` y el del lock reentrante en
`tests/test_estado_atomico.py`.

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
