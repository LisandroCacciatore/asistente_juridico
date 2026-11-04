# -*- coding: utf-8 -*-
# ============================================================
#  PORTAL/CSRF.PY — Token anti-CSRF derivado de la sesión
# ------------------------------------------------------------
#  El token es un HMAC de PORTAL_SECRETO sobre el identificador de la
#  sesión (el valor de la cookie firmada). No se guarda en ningún lado:
#  se recalcula y se compara en tiempo constante.
#
#  Un pedido de escritura sin sesión no exige token: la falta de sesión
#  ya lo rechaza con 401. El login, que todavía no tiene sesión, valida
#  un token anónimo que el formulario trae como campo oculto.
# ============================================================
import hashlib
import hmac

from . import db

#: Cookie con el identificador anónimo que usa el formulario de login.
NOMBRE_COOKIE_ANON = "portal_csrf"

#: Largo del token (40 hex = 160 bits del HMAC-SHA256).
LARGO_TOKEN = 40


def secreto():
    return str(db.config_portal("PORTAL_SECRETO", "") or "")


def token(valor):
    """Token para un identificador (sesión o anónimo). '' si no hay secreto."""
    clave = secreto()
    if not clave or not valor:
        return ""
    return hmac.new(
        clave.encode("utf-8"),
        str(valor).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:LARGO_TOKEN]


def valido(valor, recibido):
    """Compara en tiempo constante el token esperado con el recibido."""
    esperado = token(valor)
    if not esperado or not recibido:
        return False
    return hmac.compare_digest(esperado, str(recibido))
