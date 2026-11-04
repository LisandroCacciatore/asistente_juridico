# -*- coding: utf-8 -*-
# ============================================================
#  PORTAL_ADMIN.PY — Administración del portal por consola
# ------------------------------------------------------------
#  Crea la base, siembra las personas de config.py y maneja las
#  contraseñas. No hay panel de administración todavía: esto es
#  lo mínimo para dejar el login funcionando.
#
#  Uso:
#    python portal_admin.py init
#    python portal_admin.py listar
#    python portal_admin.py password santiago
#    python portal_admin.py desactivar jr
# ============================================================

import argparse
import getpass
import re
import sys

from portal import auth, db

MIN_LARGO_PASSWORD = 8


def _slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", str(texto or "").strip().lower()).strip("-")


def sembrar_desde_config(personas=None, ruta=None):
    """Copia PERSONAS de config.py a la base.

    Solo los datos que se centralizan (D21): persona_id, nombre, mail y
    matrícula. `firma` y `perfil` son de cada máquina y no se guardan.
    Es idempotente: si la persona ya existe, actualiza esos campos.
    """
    if personas is None:
        try:
            from config import PERSONAS
            personas = PERSONAS
        except Exception:
            personas = {}
    if not isinstance(personas, dict):
        return []
    sembradas = []
    for nombre, datos in personas.items():
        datos = datos if isinstance(datos, dict) else {}
        persona_id = str(datos.get("persona_id") or _slug(nombre)).strip()
        if not persona_id:
            continue
        mail = str(datos.get("mail") or "").strip()
        matricula = str(datos.get("matricula") or "").strip()
        if db.obtener_persona(persona_id, ruta=ruta):
            db.actualizar_persona(
                persona_id, nombre=str(nombre), mail=mail,
                matricula=matricula, ruta=ruta,
            )
        else:
            db.crear_persona(
                persona_id, str(nombre), mail=mail,
                matricula=matricula, ruta=ruta,
            )
        sembradas.append(persona_id)
    return sembradas


def guardar_password(persona_id, password, ruta=None):
    if not isinstance(password, str) or len(password) < MIN_LARGO_PASSWORD:
        raise ValueError(
            f"La contraseña tiene que tener al menos {MIN_LARGO_PASSWORD} caracteres."
        )
    if not db.obtener_persona(persona_id, ruta=ruta):
        raise db.PersonaNoEncontrada(f"No existe la persona {persona_id!r}.")
    # Una clave puesta desde la consola es provisoria: se cambia al entrar.
    db.guardar_credencial(
        persona_id, auth.hashear(password), debe_cambiar=1, ruta=ruta
    )
    return True


def auditar(accion, detalle="", ruta=None):
    """Deja rastro en `auditoria` de lo que se hace desde la consola.

    Firma como "cli" y agrega el usuario de Windows al detalle: si no, no se
    sabe desde qué cuenta de la máquina se hizo. Si la auditoría falla, avisa
    por stderr y sigue: no puede tumbar una operación que ya se hizo.
    """
    try:
        usuario, _maquina = db.quien()
    except Exception:
        usuario = ""
    texto = f"{detalle} [{usuario}]".strip()
    try:
        db.registrar_auditoria(
            persona_id="cli", accion=accion, ip="", detalle=texto[:80], ruta=ruta
        )
    except Exception as e:
        print(f"AVISO: no se pudo auditar {accion!r}: {e}", file=sys.stderr)


def pedir_password():
    primera = getpass.getpass("Contraseña: ")
    segunda = getpass.getpass("Repetir contraseña: ")
    if primera != segunda:
        raise ValueError("Las contraseñas no coinciden.")
    return primera


def listar(ruta=None):
    filas = db.listar_personas(ruta=ruta)
    if not filas:
        print("No hay personas cargadas. Corré: python portal_admin.py init")
        return []
    print(
        f"{'persona_id':<14} {'nombre':<22} {'mail':<30} {'matricula':<12} "
        f"{'activo':<7} {'clave':<6} {'actua como':<20} {'sesiones':>8}"
    )
    for persona in filas:
        credencial = db.obtener_credencial(persona["persona_id"], ruta=ruta)
        sesiones = db.contar_sesiones(persona["persona_id"], ruta=ruta)
        actua = (persona.get("puede_actuar_como") or "-")[:20]
        print(
            f"{persona['persona_id']:<14} {persona['nombre'][:22]:<22} "
            f"{persona['mail'][:30]:<30} {persona['matricula'][:12]:<12} "
            f"{'si' if persona['activo'] else 'no':<7} "
            f"{'si' if credencial else 'no':<6} {actua:<20} {sesiones:>8}"
        )
    return filas


def _ruta_mostrada(ruta):
    return db.ruta_db() if ruta is None else ruta


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="portal_admin.py",
        description="Administración del portal del estudio.",
    )
    parser.add_argument("--db", default=None, help="Ruta de portal.db (por defecto, la de config.py).")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("init", help="Crea la base y siembra las personas de config.py.")
    p.add_argument("--sin-sembrar", action="store_true", help="No copiar PERSONAS de config.py.")

    sub.add_parser("sembrar", help="Copia/actualiza las personas de config.py en la base.")

    p = sub.add_parser("crear", help="Crea una persona.")
    p.add_argument("persona_id")
    p.add_argument("nombre")
    p.add_argument("--mail", default="")
    p.add_argument("--matricula", default="")

    p = sub.add_parser("password", help="Cambia la contraseña de una persona (la pide por consola).")
    p.add_argument("persona_id")

    sub.add_parser("listar", help="Lista personas, si tienen clave y sesiones activas.")

    p = sub.add_parser("activar", help="Reactiva una persona.")
    p.add_argument("persona_id")

    p = sub.add_parser("desactivar", help="Desactiva una persona y cierra sus sesiones.")
    p.add_argument("persona_id")

    p = sub.add_parser("sesiones-borrar", help="Borra las sesiones (todas o de una persona).")
    p.add_argument("persona_id", nargs="?")

    p = sub.add_parser(
        "puede-actuar",
        help="Fija qué identidades puede operar una persona (además de la propia).",
    )
    p.add_argument("persona_id")
    p.add_argument(
        "identidades", nargs="*",
        help="Nombres tal como figuran en PERSONAS (ej. Santiago Jr).",
    )
    p.add_argument("--limpiar", action="store_true", help="Deja la lista vacía.")

    args = parser.parse_args(argv)
    ruta = args.db

    try:
        db.inicializar(ruta)
        if args.comando == "init":
            if args.sin_sembrar:
                print(f"Base creada en {_ruta_mostrada(ruta)}")
            else:
                ids = sembrar_desde_config(ruta=ruta)
                print(
                    f"Base creada en {_ruta_mostrada(ruta)}. "
                    f"Personas sembradas: {len(ids)}"
                )
        elif args.comando == "sembrar":
            ids = sembrar_desde_config(ruta=ruta)
            detalle = ", ".join(ids) if ids else "ninguna"
            print(f"Personas sembradas/actualizadas: {len(ids)} ({detalle})")
        elif args.comando == "crear":
            persona = db.crear_persona(
                args.persona_id, args.nombre, mail=args.mail,
                matricula=args.matricula, ruta=ruta,
            )
            auditar("cli_persona_creada", persona["persona_id"], ruta)
            print(f"Persona creada: {persona['persona_id']} ({persona['nombre']})")
        elif args.comando == "password":
            guardar_password(args.persona_id, pedir_password(), ruta=ruta)
            auditar("cli_password_actualizada", args.persona_id, ruta)
            print(f"Contraseña actualizada para {args.persona_id}.")
        elif args.comando == "listar":
            listar(ruta=ruta)
        elif args.comando == "activar":
            db.activar_persona(args.persona_id, ruta=ruta)
            print(f"Persona activada: {args.persona_id}")
        elif args.comando == "desactivar":
            db.desactivar_persona(args.persona_id, ruta=ruta)
            auditar("cli_persona_desactivada", args.persona_id, ruta)
            print(f"Persona desactivada y sesiones cerradas: {args.persona_id}")
        elif args.comando == "sesiones-borrar":
            if args.persona_id:
                cantidad = db.eliminar_sesiones_persona(args.persona_id, ruta=ruta)
            else:
                cantidad = db.eliminar_todas_las_sesiones(ruta=ruta)
            print(f"Sesiones borradas: {cantidad}")
        elif args.comando == "puede-actuar":
            identidades = [] if args.limpiar else args.identidades
            persona = db.fijar_puede_actuar_como(args.persona_id, identidades, ruta=ruta)
            auditar(
                "cli_puede_actuar",
                f"{args.persona_id}: {persona.get('puede_actuar_como') or '-'}",
                ruta,
            )
            print(
                f"{persona['persona_id']} puede actuar como: "
                f"{persona.get('puede_actuar_como') or '(ninguna)'}"
            )
        return 0
    except (ValueError, db.ErrorPortal, auth.ErrorConfiguracion) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
