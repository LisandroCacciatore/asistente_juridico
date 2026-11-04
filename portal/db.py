# -*- coding: utf-8 -*-
# ============================================================
#  PORTAL/DB.PY — Base SQLite del hub (Fase 10b)
# ------------------------------------------------------------
#  Una sola fuente de verdad para lo que se centraliza (D21):
#    personas e identidades, estado de cédulas, log, ficha del
#    cliente y documentos subidos.
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

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETO_PLACEHOLDER = "CAMBIAR-EN-CONFIG-PY"


class ErrorPortal(RuntimeError):
    """Error de la base del portal."""


class PersonaExistente(ErrorPortal):
    """Ya hay una persona con ese persona_id o con ese mail."""


class PersonaNoEncontrada(ErrorPortal):
    """No existe la persona pedida."""


class YaPresentada(ErrorPortal):
    """La cédula ya fue marcada como presentada (anti-duplicado, D22)."""


class CedulaNoEncontrada(ErrorPortal):
    """No existe la cédula pedida en el estado central."""


class ConflictoCadena(ErrorPortal):
    """La cédula pertenece a otra identidad y no se puede cruzar (D25)."""


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

CREATE TABLE IF NOT EXISTS estado (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    datos           TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 0,
    actualizado     TEXT NOT NULL,
    actualizado_por TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS log_acciones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora TEXT NOT NULL,
    accion     TEXT NOT NULL,
    id_cedula  TEXT NOT NULL DEFAULT '',
    caratula   TEXT NOT NULL DEFAULT '',
    cuij       TEXT NOT NULL DEFAULT '',
    detalle    TEXT NOT NULL DEFAULT '',
    usuario    TEXT NOT NULL DEFAULT '',
    maquina    TEXT NOT NULL DEFAULT '',
    operador   TEXT NOT NULL DEFAULT '',
    identidad  TEXT NOT NULL DEFAULT '',
    persona_id TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_log_fecha ON log_acciones(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_log_cedula ON log_acciones(id_cedula);

CREATE TABLE IF NOT EXISTS fichas (
    cuij            TEXT PRIMARY KEY,
    datos           TEXT NOT NULL,
    actualizado     TEXT NOT NULL,
    actualizado_por TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS documentos (
    id         TEXT PRIMARY KEY,
    cuij       TEXT NOT NULL DEFAULT '',
    nombre     TEXT NOT NULL,
    ruta       TEXT NOT NULL,
    sha256     TEXT NOT NULL,
    tamano     INTEGER NOT NULL DEFAULT 0,
    subido_por TEXT NOT NULL DEFAULT '',
    subido_en  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documentos_cuij ON documentos(cuij);

CREATE TABLE IF NOT EXISTS presentaciones (
    id_cedula  TEXT PRIMARY KEY,
    persona_id TEXT NOT NULL DEFAULT '',
    fecha_hora TEXT NOT NULL,
    detalle    TEXT NOT NULL DEFAULT ''
);

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
def registrar_auditoria(persona_id="", accion="", ip="", detalle="", ruta=None):
    """Deja una fila en `auditoria`: login, logout y rechazos del portal.

    Es aparte de `log_acciones` (y de `log_acciones.jsonl`), que guarda
    solo lo que pasa con las cédulas. El detalle se recorta a 80
    caracteres para que un identificador largo no se convierta en basura.
    """
    with conexion(ruta) as con, _transaccion(con):
        cur = con.execute(
            "INSERT INTO auditoria (fecha, persona_id, accion, ip, detalle) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                _ahora(),
                str(persona_id or ""),
                str(accion or ""),
                str(ip or ""),
                str(detalle)[:80],
            ),
        )
        return cur.lastrowid


def inicializar(ruta=None):
    """Crea las tablas si faltan. Es idempotente."""
    with conexion(ruta) as con:
        con.executescript(ESQUEMA)
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


# --- Estado central ----------------------------------------------
def _normalizar_estado(datos):
    if not isinstance(datos, dict):
        raise ErrorPortal("El estado tiene que ser un objeto JSON.")
    for clave in ("cedulas", "pendientes"):
        if clave not in datos:
            datos[clave] = []
        if not isinstance(datos[clave], list):
            raise ErrorPortal(f"'{clave}' tiene que ser una lista.")
    return datos


def _leer_estado_con(con):
    """Lee el estado dentro de una conexión ya abierta (para transacciones)."""
    fila = con.execute("SELECT datos FROM estado WHERE id = 1").fetchone()
    datos = json.loads(fila["datos"]) if fila else {"cedulas": [], "pendientes": []}
    return _normalizar_estado(datos)


def _buscar_cedula(datos, id_cedula):
    buscado = str(id_cedula or "").strip()
    for cedula in datos.get("cedulas", []):
        if isinstance(cedula, dict) and str(cedula.get("id") or "").strip() == buscado:
            return cedula
    return None


def leer_estado(ruta=None):
    with conexion(ruta) as con:
        return _leer_estado_con(con)


def buscar_cedula(id_cedula, datos=None, ruta=None):
    """Busca una cédula en el estado (o en `datos` si ya se leyó)."""
    if datos is None:
        datos = leer_estado(ruta=ruta)
    return _buscar_cedula(datos, id_cedula)


def version_estado(ruta=None):
    with conexion(ruta) as con:
        fila = con.execute("SELECT version FROM estado WHERE id = 1").fetchone()
    return fila["version"] if fila else 0


def _guardar_estado(con, datos, persona_id):
    con.execute(
        "INSERT INTO estado (id, datos, version, actualizado, actualizado_por) "
        "VALUES (1, ?, 1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET datos = excluded.datos, "
        "version = estado.version + 1, actualizado = excluded.actualizado, "
        "actualizado_por = excluded.actualizado_por",
        (json.dumps(datos, ensure_ascii=False), _ahora(), str(persona_id or "")),
    )


def escribir_estado(datos, persona_id="", ruta=None):
    datos = _normalizar_estado(datos)
    with conexion(ruta) as con, _transaccion(con):
        _guardar_estado(con, datos, persona_id)
    return datos


def mutar_estado(modificador, persona_id="", ruta=None):
    """Lee, modifica en el lugar y guarda en una sola transacción."""
    with conexion(ruta) as con, _transaccion(con):
        datos = _leer_estado_con(con)
        modificador(datos)
        _normalizar_estado(datos)
        _guardar_estado(con, datos, persona_id)
    return datos


# --- Cédulas en el estado central (D25) --------------------------
def guardar_cedula(cedula, persona_id="", operador="", ruta=None):
    """Inserta o actualiza una cédula sin romper la cadena ya fijada.

    Si la cédula ya existe con `identidad_cadena`, esa identidad manda:
    un pedido con otra identidad se rechaza y uno sin identidad la
    conserva. Así el candado de D25 no se puede corregir por atrás.
    """
    if not isinstance(cedula, dict):
        raise ValueError("La cédula tiene que ser un objeto JSON.")
    cedula = dict(cedula)
    id_cedula = str(cedula.get("id") or "").strip()
    if not id_cedula:
        raise ValueError("La cédula necesita un id.")
    cedula["id"] = id_cedula

    with conexion(ruta) as con, _transaccion(con):
        datos = _leer_estado_con(con)
        existente = _buscar_cedula(datos, id_cedula)
        if existente is None:
            datos["cedulas"].append(cedula)
            accion = "cedula_registrada"
        else:
            fijada = str(existente.get("identidad_cadena") or "").strip()
            nueva = str(cedula.get("identidad_cadena") or "").strip()
            if fijada and nueva and fijada != nueva:
                raise ConflictoCadena(
                    f"La cédula {id_cedula!r} ya es de {fijada!r}; no se puede "
                    f"pasar a {nueva!r} (D25)."
                )
            cedula["identidad_cadena"] = fijada or nueva
            datos["cedulas"] = [
                cedula if str(c.get("id") or "").strip() == id_cedula else c
                for c in datos["cedulas"]
            ]
            accion = "cedula_actualizada"
        _guardar_estado(con, datos, persona_id)
        _insertar_log(con, _entrada_log(
            accion,
            id_cedula=id_cedula,
            caratula=cedula.get("caratula", ""),
            cuij=cedula.get("cuij", ""),
            operador=operador,
            identidad=cedula.get("identidad_cadena", ""),
            persona_id=persona_id,
        ))
    return cedula


def sincronizar_estado(datos, persona_id="", operador="", ruta=None):
    """Sincroniza el estado central sin poder corregir una cadena (D25).

    Las cédulas se agregan o actualizan; las que no vienen en el pedido
    **no se borran** (el hub es archivo, no una copia efímera de una
    máquina). Los pendientes sí se reemplazan: son de la corrida actual.
    Si una cédula ya tenía `identidad_cadena`, esa identidad se conserva
    y un pedido que intente cambiarla se rechaza.
    """
    datos = _normalizar_estado(dict(datos))
    with conexion(ruta) as con, _transaccion(con):
        actual = _leer_estado_con(con)
        por_id = {
            str(c.get("id") or "").strip(): c
            for c in actual.get("cedulas", [])
            if isinstance(c, dict)
        }
        for cedula in datos.get("cedulas", []):
            if not isinstance(cedula, dict):
                raise ValueError("Cada cédula tiene que ser un objeto JSON.")
            id_cedula = str(cedula.get("id") or "").strip()
            if not id_cedula:
                raise ValueError("Cada cédula necesita un id.")
            cedula = dict(cedula)
            cedula["id"] = id_cedula
            previa = por_id.get(id_cedula)
            fijada = str((previa or {}).get("identidad_cadena") or "").strip()
            nueva = str(cedula.get("identidad_cadena") or "").strip()
            if fijada and nueva and fijada != nueva:
                raise ConflictoCadena(
                    f"La cédula {id_cedula!r} ya es de {fijada!r}; no se puede "
                    f"pasar a {nueva!r} (D25)."
                )
            cedula["identidad_cadena"] = fijada or nueva
            por_id[id_cedula] = cedula
        datos["cedulas"] = list(por_id.values())
        _guardar_estado(con, datos, persona_id)
        _insertar_log(con, _entrada_log(
            "estado_sincronizado",
            detalle=f"{len(datos['cedulas'])} cédulas",
            operador=operador,
            identidad=operador or persona_id,
            persona_id=persona_id,
        ))
    return datos


def fijar_cadena_cedula(id_cedula, identidad, persona_id="", operador="", ruta=None):
    """Fija la identidad de la cédula en el primer acto del portal (D25)."""
    id_cedula = str(id_cedula or "").strip()
    identidad = str(identidad or "").strip()
    if not id_cedula:
        raise ValueError("La cédula necesita un id.")
    if not identidad:
        raise ValueError("La identidad no puede estar vacía.")

    with conexion(ruta) as con, _transaccion(con):
        datos = _leer_estado_con(con)
        cedula = _buscar_cedula(datos, id_cedula)
        if cedula is None:
            raise CedulaNoEncontrada(
                f"No existe la cédula {id_cedula!r} en el estado central."
            )
        fijada = str(cedula.get("identidad_cadena") or "").strip()
        if fijada and fijada != identidad:
            raise ConflictoCadena(
                f"La cédula {id_cedula!r} ya es de {fijada!r}; no se puede "
                f"pasar a {identidad!r} (D25)."
            )
        if not fijada:
            cedula["identidad_cadena"] = identidad
            _guardar_estado(con, datos, persona_id)
            _insertar_log(con, _entrada_log(
                "cadena_fijada",
                id_cedula=id_cedula,
                caratula=cedula.get("caratula", ""),
                cuij=cedula.get("cuij", ""),
                detalle=f"identidad {identidad}",
                operador=operador,
                identidad=identidad,
                persona_id=persona_id,
            ))
    return identidad


def presentar_cedula(id_cedula, identidad, persona_id="", operador="",
                     detalle="", ruta=None):
    """Marca presentada, actualiza el estado y deja el log, todo junto.

    La cadena se chequea dentro de la misma transacción: si la cédula es
    de otra identidad, no se inserta la presentación (D25). El
    anti-duplicado es la PK de `presentaciones` (D22).
    """
    id_cedula = str(id_cedula or "").strip()
    identidad = str(identidad or "").strip()
    if not id_cedula:
        raise ValueError("La cédula necesita un id.")
    if not identidad:
        raise ValueError("La identidad no puede estar vacía.")
    fecha = _ahora()

    with conexion(ruta) as con, _transaccion(con):
        datos = _leer_estado_con(con)
        cedula = _buscar_cedula(datos, id_cedula)
        if cedula is None:
            raise CedulaNoEncontrada(
                f"No existe la cédula {id_cedula!r} en el estado central."
            )
        fijada = str(cedula.get("identidad_cadena") or "").strip()
        if fijada and fijada != identidad:
            raise ConflictoCadena(
                f"La cédula {id_cedula!r} es de {fijada!r} y estás actuando "
                f"como {identidad!r}. No se puede cruzar la cadena (D25)."
            )
        try:
            con.execute(
                "INSERT INTO presentaciones (id_cedula, persona_id, fecha_hora, detalle) "
                "VALUES (?, ?, ?, ?)",
                (id_cedula, str(persona_id or ""), fecha, str(detalle or "")),
            )
        except sqlite3.IntegrityError as e:
            raise YaPresentada(
                f"La cédula {id_cedula!r} ya fue marcada como presentada."
            ) from e
        cedula["identidad_cadena"] = fijada or identidad
        cedula["estado"] = "presentada"
        cedula["fecha_presentada"] = fecha
        _guardar_estado(con, datos, persona_id)
        entrada = _entrada_log(
            "presentada",
            id_cedula=id_cedula,
            caratula=cedula.get("caratula", ""),
            cuij=cedula.get("cuij", ""),
            detalle=detalle,
            operador=operador,
            identidad=cedula["identidad_cadena"],
            persona_id=persona_id,
        )
        _insertar_log(con, entrada)
    return {
        "cedula": cedula,
        "presentacion": {
            "id_cedula": id_cedula,
            "persona_id": str(persona_id or ""),
            "fecha_hora": fecha,
            "detalle": str(detalle or ""),
        },
        "log": entrada,
    }


# --- Log de acciones ---------------------------------------------
_CAMPOS_LOG = (
    "fecha_hora", "accion", "id_cedula", "caratula", "cuij", "detalle",
    "usuario", "maquina", "operador", "identidad", "persona_id",
)


def _entrada_log(accion, id_cedula="", caratula="", cuij="", detalle="",
                 usuario="", maquina="", operador="", identidad="",
                 persona_id=""):
    accion = str(accion or "").strip()
    if not accion:
        raise ValueError("La acción del log no puede estar vacía.")
    usuario_win, maquina_win = _quien()
    return {
        "fecha_hora": _ahora(),
        "accion": accion,
        "id_cedula": str(id_cedula or ""),
        "caratula": str(caratula or ""),
        "cuij": str(cuij or ""),
        "detalle": str(detalle or ""),
        "usuario": str(usuario or usuario_win),
        "maquina": str(maquina or maquina_win),
        "operador": str(operador or usuario or usuario_win),
        "identidad": str(identidad or operador or usuario or usuario_win),
        "persona_id": str(persona_id or ""),
    }


def _insertar_log(con, entrada):
    cur = con.execute(
        f"INSERT INTO log_acciones ({', '.join(_CAMPOS_LOG)}) "
        f"VALUES ({', '.join('?' for _ in _CAMPOS_LOG)})",
        tuple(entrada[c] for c in _CAMPOS_LOG),
    )
    entrada["id"] = cur.lastrowid
    return entrada


def agregar_log(accion, id_cedula="", caratula="", cuij="", detalle="",
                usuario="", maquina="", operador="", identidad="",
                persona_id="", ruta=None):
    entrada = _entrada_log(
        accion, id_cedula=id_cedula, caratula=caratula, cuij=cuij,
        detalle=detalle, usuario=usuario, maquina=maquina,
        operador=operador, identidad=identidad, persona_id=persona_id,
    )
    with conexion(ruta) as con, _transaccion(con):
        _insertar_log(con, entrada)
    return entrada


def leer_log(limite=None, ruta=None):
    sql = "SELECT * FROM log_acciones ORDER BY id DESC"
    parametros = ()
    if limite is not None:
        limite = int(limite)
        if limite < 0:
            raise ValueError("El límite no puede ser negativo.")
        sql += " LIMIT ?"
        parametros = (limite,)
    with conexion(ruta) as con:
        return [dict(f) for f in con.execute(sql, parametros).fetchall()]


# --- Ficha del cliente -------------------------------------------
def leer_ficha(cuij, ruta=None):
    with conexion(ruta) as con:
        fila = con.execute("SELECT * FROM fichas WHERE cuij = ?", (str(cuij or ""),)).fetchone()
    if fila is None:
        return None
    datos = json.loads(fila["datos"])
    datos["cuij"] = fila["cuij"]
    datos["actualizado"] = fila["actualizado"]
    datos["actualizado_por"] = fila["actualizado_por"]
    return datos


def guardar_ficha(cuij, datos, persona_id="", ruta=None):
    """Upsert que mezcla las claves: no borra lo que no vino."""
    cuij = str(cuij or "").strip()
    if not cuij:
        raise ValueError("La ficha necesita un CUIJ.")
    if not isinstance(datos, dict):
        raise ValueError("La ficha tiene que ser un objeto JSON.")
    with conexion(ruta) as con, _transaccion(con):
        fila = con.execute("SELECT datos FROM fichas WHERE cuij = ?", (cuij,)).fetchone()
        actual = json.loads(fila["datos"]) if fila else {}
        actual.update(datos)
        actual["cuij"] = cuij
        con.execute(
            "INSERT INTO fichas (cuij, datos, actualizado, actualizado_por) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(cuij) DO UPDATE SET datos = excluded.datos, "
            "actualizado = excluded.actualizado, actualizado_por = excluded.actualizado_por",
            (cuij, json.dumps(actual, ensure_ascii=False), _ahora(), str(persona_id or "")),
        )
    return leer_ficha(cuij, ruta=ruta)


def listar_fichas(ruta=None):
    with conexion(ruta) as con:
        filas = con.execute(
            "SELECT cuij, datos, actualizado, actualizado_por FROM fichas ORDER BY actualizado DESC"
        ).fetchall()
    resultado = []
    for fila in filas:
        datos = json.loads(fila["datos"])
        datos["cuij"] = fila["cuij"]
        datos["actualizado"] = fila["actualizado"]
        datos["actualizado_por"] = fila["actualizado_por"]
        resultado.append(datos)
    return resultado


# --- Documentos subidos ------------------------------------------
def registrar_documento(nombre, ruta_archivo, sha256, tamano=0, cuij="",
                        subido_por="", documento_id=None, ruta=None):
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ValueError("El documento necesita un nombre.")
    if not sha256:
        raise ValueError("El documento necesita su sha256.")
    doc_id = str(documento_id or secrets.token_hex(8))
    subido_en = _ahora()
    with conexion(ruta) as con, _transaccion(con):
        try:
            con.execute(
                "INSERT INTO documentos (id, cuij, nombre, ruta, sha256, tamano, subido_por, subido_en) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_id, str(cuij or ""), nombre, str(ruta_archivo or ""), str(sha256),
                 int(tamano or 0), str(subido_por or ""), subido_en),
            )
        except sqlite3.IntegrityError as e:
            raise ErrorPortal(f"Ya existe un documento con id {doc_id!r}.") from e
    return obtener_documento(doc_id, ruta=ruta)


def obtener_documento(documento_id, ruta=None):
    with conexion(ruta) as con:
        return _fila(con.execute(
            "SELECT * FROM documentos WHERE id = ?", (documento_id,)
        ).fetchone())


def listar_documentos(cuij=None, ruta=None):
    with conexion(ruta) as con:
        if cuij is None:
            filas = con.execute("SELECT * FROM documentos ORDER BY subido_en DESC").fetchall()
        else:
            filas = con.execute(
                "SELECT * FROM documentos WHERE cuij = ? ORDER BY subido_en DESC", (cuij,)
            ).fetchall()
    return [dict(f) for f in filas]


def eliminar_documento(documento_id, ruta=None):
    with conexion(ruta) as con, _transaccion(con):
        return con.execute(
            "DELETE FROM documentos WHERE id = ?", (documento_id,)
        ).rowcount > 0


# --- Anti-duplicado central (D22) --------------------------------
def marcar_presentada(id_cedula, persona_id="", detalle="", ruta=None):
    id_cedula = str(id_cedula or "").strip()
    if not id_cedula:
        raise ValueError("La cédula necesita un id.")
    fecha = _ahora()
    with conexion(ruta) as con, _transaccion(con):
        try:
            con.execute(
                "INSERT INTO presentaciones (id_cedula, persona_id, fecha_hora, detalle) "
                "VALUES (?, ?, ?, ?)",
                (id_cedula, str(persona_id or ""), fecha, str(detalle or "")),
            )
        except sqlite3.IntegrityError as e:
            raise YaPresentada(
                f"La cédula {id_cedula!r} ya fue marcada como presentada."
            ) from e
    return {
        "id_cedula": id_cedula,
        "persona_id": str(persona_id or ""),
        "fecha_hora": fecha,
        "detalle": str(detalle or ""),
    }


def ya_presentada(id_cedula, ruta=None):
    with conexion(ruta) as con:
        return con.execute(
            "SELECT 1 FROM presentaciones WHERE id_cedula = ?", (str(id_cedula or ""),)
        ).fetchone() is not None


def listar_presentaciones(ruta=None):
    with conexion(ruta) as con:
        return [dict(f) for f in con.execute(
            "SELECT * FROM presentaciones ORDER BY fecha_hora DESC"
        ).fetchall()]
