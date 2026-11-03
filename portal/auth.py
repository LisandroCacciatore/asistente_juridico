# -*- coding: utf-8 -*-
# ============================================================
#  PORTAL/AUTH.PY — Login real del portal (D23)
# ------------------------------------------------------------
#  Reemplaza la declaración local (D19) por una identidad
#  autenticada: contraseña con argon2id y una sesión con
#  vencimiento por inactividad.
#
#  La cookie lleva el token de sesión + una firma HMAC con
#  PORTAL_SECRETO. El token en claro no se guarda: en la base
#  queda solo su sha256, así una copia de portal.db no sirve
#  para entrar.
# ============================================================

import datetime
import hashlib
import hmac
import secrets

from . import db

NOMBRE_COOKIE = "portal_sesion"
PLACEHOLDER_SECRETO = db.SECRETO_PLACEHOLDER


class ErrorConfiguracion(RuntimeError):
    """Falta una clave PORTAL_* o tiene un valor inválido."""


class ErrorSesion(RuntimeError):
    """No se puede abrir una sesión para esa persona."""


# --- Configuración ------------------------------------------------
def _bool(valor):
    if isinstance(valor, str):
        return valor.strip().lower() in ("1", "true", "si", "sí", "yes", "on")
    return bool(valor)


def horas_sesion():
    try:
        horas = int(db.config_portal("PORTAL_SESION_HORAS", 12))
    except (TypeError, ValueError):
        return 12
    return horas if horas > 0 else 12


def max_age_sesion():
    return horas_sesion() * 3600


def cookie_segura():
    return _bool(db.config_portal("PORTAL_COOKIE_SEGURA", False))


def opciones_cookie():
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": cookie_segura(),
        "max_age": max_age_sesion(),
        "path": "/",
    }


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(momento):
    return momento.isoformat(timespec="seconds")


# --- Contraseñas --------------------------------------------------
def hashear(password):
    if not isinstance(password, str) or not password:
        raise ValueError("La contraseña no puede estar vacía.")
    algoritmo = str(db.config_portal("PORTAL_HASH", "argon2") or "argon2").strip().lower()
    if algoritmo == "argon2":
        try:
            from argon2 import PasswordHasher
        except ImportError as e:
            raise ErrorConfiguracion(
                "PORTAL_HASH = 'argon2' pero argon2-cffi no está instalado. "
                "Instalalo con `pip install argon2-cffi`."
            ) from e
        return PasswordHasher().hash(password)
    if algoritmo == "bcrypt":
        try:
            import bcrypt
        except ImportError as e:
            raise ErrorConfiguracion(
                "PORTAL_HASH = 'bcrypt' pero bcrypt no está instalado. "
                "Instalalo con `pip install bcrypt` o volvé a 'argon2'."
            ) from e
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    raise ErrorConfiguracion(
        f"PORTAL_HASH desconocido: {algoritmo!r}. Usá 'argon2' o 'bcrypt'."
    )


def verificar(password, hash_guardado):
    """Verifica detectando el algoritmo por el prefijo del hash guardado.

    Así se puede migrar de argon2 a bcrypt (o al revés) sin invalidar
    las claves ya cargadas: cada hash se verifica con su librería.
    """
    if not password or not hash_guardado:
        return False
    if hash_guardado.startswith("$argon2"):
        try:
            from argon2 import PasswordHasher
            from argon2.exceptions import InvalidHashError, VerificationError
        except ImportError as e:
            raise ErrorConfiguracion(
                "Hay una contraseña guardada con argon2 pero argon2-cffi no está instalado."
            ) from e
        try:
            return bool(PasswordHasher().verify(hash_guardado, password))
        except (VerificationError, InvalidHashError):
            return False
    if hash_guardado.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            import bcrypt
        except ImportError as e:
            raise ErrorConfiguracion(
                "Hay una contraseña guardada con bcrypt pero bcrypt no está instalado."
            ) from e
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("ascii"))
        except (ValueError, TypeError):
            return False
    return False


# --- Token y cookie ----------------------------------------------
def hash_token(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _secreto(secreto=None):
    valor = secreto if secreto is not None else db.config_portal("PORTAL_SECRETO", "")
    if not isinstance(valor, str):
        raise ErrorConfiguracion("PORTAL_SECRETO tiene que ser un texto no vacío.")
    valor = valor.strip()
    if not valor or valor == PLACEHOLDER_SECRETO:
        raise ErrorConfiguracion(
            "PORTAL_SECRETO no está configurado. Copiá config.example.py a "
            "config.py y poné una clave real (ver docs/PORTAL.md)."
        )
    return valor


def firmar_cookie(token, secreto=None):
    if not token:
        raise ValueError("El token de sesión no puede estar vacío.")
    clave = _secreto(secreto).encode("utf-8")
    firma = hmac.new(clave, str(token).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token}.{firma}"


def verificar_cookie(valor, secreto=None):
    if not valor or "." not in valor:
        return None
    token, firma = valor.rsplit(".", 1)
    if not token or not firma:
        return None
    clave = _secreto(secreto).encode("utf-8")
    esperada = hmac.new(clave, token.encode("utf-8"), hashlib.sha256).hexdigest()
    return token if hmac.compare_digest(firma, esperada) else None


# --- Autenticación y sesiones -------------------------------------
def autenticar(identificador, password, ruta=None):
    """Devuelve la persona o None. Acepta persona_id o mail."""
    persona = db.obtener_persona_por_identificador(identificador, ruta=ruta)
    if not persona or not persona["activo"]:
        return None
    credencial = db.obtener_credencial(persona["persona_id"], ruta=ruta)
    if not credencial:
        return None
    return persona if verificar(password, credencial["hash"]) else None


def crear_sesion(persona_id, horas=None, usuario_windows="", maquina="", ruta=None):
    persona = db.obtener_persona(persona_id, ruta=ruta)
    if not persona:
        raise db.PersonaNoEncontrada(f"No existe la persona {persona_id!r}.")
    if not persona["activo"]:
        raise ErrorSesion(f"La persona {persona_id!r} está desactivada.")
    horas = horas_sesion() if horas is None else int(horas)
    if horas <= 0:
        raise ValueError("La sesión tiene que durar al menos una hora.")
    token = secrets.token_urlsafe(32)
    expira = _iso(_ahora() + datetime.timedelta(hours=horas))
    db.crear_sesion(
        hash_token(token), persona["persona_id"], expira,
        usuario_windows=usuario_windows, maquina=maquina, ruta=ruta,
    )
    return token


def validar_sesion(token, tocar=True, horas=None, ruta=None):
    """Devuelve la persona si la sesión vive; si no, None.

    `tocar=True` renueva el vencimiento: la sesión vence por
    inactividad, no por hora fija de inicio.
    """
    if not token:
        return None
    token_hash = hash_token(token)
    fila = db.obtener_sesion(token_hash, ruta=ruta)
    if not fila:
        return None
    ahora = _ahora()
    try:
        vence = datetime.datetime.fromisoformat(fila["expira"])
    except (TypeError, ValueError):
        vence = None
    if vence is not None and vence.tzinfo is None:
        vence = vence.replace(tzinfo=datetime.timezone.utc)
    if vence is None or vence <= ahora:
        db.eliminar_sesion(token_hash, ruta=ruta)
        return None
    persona = db.obtener_persona(fila["persona_id"], ruta=ruta)
    if not persona or not persona["activo"]:
        db.eliminar_sesion(token_hash, ruta=ruta)
        return None
    if tocar:
        horas = horas_sesion() if horas is None else int(horas)
        if horas <= 0:
            raise ValueError("La sesión tiene que durar al menos una hora.")
        db.renovar_sesion(
            token_hash, _iso(ahora + datetime.timedelta(hours=horas)), ruta=ruta
        )
    return persona


def cerrar_sesion(token, ruta=None):
    if not token:
        return False
    return db.eliminar_sesion(hash_token(token), ruta=ruta)


def cerrar_sesiones_persona(persona_id, ruta=None):
    return db.eliminar_sesiones_persona(persona_id, ruta=ruta)


def iniciar_sesion(identificador, password, usuario_windows="", maquina="", ruta=None):
    """Login completo: (token, persona) o (None, None)."""
    persona = autenticar(identificador, password, ruta=ruta)
    if not persona:
        return None, None
    token = crear_sesion(
        persona["persona_id"], usuario_windows=usuario_windows,
        maquina=maquina, ruta=ruta,
    )
    return token, persona


def persona_actual(cookie, ruta=None):
    token = verificar_cookie(cookie)
    return validar_sesion(token, ruta=ruta) if token else None
