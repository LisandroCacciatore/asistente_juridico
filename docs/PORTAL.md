# Portal del estudio — Paso 0 (preparación)

> **Estado:** Paso 0. Todavía **no hay código de portal**. Este documento
> fija el contrato de configuración y las reglas de datos/secretos que el
> Paso 1 va a implementar. La fuente de verdad del circuito sigue siendo
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

## Cómo verificar (sin portal)

```bash
python -m pytest tests/ -q
```

Los tests del Paso 0 son `tests/test_reset_registros.py` y el del lock
reentrante en `tests/test_estado_atomico.py`.

## Qué NO hace el Paso 0

- No crea `portal.py` ni endpoints.
- No crea la base ni las tablas.
- No implementa login, sesiones ni subida de PDFs.
- No toca `config.py` (es por máquina y no se sube).

Eso es el **Paso 1**.
