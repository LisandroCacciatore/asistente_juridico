# -*- coding: utf-8 -*-
# ============================================================
#  SESION.PY — Quién está trabajando, y con qué identidad.
# ------------------------------------------------------------
#  Dos cosas que el sistema no puede confundir (SPEC D18):
#
#    OPERADOR   quién está manejando el asistente          (Jr)
#    IDENTIDAD  con qué matrícula/sesión y con qué firma
#               se ejecutó el acto                (Santiago — LV029)
#
#  Cada uno tiene su propio acceso al SISFE y a FirmAr, así que lo normal
#  es que coincidan. Cuando NO coinciden (alguien operando con la sesión
#  de otro) el log lo tiene que mostrar: por eso van las dos.
#
#  La declaración dura la jornada (SPEC D19): se pide al abrir el
#  asistente, se ve siempre en la barra de arriba, se puede cambiar, y
#  vence al cambiar el día o después de N horas sin actividad.
#
#  OJO: esto NO es un login. Mientras el asistente corra local, el
#  ingreso es una declaración. El login de verdad llega cuando el panel
#  se sirva desde el hub (SPEC D23): recién ahí deja de ser "lo que
#  alguien dijo ser".
# ============================================================

import os
import json
import getpass
import platform

BASE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(BASE, "sesion.json")


def _ahora():
    import datetime
    return datetime.datetime.now()


def usuario_windows():
    """El usuario de la sesión de Windows: el dato que la interfaz no puede
    falsear, y por eso el control cruzado de lo que se declara (D18)."""
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME") or os.environ.get("USER") or "?"


def maquina():
    try:
        return platform.node()
    except Exception:
        return ""


def personas():
    """La lista de personas del estudio, de config.py.

    Sin lista configurada **no se inventa gente**: se devuelve vacío y el
    sistema cae al usuario de Windows, que es el único dato que hay.
    """
    try:
        from config import PERSONAS
    except Exception:
        return {}
    if isinstance(PERSONAS, dict) and PERSONAS:
        return PERSONAS
    return {}


def operadores():
    """Nombres para elegir. Si no hay lista, el de Windows (para que el
    asistente siga siendo usable en una máquina sin configurar)."""
    gente = personas()
    return list(gente) if gente else [usuario_windows()]


def nombre_valido(nombre):
    """Devuelve el nombre tal como está en la lista, o "" si no está.

    No alcanza con que venga un texto: si el nombre no está en la lista no
    se acepta, o cualquiera podría firmar el log con cualquier nombre.

    Acepta el nombre O el mail, porque cada uno entra con su mail (D26);
    adentro y en los registros se usa siempre el nombre.
    """
    buscado = str(nombre or "").strip().lower()
    if not buscado:
        return ""
    for real, datos in personas().items():
        if real.strip().lower() == buscado:
            return real
        mail = ((datos or {}).get("mail") or "").strip().lower()
        if mail and mail == buscado:
            return real
    # Sin lista de personas configurada, el único nombre legítimo es el de
    # la máquina: si no, no habría con qué validar.
    if not personas() and buscado == usuario_windows().strip().lower():
        return usuario_windows()
    return ""


def matricula_de(persona):
    datos = personas().get(persona) or {}
    return (datos.get("matricula") or "").strip()


def mail_de(persona):
    return ((personas().get(persona) or {}).get("mail") or "").strip()


def firma_de(persona):
    return ((personas().get(persona) or {}).get("firma") or "").strip()


def persona_por_matricula(matricula):
    """Qué persona del estudio entra al SISFE con esta matrícula.

    Es la base de la regla de la cadena (D25): las cédulas que salieron de
    esa sesión son de esa persona, y tienen que firmarse con la firma de
    esa persona. Si la matrícula no está en la lista, devuelve "" y la
    cadena se fija después, con la identidad que se elija en el primer
    acto (no se inventa a quién pertenece).
    """
    buscada = str(matricula or "").strip().lower()
    if not buscada:
        return ""
    for real, datos in personas().items():
        if ((datos or {}).get("matricula") or "").strip().lower() == buscada:
            return real
    return ""


def detalle_identidad(persona=None):
    """Texto corto para mostrar y para el log: «Jr — matrícula LV029»."""
    persona = persona or (actual() or {}).get("identidad") or ""
    if not persona:
        return "(identidad sin declarar)"
    mat = matricula_de(persona)
    firma = firma_de(persona)
    if mat:
        return f"{persona} — matrícula {mat}" + (f" · firma {firma}" if firma else "")
    return f"{persona} (sin matrícula cargada)"


def perfil_de(persona=None):
    """La carpeta del perfil de Chrome de esa persona (SPEC D24).

    La sesión del SISFE y la de FirmAr son personales: cada uno entra con
    la suya. Si la persona no está en la lista se usa el perfil de
    siempre, para que el sistema siga andando igual en una máquina que
    todavía no tiene la lista cargada.
    """
    from config_portales import PERFIL_CHROME
    datos = personas().get(persona or "") or {}
    nombre = (datos.get("perfil") or "").strip()
    if not nombre:
        return PERFIL_CHROME
    ruta = nombre if os.path.isabs(nombre) else os.path.join(BASE, nombre)
    return ruta


# ============================================================
#  La jornada
# ============================================================

def _leer():
    if not os.path.isfile(ARCHIVO):
        return None
    try:
        with open(ARCHIVO, encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) and datos.get("operador") else None
    except Exception:
        return None


def _escribir(datos):
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    return datos


def _cuando(texto):
    import datetime
    try:
        return datetime.datetime.fromisoformat(texto)
    except Exception:
        return None


def _ajustes():
    """Los dos ajustes de vencimiento, de config.py, con defaults sanos."""
    dia, horas = True, 12
    try:
        from config import SESION_VENCE_AL_CAMBIAR_EL_DIA, SESION_HORAS_INACTIVIDAD
        dia = bool(SESION_VENCE_AL_CAMBIAR_EL_DIA)
        horas = int(SESION_HORAS_INACTIVIDAD)
    except Exception:
        pass
    return dia, horas


def vencida(sesion, ahora=None, vence_al_cambiar_el_dia=True, horas_inactividad=12):
    """¿Hay que volver a preguntar? Función pura: se prueba sin reloj real.

    Vence al cambiar el día (nadie declara quién es y sigue siendo válido
    al otro día) y también por inactividad, que es lo que cubre la máquina
    que quedó abierta y sin nadie.
    """
    import datetime
    if not sesion or not sesion.get("operador"):
        return True
    ahora = ahora or _ahora()
    ultimo = _cuando(sesion.get("ultimo_uso") or sesion.get("inicio") or "")
    if ultimo is None:
        return True
    if vence_al_cambiar_el_dia and ultimo.date() != ahora.date():
        return True
    if horas_inactividad and (ahora - ultimo) > datetime.timedelta(hours=horas_inactividad):
        return True
    return False


def actual(tocar=False):
    """La jornada en curso, o None si no hay o si venció.

    `tocar=True` marca actividad (lo usa el panel cuando se refresca):
    sin eso, la máquina que quedó abierta sin nadie seguiría contando
    como "trabajando".
    """
    sesion = _leer()
    dia, horas = _ajustes()
    if vencida(sesion, vence_al_cambiar_el_dia=dia, horas_inactividad=horas):
        return None
    if tocar:
        sesion["ultimo_uso"] = _ahora().isoformat(timespec="seconds")
        _escribir(sesion)
    return sesion


def declarar(operador, identidad=None, cuando=None):
    """Arranca (o cambia) la jornada. Devuelve la sesión o lanza ValueError.

    `identidad` es con qué matrícula/sesión va a actuar; si no se dice,
    actúa con la suya, que es lo normal (D18).
    """
    nombre = nombre_valido(operador)
    if not nombre:
        raise ValueError(
            f"«{operador}» no está en la lista de personas del estudio. "
            "Agregalo en config.py antes de usarlo."
        )
    ident = nombre_valido(identidad) if identidad else nombre
    if not ident:
        raise ValueError(f"«{identidad}» no está en la lista de personas del estudio.")

    momento = (cuando or _ahora()).isoformat(timespec="seconds")
    return _escribir({
        "operador": nombre,
        "identidad": ident,
        "mail_operador": mail_de(nombre),
        "inicio": momento,
        "ultimo_uso": momento,
        "maquina": maquina(),
        "usuario_windows": usuario_windows(),
    })


def cerrar():
    """Cierra la jornada (para que el próximo que se siente declare)."""
    try:
        if os.path.isfile(ARCHIVO):
            os.remove(ARCHIVO)
    except Exception:
        pass


def estado_para_el_panel(tocar=False):
    """Lo que el panel necesita para dibujar la puerta y la barra de arriba.

    `tocar=True` marca actividad: el panel se refresca solo cada 60 s, así
    que mientras está abierto la jornada sigue viva (y si nadie lo mira
    por 12 horas, vence y vuelve a preguntar).
    """
    sesion = actual(tocar=tocar)
    return {
        "declarada": sesion is not None,
        "operador": (sesion or {}).get("operador", ""),
        "identidad": (sesion or {}).get("identidad", ""),
        "inicio": (sesion or {}).get("inicio", ""),
        "usuario_windows": usuario_windows(),
        "maquina": maquina(),
        "identidad_detalle": detalle_identidad((sesion or {}).get("identidad")) if sesion else "",
        "opciones": operadores(),
    }


# ============================================================
#  La confirmación antes de tocar el portal (SPEC D19)
# ============================================================

def pausar_con_identidad(pausar, identidad=None):
    """Envuelve una pausa para que ANTES de tocar el portal diga con qué
    identidad se va a actuar.

    Antes del portal no se vuelve a preguntar quién sos (ya se declaró al
    abrir el asistente): se confirma en pantalla, que es distinto.
    """
    identidad = identidad or identidad_para_el_acto()
    # La identidad se dice UNA vez por trabajo: en la firma en lote hay una
    # pausa por documento y repetir el aviso cinco veces es ruido.
    primera = {"vez": True}

    def envuelta(mensaje, *args, **kwargs):
        jornada = actual() or {}
        operador = jornada.get("operador") or usuario_windows()
        quien = identidad or jornada.get("identidad")

        if quien:
            aviso = f"Vas a actuar con la identidad de {detalle_identidad(quien)}."
        elif personas():
            # Hay lista de gente pero nadie se declaró: no se inventa una
            # identidad con el nombre de la máquina, porque eso haría creer
            # que sí se sabe quién está firmando.
            aviso = ("No hay una identidad declarada para este acto: "
                     "fijate quién está trabajando antes de seguir.")
        else:
            # Máquina sin la lista cargada (un solo usuario): la identidad
            # es la del usuario de Windows, y se dice tal cual.
            aviso = (f"Esta máquina no tiene la lista de personas cargada: se va "
                     f"a usar la identidad del usuario {operador}.")

        if not primera["vez"]:
            return pausar(mensaje, *args, **kwargs)
        primera["vez"] = False
        return pausar(f"{aviso}\nOperador registrado: {operador}.\n\n{mensaje}",
                      *args, **kwargs)
    return envuelta


def identidad_para_el_acto(identidad=None):
    """Con qué identidad se va a ejecutar ESTE acto.

    Si el que llama dice una (alguien operando con la sesión de otro: la
    excepción tolerada de D18), vale esa. Si no, la de la jornada. Nunca
    inventa: sin ninguna, devuelve "" y el llamador decide qué hacer.
    """
    explicita = nombre_valido(identidad) if identidad else ""
    if explicita:
        return explicita
    return (actual() or {}).get("identidad") or ""
