# -*- coding: utf-8 -*-
# ============================================================
#  PORTAL/DB.PY — Base SQLite del hub (Fase 10b)
# ------------------------------------------------------------
#  Una sola fuente de verdad para lo que se centraliza (D21):
#    personas e identidades, estado de cédulas, log, ficha del
#  Un solo archivo SQLite (portal.db) para personas, credenciales, sesiones,
#  auditoría y el bloqueo de login. El estado y el log viven en estado.py.
#
#  Lo que NO se guarda acá: perfiles de Chrome, sesiones de los
#  portales, firma, matrícula del perfil ni rutas de cada máquina.
#  Eso sigue siendo de la máquina (D21).
#
#  Concurrencia: cada operación abre su propia conexión y las
#  escrituras compuestas usan BEGIN IMMEDIATE, así dos procesos
#  (consola + portal) no pierden actualizaciones.
# ============================================================

import contextlib
import datetime
import getpass
import json
import os
import platform
import re
import secrets
import sqlite3
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETO_PLACEHOLDER = "CAMBIAR-EN-CONFIG-PY"


class ErrorPortal(RuntimeError):
    """Error de la base del portal."""


class PersonaExistente(ErrorPortal):
    """Ya hay una persona con ese persona_id o con ese mail."""


class PersonaNoEncontrada(ErrorPortal):
    """No existe la persona pedida."""


# --- Configuración ------------------------------------------------
def config_portal(nombre, default=None):
    """Lee una clave PORTAL_* de config.py, con default si no está."""
    try:
        import config
    except Exception:
        return default
    return getattr(config, nombre, default)


def ruta_db():
    return config_portal("PORTAL_DB", os.path.join(RAIZ, "portal.db"))


def ruta_uploads():
    return config_portal("PORTAL_UPLOADS", os.path.join(RAIZ, "portal_uploads"))


# --- Conexión -----------------------------------------------------
def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _quien():
    """Usuario de Windows y máquina, para que el log nunca quede vacío."""
    try:
        usuario = getpass.getuser()
    except Exception:
        usuario = os.environ.get("USERNAME") or os.environ.get("USER") or "?"
    try:
        maquina = platform.node()
    except Exception:
        maquina = ""
    return usuario, maquina


def quien():
    """Alias público de `_quien` para el servidor."""
    return _quien()


def _conectar(ruta=None):
    ruta = ruta or ruta_db()
    if ruta != ":memory:":
        carpeta = os.path.dirname(os.path.abspath(ruta))
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
    con = sqlite3.connect(ruta, timeout=10)
    con.row_factory = sqlite3.Row
    con.isolation_level = None
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 10000")
    if ruta != ":memory:":
        con.execute("PRAGMA journal_mode = WAL")
    return con


@contextlib.contextmanager
def conexion(ruta=None):
    con = _conectar(ruta)
    try:
        yield con
    finally:
        con.close()


@contextlib.contextmanager
def _transaccion(con):
    """BEGIN IMMEDIATE: toma el lock de escritura de entrada."""
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    try:
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


ESQUEMA = """
CREATE TABLE IF NOT EXISTS personas (
    persona_id  TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    mail        TEXT NOT NULL DEFAULT '',
    matricula   TEXT NOT NULL DEFAULT '',
    activo      INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    puede_actuar_como TEXT NOT NULL DEFAULT '',
    creado      TEXT NOT NULL,
    actualizado TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_personas_mail
    ON personas(mail) WHERE mail <> '';

CREATE TABLE IF NOT EXISTS credenciales (
    persona_id  TEXT PRIMARY KEY REFERENCES personas(persona_id) ON DELETE CASCADE,
    hash        TEXT NOT NULL,
    actualizado TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sesiones (
    token_hash      TEXT PRIMARY KEY,
    persona_id      TEXT NOT NULL REFERENCES personas(persona_id) ON DELETE CASCADE,
    creado          TEXT NOT NULL,
    expira          TEXT NOT NULL,
    usuario_windows TEXT NOT NULL DEFAULT '',
    maquina         TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sesiones_persona ON sesiones(persona_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_expira ON sesiones(expira);


CREATE TABLE IF NOT EXISTS auditoria (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha      TEXT NOT NULL,
    persona_id TEXT NOT NULL DEFAULT '',
    accion     TEXT NOT NULL,
    ip         TEXT NOT NULL DEFAULT '',
    detalle    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria(fecha);
CREATE INDEX IF NOT EXISTS idx_auditoria_persona ON auditoria(persona_id);
"""


# --- Auditoría (tablas del hub, separada del log de cédulas) ------
def _limpiar(texto, tope):
    """Texto en una línea, sin caracteres de control, recortado a `tope`.

    Todo lo que entra a `auditoria` viene de afuera (un identificador de login
    puede ser cualquier cosa), así que se normaliza acá y no en el llamador.
    """
    limpio = "".join(c for c in str(texto or "") if c == " " or c.isprintable())
    return limpio.strip()[:tope]


def registrar_auditoria(persona_id="", accion="", ip="", detalle="", ruta=None):
    """Deja una fila en `auditoria`: login, logout y rechazos del portal.

    Es aparte de `log_acciones` (y de `log_acciones.jsonl`), que guarda
    solo lo que pasa con las cédulas. Los cuatro campos se recortan y se
    limpian: `persona_id` 80, `accion` 40, `ip` 45, `detalle` 80.
    """
    with conexion(ruta) as con, _transaccion(con):
        cur = con.execute(
            "INSERT INTO auditoria (fecha, persona_id, accion, ip, detalle) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                _ahora(),
                _limpiar(persona_id, 80),
                _limpiar(accion, 40),
                _limpiar(ip, 45),
                _limpiar(detalle, 80),
            ),
        )
        return cur.lastrowid


def _migrar(con):
    """Agrega columnas nuevas a bases ya creadas. Es idempotente.

    `CREATE TABLE IF NOT EXISTS` no toca una tabla que ya existe, así que una
    base vieja se quedaría sin `puede_actuar_como` para siempre.
    """
    columnas = {fila["name"] for fila in con.execute("PRAGMA table_info(personas)")}
    if "puede_actuar_como" not in columnas:
        con.execute(
            "ALTER TABLE personas ADD COLUMN puede_actuar_como TEXT NOT NULL DEFAULT ''"
        )
    con.commit()


def inicializar(ruta=None):
    """Crea las tablas, migra columnas y reduce el esquema viejo.

    Es idempotente: la segunda vez no crea, no migra y no hace backup.
    """
    with conexion(ruta) as con:
        con.executescript(ESQUEMA)
        _migrar(con)
    reducir_esquema(ruta)
    return ruta or ruta_db()


# --- Personas -----------------------------------------------------
def _validar_persona_id(persona_id):
    pid = str(persona_id or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", pid):
        raise ValueError(
            "persona_id tiene que ser un slug de hasta 64 caracteres: "
            "minúsculas, números, '-' o '_'."
        )
    return pid


def _fila(row):
    return dict(row) if row is not None else None


def crear_persona(persona_id, nombre, mail="", matricula="", activo=True, ruta=None):
    pid = _validar_persona_id(persona_id)
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre no puede estar vacío.")
    mail = str(mail or "").strip().lower()
    matricula = str(matricula or "").strip()
    ahora = _ahora()
    with conexion(ruta) as con, _transaccion(con):
        try:
            con.execute(
                "INSERT INTO personas (persona_id, nombre, mail, matricula, activo, creado, actualizado) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (pid, nombre, mail, matricula, 1 if activo else 0, ahora, ahora),
            )
        except sqlite3.IntegrityError as e:
            raise PersonaExistente(
                f"Ya existe una persona con persona_id={pid!r} o con el mail {mail!r}."
            ) from e
    return obtener_persona(pid, ruta=ruta)


def obtener_persona(persona_id, ruta=None):
    with conexion(ruta) as con:
        return _fila(con.execute(
            "SELECT * FROM personas WHERE persona_id = ?", (str(persona_id or ""),)
        ).fetchone())


def obtener_persona_por_identificador(identificador, ruta=None):
    """Busca por persona_id o por mail (sin distinguir mayúsculas)."""
    buscado = str(identificador or "").strip()
    if not buscado:
        return None
    with conexion(ruta) as con:
        return _fila(con.execute(
            "SELECT * FROM personas "
            "WHERE persona_id = ? OR (mail <> '' AND lower(mail) = lower(?)) "
            "ORDER BY CASE WHEN persona_id = ? THEN 0 ELSE 1 END LIMIT 1",
            (buscado, buscado, buscado),
        ).fetchone())


def listar_personas(ruta=None):
    with conexion(ruta) as con:
        return [dict(f) for f in con.execute(
            "SELECT * FROM personas ORDER BY nombre COLLATE NOCASE, persona_id"
        ).fetchall()]


# --- Identidades delegadas ----------------------------------------
def _lista_identidades(valor):
    """Texto guardado (o lista) -> identidades sin vacíos ni repetidos.

    En la base se guarda como texto separado por comas porque es legible con
    `sqlite3` a mano; el orden y las mayúsculas se respetan como los escribió
    el administrador (importan para mostrar, no para comparar).
    """
    if isinstance(valor, (list, tuple, set)):
        partes = list(valor)
    else:
        partes = str(valor or "").split(",")
    vistas, salida = set(), []
    for parte in partes:
        limpio = str(parte or "").strip()
        if limpio and limpio.casefold() not in vistas:
            vistas.add(limpio.casefold())
            salida.append(limpio)
    return salida


def puede_actuar_como(persona_id, ruta=None):
    """Identidades que esta persona puede operar además de la propia."""
    persona = obtener_persona(persona_id, ruta=ruta)
    if not persona:
        return []
    return _lista_identidades(persona.get("puede_actuar_como", ""))


def fijar_puede_actuar_como(persona_id, identidades, ruta=None):
    """Reemplaza la lista de identidades delegadas de una persona."""
    persona_id = str(persona_id or "")
    if obtener_persona(persona_id, ruta=ruta) is None:
        raise PersonaNoEncontrada(f"No existe la persona {persona_id!r}.")
    texto = ", ".join(_lista_identidades(identidades))
    with conexion(ruta) as con, _transaccion(con):
        con.execute(
            "UPDATE personas SET puede_actuar_como = ?, actualizado = ? "
            "WHERE persona_id = ?",
            (texto, _ahora(), persona_id),
        )
    return obtener_persona(persona_id, ruta=ruta)


def actualizar_persona(persona_id, nombre=None, mail=None, matricula=None, activo=None, ruta=None):
    persona_id = str(persona_id or "")
    campos = {}
    if nombre is not None:
        nombre = str(nombre).strip()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío.")
        campos["nombre"] = nombre
    if mail is not None:
        campos["mail"] = str(mail).strip().lower()
    if matricula is not None:
        campos["matricula"] = str(matricula).strip()
    if activo is not None:
        campos["activo"] = 1 if activo else 0
    if not campos:
        return obtener_persona(persona_id, ruta=ruta)
    campos["actualizado"] = _ahora()
    sql = "UPDATE personas SET " + ", ".join(f"{c} = ?" for c in campos) + " WHERE persona_id = ?"
    with conexion(ruta) as con, _transaccion(con):
        try:
            cur = con.execute(sql, (*campos.values(), persona_id))
        except sqlite3.IntegrityError as e:
            raise PersonaExistente(
                f"Ya hay otra persona con el mail {campos.get('mail', '')!r}."
            ) from e
        if cur.rowcount == 0:
            raise PersonaNoEncontrada(f"No existe la persona {persona_id!r}.")
    return obtener_persona(persona_id, ruta=ruta)


def activar_persona(persona_id, ruta=None):
    return actualizar_persona(persona_id, activo=True, ruta=ruta)


def desactivar_persona(persona_id, ruta=None):
    """Desactiva y cierra sus sesiones: no queda una cookie viva."""
    persona = actualizar_persona(persona_id, activo=False, ruta=ruta)
    eliminar_sesiones_persona(persona_id, ruta=ruta)
    return persona


# --- Credenciales -------------------------------------------------
def guardar_credencial(persona_id, hash_guardado, ruta=None):
    if not hash_guardado:
        raise ValueError("El hash de la contraseña no puede estar vacío.")
    ahora = _ahora()
    with conexion(ruta) as con, _transaccion(con):
        if con.execute("SELECT 1 FROM personas WHERE persona_id = ?", (persona_id,)).fetchone() is None:
            raise PersonaNoEncontrada(f"No existe la persona {persona_id!r}.")
        con.execute(
            "INSERT INTO credenciales (persona_id, hash, actualizado) VALUES (?, ?, ?) "
            "ON CONFLICT(persona_id) DO UPDATE SET hash = excluded.hash, actualizado = excluded.actualizado",
            (persona_id, hash_guardado, ahora),
        )
    return obtener_credencial(persona_id, ruta=ruta)


def obtener_credencial(persona_id, ruta=None):
    with conexion(ruta) as con:
        return _fila(con.execute(
            "SELECT * FROM credenciales WHERE persona_id = ?", (persona_id,)
        ).fetchone())


def eliminar_credencial(persona_id, ruta=None):
    with conexion(ruta) as con, _transaccion(con):
        return con.execute(
            "DELETE FROM credenciales WHERE persona_id = ?", (persona_id,)
        ).rowcount > 0


# --- Sesiones -----------------------------------------------------
def crear_sesion(token_hash, persona_id, expira, usuario_windows="", maquina="", ruta=None):
    with conexion(ruta) as con, _transaccion(con):
        try:
            con.execute(
                "INSERT INTO sesiones (token_hash, persona_id, creado, expira, usuario_windows, maquina) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (token_hash, persona_id, _ahora(), expira, usuario_windows, maquina),
            )
        except sqlite3.IntegrityError as e:
            raise ErrorPortal(
                "No se pudo crear la sesión (token repetido o persona inexistente)."
            ) from e
    return obtener_sesion(token_hash, ruta=ruta)


def obtener_sesion(token_hash, ruta=None):
    with conexion(ruta) as con:
        return _fila(con.execute(
            "SELECT * FROM sesiones WHERE token_hash = ?", (token_hash,)
        ).fetchone())


def renovar_sesion(token_hash, expira, ruta=None):
    with conexion(ruta) as con, _transaccion(con):
        return con.execute(
            "UPDATE sesiones SET expira = ? WHERE token_hash = ?", (expira, token_hash)
        ).rowcount > 0


def eliminar_sesion(token_hash, ruta=None):
    with conexion(ruta) as con, _transaccion(con):
        return con.execute(
            "DELETE FROM sesiones WHERE token_hash = ?", (token_hash,)
        ).rowcount > 0


def eliminar_sesiones_persona(persona_id, ruta=None):
    with conexion(ruta) as con, _transaccion(con):
        return con.execute(
            "DELETE FROM sesiones WHERE persona_id = ?", (persona_id,)
        ).rowcount


def eliminar_todas_las_sesiones(ruta=None):
    with conexion(ruta) as con, _transaccion(con):
        return con.execute("DELETE FROM sesiones").rowcount


def limpiar_sesiones_expiradas(ahora=None, ruta=None):
    ahora = ahora or _ahora()
    with conexion(ruta) as con, _transaccion(con):
        return con.execute(
            "DELETE FROM sesiones WHERE expira <= ?", (ahora,)
        ).rowcount


def contar_sesiones(persona_id=None, ruta=None):
    with conexion(ruta) as con:
        if persona_id is None:
            return con.execute("SELECT count(*) FROM sesiones").fetchone()[0]
        return con.execute(
            "SELECT count(*) FROM sesiones WHERE persona_id = ?", (persona_id,)
        ).fetchone()[0]


# --- Reducción del esquema (commit 4b) ----------------------------
#: Tablas del portal viejo que ya no existen: el estado y el log viven en
#: `estado.py`, la ficha se fue en el commit 4 y `documentos` en el 5 (el PDF
#: vive en PORTAL_UPLOADS y en `ruta_firmada`).
TABLAS_VIEJAS = (
    "estado", "log_acciones", "fichas", "presentaciones", "documentos",
)


def _tablas(con):
    return {
        fila["name"]
        for fila in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def backup(ruta=None):
    """Copia consistente de portal.db con la API de backup de sqlite.

    No se copia el archivo en caliente: con WAL, un `copy` puede dejar una
    base a medias. `Connection.backup` la copia abierta y consistente.
    Devuelve la ruta del backup.
    """
    origen_ruta = ruta or ruta_db()
    destino = f"{origen_ruta}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    origen = sqlite3.connect(origen_ruta)
    try:
        copia = sqlite3.connect(destino)
        try:
            origen.backup(copia)
        finally:
            copia.close()
    finally:
        origen.close()
    return destino


def reducir_esquema(ruta=None):
    """Borra las tablas del portal viejo, con backup previo.

    Idempotente: si no queda ninguna de `TABLAS_VIEJAS` no hace nada (y no
    genera backups de más). Devuelve la ruta del backup, o None.
    """
    origen = ruta or ruta_db()
    with conexion(origen) as con:
        presentes = _tablas(con)
    a_borrar = [tabla for tabla in TABLAS_VIEJAS if tabla in presentes]
    if not a_borrar:
        return None
    destino = backup(origen)
    with conexion(origen) as con, _transaccion(con):
        for tabla in a_borrar:
            con.execute(f"DROP TABLE IF EXISTS {tabla}")
    return destino


