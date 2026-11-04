# -*- coding: utf-8 -*-
# ============================================================
#  PORTAL/PERMISOS.PY — Quién puede hacer qué (D18/D19/D25)
# ------------------------------------------------------------
#  El portal no tiene roles: todos los que entran son abogados del
#  estudio y pueden operar. Lo que sí distingue es:
#
#    - la persona autenticada (la sesión del portal),
#    - la identidad de la cédula (la que la generó y la que firma),
#    - y la regla de la cadena (D25): una cédula es de una sola
#      identidad y no se puede cruzar.
#
#  El operador puede ser distinto de la identidad del acto (D18).
#  Por eso `verificar_cadena` compara la identidad de la cédula con
#  la persona autenticada: el portal no escribe cédulas (eso es de
#  `estado.py`), pero sí decide qué puede ver y qué puede tocar.
#
#  La administración por HTTP queda para quien esté en
#  PORTAL_ADMINISTRADORES (lista vacía = nadie); la consola
#  `portal_admin.py` sigue siendo la vía normal.
# ============================================================

import logging

from . import db

LEER_ESTADO = "leer_estado"
ESCRIBIR_ESTADO = "escribir_estado"
LEER_LOG = "leer_log"
AGREGAR_LOG = "agregar_log"
LEER_FICHA = "leer_ficha"
ESCRIBIR_FICHA = "escribir_ficha"
SUBIR_DOCUMENTO = "subir_documento"
DESCARGAR_DOCUMENTO = "descargar_documento"
MARCAR_PRESENTADA = "marcar_presentada"
ADMINISTRAR = "administrar"

ACCIONES = frozenset({
    LEER_ESTADO,
    ESCRIBIR_ESTADO,
    LEER_LOG,
    AGREGAR_LOG,
    LEER_FICHA,
    ESCRIBIR_FICHA,
    SUBIR_DOCUMENTO,
    DESCARGAR_DOCUMENTO,
    MARCAR_PRESENTADA,
    ADMINISTRAR,
})

# Todo el que entra puede operar; administrar es aparte.
ACCIONES_DE_TODOS = ACCIONES - {ADMINISTRAR}


class ErrorPermiso(RuntimeError):
    """La persona autenticada no puede hacer esa acción (o no hay persona)."""


# --- Persona ------------------------------------------------------
def identidad(persona):
    """El persona_id de la persona autenticada, o '' si no hay.

    OJO: es el ID (`santiago`), no el nombre. Para comparar contra
    `identidad_cadena` —que guarda nombres— va `identidad_de`.
    """
    return str((persona or {}).get("persona_id") or "").strip()


def normalizar(texto):
    """Forma de comparación: sin espacios de más y sin distinguir mayúsculas."""
    return " ".join(str(texto or "").split()).casefold()


def personas_config():
    """PERSONAS de config.py, o {} si no hay config en esta máquina."""
    try:
        from config import PERSONAS
    except Exception:
        return {}
    return PERSONAS if isinstance(PERSONAS, dict) else {}


def identidad_de(persona):
    """El NOMBRE canónico de la persona, tal como figura en PERSONAS.

    `identidad_cadena` guarda nombres ("Santiago"), no persona_id
    ("santiago"): comparar contra el persona_id nunca coincide y hacía que
    cualquier cédula propia pareciera ajena. La fuente de verdad del nombre es
    `PERSONAS` de `config.py`; si la persona no está ahí, se usa el `nombre` de
    la base.
    """
    if not isinstance(persona, dict):
        return ""
    pid = str(persona.get("persona_id") or "").strip()
    for nombre, datos in personas_config().items():
        if str((datos or {}).get("persona_id") or "").strip() == pid:
            return str(nombre).strip()
    return str(persona.get("nombre") or "").strip()


def identidades_de(persona):
    """Identidades que esta persona puede ver: la propia y las delegadas."""
    propia = identidad_de(persona)
    pid = str((persona or {}).get("persona_id") or "").strip()
    try:
        delegadas = db.puede_actuar_como(pid)
    except Exception as e:
        # Se sigue con lo propio (la persona ve menos, nunca más), pero el
        # aviso queda: un fallo de la base no puede pasar inadvertido.
        logging.getLogger("portal.permisos").warning(
            "No se pudo leer puede_actuar_como de %r (%s): se usa solo la "
            "identidad propia.", pid, e,
        )
        delegadas = []
    salida, vistas = [], set()
    for valor in [propia, *delegadas]:
        clave = normalizar(valor)
        if clave and clave not in vistas:
            vistas.add(clave)
            salida.append(str(valor).strip())
    return salida


def _puede_ver(cedula, visibles, admin):
    if admin:
        return True
    fijada = cadena_de(cedula)
    if not fijada:
        # Una cédula sin cadena todavía no es de nadie: solo la ve un admin.
        return False
    return normalizar(fijada) in visibles


def puede_ver_cedula(cedula, persona):
    """True si la persona puede ver esa cédula (admin, propia o delegada)."""
    visibles = {normalizar(i) for i in identidades_de(persona)}
    return _puede_ver(cedula, visibles, es_administrador(persona))


def filtrar_cedulas(cedulas, persona):
    """Las cédulas visibles para la persona, en el mismo orden."""
    visibles = {normalizar(i) for i in identidades_de(persona)}
    admin = es_administrador(persona)
    return [c for c in (cedulas or []) if _puede_ver(c, visibles, admin)]


def esta_activa(persona):
    return bool(
        isinstance(persona, dict)
        and persona.get("persona_id")
        and persona.get("activo")
    )


def exigir_activo(persona):
    if not isinstance(persona, dict) or not persona.get("persona_id"):
        raise ErrorPermiso("No hay una persona autenticada en el portal.")
    if not persona.get("activo"):
        raise ErrorPermiso(
            f"La persona {persona.get('persona_id')!r} está desactivada."
        )


# --- Acciones -----------------------------------------------------
def administradores():
    """persona_id habilitados para administrar por HTTP (default: ninguno)."""
    valor = db.config_portal("PORTAL_ADMINISTRADORES", []) or []
    if isinstance(valor, str):
        valor = valor.split(",")
    return {str(p).strip() for p in valor if str(p).strip()}


def es_administrador(persona):
    return bool(identidad(persona) and identidad(persona) in administradores())


def puede(persona, accion):
    if not esta_activa(persona):
        return False
    if accion not in ACCIONES:
        raise ValueError(f"Acción desconocida: {accion!r}.")
    if accion == ADMINISTRAR:
        return es_administrador(persona)
    return True


def exigir(persona, accion):
    exigir_activo(persona)
    if accion not in ACCIONES:
        raise ValueError(f"Acción desconocida: {accion!r}.")
    if not puede(persona, accion):
        nombre = persona.get("nombre") or persona.get("persona_id")
        raise ErrorPermiso(
            f"{nombre!r} no tiene permiso para {accion!r}."
        )


# --- Regla de la cadena (D25) ------------------------------------
def cadena_de(cedula):
    """La identidad grabada en la cédula, o '' si todavía no tiene."""
    if not isinstance(cedula, dict):
        return ""
    return str(cedula.get("identidad_cadena") or "").strip()


def verificar_cadena(cedula, persona):
    """Devuelve la identidad que corresponde usar.

    Compara NOMBRES normalizados (la cadena guarda "Santiago", no "santiago").
    Si la cédula ya tiene una identidad distinta de la persona autenticada —y
    que no está entre las que puede operar— frena con el motivo (D25). Si
    todavía no tiene, devuelve la persona autenticada: el primer acto la fija.
    """
    exigir_activo(persona)
    quien = identidad_de(persona)
    fijada = cadena_de(cedula)
    if fijada and quien and normalizar(fijada) != normalizar(quien):
        delegadas = {normalizar(i) for i in identidades_de(persona)}
        if normalizar(fijada) not in delegadas:
            id_cedula = str((cedula or {}).get("id") or "").strip()
            raise ErrorPermiso(
                f"La cédula {id_cedula!r} es de la identidad {fijada!r} y estás "
                f"actuando como {quien!r}. No se puede cruzar la cadena (D25)."
            )
    return fijada or quien


def fijar_cadena(cedula, persona):
    """Fija la identidad en la cédula si todavía no tiene y la devuelve."""
    quien = verificar_cadena(cedula, persona)
    if isinstance(cedula, dict) and not cadena_de(cedula) and quien:
        cedula["identidad_cadena"] = quien
    return quien
