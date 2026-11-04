# -*- coding: utf-8 -*-
# ============================================================
#  PORTAL/SERVIDOR_PORTAL.PY — El hub (Fase 10b)
# ------------------------------------------------------------
#  Servidor HTTP del portal: login real (D23), estado/log/ficha
#  centralizados (D21) y anti-duplicado central (D22).
#
#  Escucha SIEMPRE en 127.0.0.1 (PORTAL_HOST). Para entrar desde
#  otra máquina se pone Tailscale Serve delante; nunca se abre a
#  0.0.0.0 en una PC con datos de clientes.
#
#  ARRANCAR:
#     python -m portal.servidor_portal
#  o el acceso directo `Iniciar_Portal.bat`.
# ============================================================

import hashlib
import html
import os
import re
import secrets
from urllib.parse import quote, urlsplit

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from pydantic import BaseModel

from . import auth, db, permisos

MIN_LARGO_PASSWORD = 8

app = FastAPI(title="Portal del Estudio Segovia")

# CORS: por defecto vacío (el panel y la API son el mismo origen). Solo se
# abre si PORTAL_ORIGENES tiene algo, y siempre con credentials para que la
# cookie de sesión viaje.
_origenes_cfg = db.config_portal("PORTAL_ORIGENES", []) or []
if isinstance(_origenes_cfg, str):
    _origenes_cfg = [o.strip() for o in _origenes_cfg.split(",") if o.strip()]
_ORIGENES = list(_origenes_cfg)
if _ORIGENES:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_ORIGENES,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def _proteger_csrf(request: Request, call_next):
    """Anti-CSRF: en mutaciones, el Origin tiene que ser el Host o uno permitido.

    Los pedidos sin Origin (scripts locales, curl) pasan; el navegador
    siempre manda Origin en un POST/PUT cross-site, así que un sitio
    externo no puede usar la cookie del portal.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin:
            host = request.headers.get("host", "")
            try:
                origen_host = urlsplit(origin).netloc
            except ValueError:
                origen_host = ""
            permitidos = {urlsplit(o).netloc for o in _ORIGENES if o}
            if origen_host and origen_host != host and origen_host not in permitidos:
                return JSONResponse(
                    {"ok": False, "error": "Origen no permitido"}, status_code=403
                )
    return await call_next(request)


@app.middleware("http")
async def _cabeceras_seguridad(request: Request, call_next):
    """Cabeceras que el navegador no puede dejar de recibir.

    `nosniff` evita que el navegador adivine el tipo de archivo y ejecute
    como HTML algo que se sirvió como PDF. `DENY` impide embeber el portal
    en un iframe ajeno (clickjacking). Se agregan al final, así también
    cubren las respuestas de error.
    """
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    return respuesta


# --- Errores ------------------------------------------------------
@app.exception_handler(permisos.ErrorPermiso)
async def _error_permiso(request: Request, exc: permisos.ErrorPermiso):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=403)


@app.exception_handler(db.CedulaNoEncontrada)
async def _error_cedula(request: Request, exc: db.CedulaNoEncontrada):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)


@app.exception_handler(db.YaPresentada)
async def _error_duplicado(request: Request, exc: db.YaPresentada):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)


@app.exception_handler(db.ConflictoCadena)
async def _error_cadena(request: Request, exc: db.ConflictoCadena):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=403)


@app.exception_handler(db.PersonaNoEncontrada)
async def _error_persona(request: Request, exc: db.PersonaNoEncontrada):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)


@app.exception_handler(db.ErrorPortal)
async def _error_portal(request: Request, exc: db.ErrorPortal):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.exception_handler(auth.ErrorConfiguracion)
async def _error_config(request: Request, exc: auth.ErrorConfiguracion):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.exception_handler(auth.ErrorSesion)
async def _error_sesion(request: Request, exc: auth.ErrorSesion):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=403)


@app.exception_handler(ValueError)
async def _error_valor(request: Request, exc: ValueError):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


# --- Modelos ------------------------------------------------------
class FichaIn(BaseModel):
    datos: dict


class PersonaIn(BaseModel):
    persona_id: str
    nombre: str
    mail: str = ""
    matricula: str = ""
    password: str = ""


class PersonaUpdate(BaseModel):
    nombre: str | None = None
    mail: str | None = None
    matricula: str | None = None
    activo: bool | None = None


class PasswordIn(BaseModel):
    password: str


# --- Persona autenticada -----------------------------------------
def _persona(request: Request):
    persona = auth.persona_actual(request.cookies.get(auth.NOMBRE_COOKIE))
    if not persona:
        raise HTTPException(status_code=401, detail="Sesión vencida o inexistente.")
    return persona


def _persona_opcional(request: Request):
    cookie = request.cookies.get(auth.NOMBRE_COOKIE)
    return auth.persona_actual(cookie) if cookie else None


def _publica(persona):
    return {
        "persona_id": persona.get("persona_id", ""),
        "nombre": persona.get("nombre", ""),
        "mail": persona.get("mail", ""),
        "matricula": persona.get("matricula", ""),
        "activo": bool(persona.get("activo")),
    }


def _nombre_seguro(nombre):
    """Nombre de archivo sin rutas ni caracteres raros."""
    nombre = os.path.basename(str(nombre or "")).strip()
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "_", nombre)
    nombre = nombre.strip("._") or "documento.pdf"
    return nombre[:120]


def _ip_cliente(request):
    """IP del cliente para la auditoría ('' si no se puede saber)."""
    cliente = getattr(request, "client", None)
    return str(getattr(cliente, "host", "") or "")


def _registrar_log(persona, request, accion, id_cedula="", caratula="",
                   cuij="", detalle=""):
    """Deja en `log_acciones` (tabla del portal) un acto sobre una CÉDULA.

    Solo para cédulas: el login, el logout y los rechazos van a
    `auditoria` y no ensucian este log. Recibe la persona ya resuelta.
    Lo usan los endpoints que actúan sobre cédulas (ver commit 4).
    """
    # `identidad_cadena` guarda el NOMBRE (ej. "Santiago"), no el persona_id.
    return db.agregar_log(
        accion,
        id_cedula=id_cedula,
        caratula=caratula,
        cuij=cuij,
        detalle=detalle,
        usuario="portal",
        maquina=_ip_cliente(request),
        operador=persona["nombre"],
        identidad=persona["nombre"],
        persona_id=persona["persona_id"],
    )


def _cuij_seguro(cuij):
    """CUIJ apto para nombrar una carpeta: solo letras, números y guiones."""
    limpio = re.sub(r"[^0-9A-Za-z-]+", "", str(cuij or ""))
    return limpio[:80]


def _dentro_de_uploads(ruta):
    """True solo si `ruta` queda dentro de PORTAL_UPLOADS.

    Se resuelven symlinks y se normaliza el caso (Windows) antes de
    comparar: una metadata vieja o un nombre armado con `..` no puede
    hacer que el servidor lea o escriba fuera de la carpeta de subidas.
    """
    raiz = os.path.normcase(os.path.realpath(db.ruta_uploads()))
    destino = os.path.normcase(os.path.realpath(ruta))
    try:
        return os.path.commonpath([destino, raiz]) == raiz
    except ValueError:
        return False


# --- Login / sesión ----------------------------------------------
@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    if _persona_opcional(request):
        return RedirectResponse("/panel", status_code=303)
    return HTMLResponse(_html_login())


@app.post("/login")
def login(
    request: Request,
    identificador: str = Form(...),
    password: str = Form(...),
):
    usuario, maquina = db.quien()
    token = None
    persona = None
    try:
        token, persona = auth.iniciar_sesion(
            identificador, password, usuario_windows=usuario, maquina=maquina
        )
        cookie = auth.firmar_cookie(token) if token else ""
    except auth.ErrorConfiguracion as e:
        if token:
            auth.cerrar_sesion(token)
        return HTMLResponse(
            _html_login(f"El portal no está configurado: {e}"), status_code=500
        )
    if not token:
        db.registrar_auditoria(
            persona_id=identificador or "",
            accion="login_fallido",
            ip=_ip_cliente(request),
            detalle=str(identificador or ""),
        )
        return HTMLResponse(
            _html_login("Usuario o contraseña incorrectos."), status_code=401
        )
    db.registrar_auditoria(
        persona_id=persona["persona_id"],
        accion="login",
        ip=_ip_cliente(request),
        detalle="",
    )
    respuesta = RedirectResponse("/panel", status_code=303)
    respuesta.set_cookie(auth.NOMBRE_COOKIE, cookie, **auth.opciones_cookie())
    return respuesta


@app.post("/logout")
def logout(request: Request):
    token = auth.verificar_cookie(request.cookies.get(auth.NOMBRE_COOKIE))
    # La persona se lee ANTES de cerrar la sesión: después ya no existe.
    persona = auth.persona_actual(request.cookies.get(auth.NOMBRE_COOKIE))
    if token:
        auth.cerrar_sesion(token)
    db.registrar_auditoria(
        persona_id=(persona or {}).get("persona_id", ""),
        accion="logout",
        ip=_ip_cliente(request),
        detalle="",
    )
    respuesta = RedirectResponse("/", status_code=303)
    respuesta.delete_cookie(auth.NOMBRE_COOKIE, path="/")
    return respuesta


@app.get("/api/sesion")
def api_sesion(persona=Depends(_persona)):
    return {"ok": True, "persona": _publica(persona)}


@app.get("/api/salud")
def api_salud():
    try:
        db.leer_estado()
    except Exception:
        return JSONResponse({"ok": False, "error": "La base no responde."}, status_code=503)
    return {"ok": True, "portal": "estudio"}


# --- Estado -------------------------------------------------------
@app.get("/api/estado")
def api_estado(persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_ESTADO)
    return {
        "ok": True,
        "version": db.version_estado(),
        "datos": db.leer_estado(),
    }


# --- Cédulas ------------------------------------------------------
@app.get("/api/cedulas")
def api_cedulas(estado: str | None = None, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_ESTADO)
    cedulas = db.leer_estado().get("cedulas", [])
    if estado:
        cedulas = [c for c in cedulas if c.get("estado") == estado]
    return {"ok": True, "cedulas": cedulas}


@app.get("/api/cedulas/{id_cedula}")
def api_cedula(id_cedula: str, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_ESTADO)
    cedula = db.buscar_cedula(id_cedula)
    if cedula is None:
        raise db.CedulaNoEncontrada(
            f"No existe la cédula {id_cedula!r} en el estado central."
        )
    return {"ok": True, "cedula": cedula}


# --- Log ----------------------------------------------------------
@app.get("/api/log")
def api_log(limite: int = 50, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_LOG)
    return {"ok": True, "entradas": db.leer_log(limite=limite)}


# --- Ficha del cliente -------------------------------------------
@app.get("/api/ficha/{cuij}")
def api_ficha(cuij: str, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_FICHA)
    ficha = db.leer_ficha(cuij)
    if ficha is None:
        raise HTTPException(status_code=404, detail="No hay ficha para ese CUIJ.")
    return {"ok": True, "ficha": ficha}


@app.put("/api/ficha/{cuij}")
def api_guardar_ficha(cuij: str, entrada: FichaIn, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.ESCRIBIR_FICHA)
    ficha = db.guardar_ficha(
        cuij, entrada.datos, persona_id=persona["persona_id"]
    )
    db.agregar_log(
        "ficha_actualizada",
        cuij=cuij,
        operador=persona["nombre"],
        identidad=persona["persona_id"],
        persona_id=persona["persona_id"],
    )
    return {"ok": True, "ficha": ficha}


# --- Documentos ---------------------------------------------------
@app.get("/api/documentos")
def api_documentos(cuij: str | None = None, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_FICHA)
    return {"ok": True, "documentos": db.listar_documentos(cuij=cuij)}


@app.post("/api/documentos")
def api_subir_documento(
    archivo: UploadFile = File(...),
    cuij: str = Form(""),
    persona=Depends(_persona),
):
    permisos.exigir(persona, permisos.SUBIR_DOCUMENTO)
    nombre = _nombre_seguro(archivo.filename)
    if not nombre.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")

    cabecera = archivo.file.read(5)
    archivo.file.seek(0)
    if cabecera != b"%PDF-":
        raise HTTPException(
            status_code=400,
            detail="El archivo no empieza con la cabecera PDF (%PDF-).",
        )

    try:
        max_mb = int(db.config_portal("PORTAL_MAX_SUBIDA_MB", 25))
    except (TypeError, ValueError):
        max_mb = 25
    max_bytes = max(1, max_mb) * 1024 * 1024

    carpeta = os.path.join(db.ruta_uploads(), _cuij_seguro(cuij) or "sin_cuij")
    documento_id = secrets.token_hex(8)
    destino = os.path.join(carpeta, f"{documento_id}_{nombre}")
    if not _dentro_de_uploads(carpeta) or not _dentro_de_uploads(destino):
        raise HTTPException(
            status_code=400,
            detail="El CUIJ no es válido para armar la carpeta de subida.",
        )
    os.makedirs(carpeta, exist_ok=True)

    sha = hashlib.sha256()
    total = 0
    try:
        with open(destino, "wb") as salida:
            while True:
                bloque = archivo.file.read(1024 * 1024)
                if not bloque:
                    break
                total += len(bloque)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"El PDF supera el tope de {max_mb} MB.",
                    )
                sha.update(bloque)
                salida.write(bloque)
    except BaseException:
        if os.path.exists(destino):
            os.remove(destino)
        raise

    documento = db.registrar_documento(
        nombre,
        destino,
        sha.hexdigest(),
        tamano=total,
        cuij=cuij,
        subido_por=persona["persona_id"],
        documento_id=documento_id,
    )
    db.agregar_log(
        "documento_subido",
        cuij=cuij,
        detalle=f"{nombre} ({total} bytes)",
        operador=persona["nombre"],
        identidad=persona["persona_id"],
        persona_id=persona["persona_id"],
    )
    return {"ok": True, "documento": documento}


@app.get("/api/documentos/{documento_id}")
def api_descargar_documento(documento_id: str, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.DESCARGAR_DOCUMENTO)
    documento = db.obtener_documento(documento_id)
    if documento is None:
        raise HTTPException(status_code=404, detail="No existe ese documento.")
    ruta = documento.get("ruta", "")
    if not _dentro_de_uploads(ruta):
        raise HTTPException(
            status_code=403, detail="El documento está fuera de la carpeta del portal."
        )
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail="El archivo ya no está en el disco.")
    return FileResponse(
        ruta,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{documento.get("nombre", "documento.pdf")}"'
        },
    )


# --- Personas (lectura) ------------------------------------------
@app.get("/api/personas")
def api_personas(persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_ESTADO)
    return {
        "ok": True,
        "personas": [_publica(p) for p in db.listar_personas() if p["activo"]],
    }


# --- Administración por HTTP (solo PORTAL_ADMINISTRADORES) -------
def _exigir_admin(persona):
    permisos.exigir(persona, permisos.ADMINISTRAR)


def _password_valida(password):
    if not isinstance(password, str) or len(password) < MIN_LARGO_PASSWORD:
        raise ValueError(
            f"La contraseña tiene que tener al menos {MIN_LARGO_PASSWORD} caracteres."
        )


@app.get("/api/admin/personas")
def api_admin_personas(persona=Depends(_persona)):
    _exigir_admin(persona)
    return {"ok": True, "personas": [_publica(p) for p in db.listar_personas()]}


@app.post("/api/admin/personas")
def api_admin_crear_persona(entrada: PersonaIn, persona=Depends(_persona)):
    _exigir_admin(persona)
    hash_guardado = ""
    if entrada.password:
        _password_valida(entrada.password)
        hash_guardado = auth.hashear(entrada.password)
    creada = db.crear_persona(
        entrada.persona_id,
        entrada.nombre,
        mail=entrada.mail,
        matricula=entrada.matricula,
    )
    if hash_guardado:
        db.guardar_credencial(creada["persona_id"], hash_guardado)
    db.agregar_log(
        "persona_creada",
        detalle=creada["persona_id"],
        operador=persona["nombre"],
        identidad=persona["persona_id"],
        persona_id=persona["persona_id"],
    )
    return {"ok": True, "persona": _publica(creada)}


@app.put("/api/admin/personas/{persona_id}")
def api_admin_actualizar_persona(
    persona_id: str, entrada: PersonaUpdate, persona=Depends(_persona)
):
    _exigir_admin(persona)
    actualizada = db.actualizar_persona(
        persona_id,
        nombre=entrada.nombre,
        mail=entrada.mail,
        matricula=entrada.matricula,
        activo=entrada.activo,
    )
    db.agregar_log(
        "persona_actualizada",
        detalle=persona_id,
        operador=persona["nombre"],
        identidad=persona["persona_id"],
        persona_id=persona["persona_id"],
    )
    return {"ok": True, "persona": _publica(actualizada)}


@app.post("/api/admin/personas/{persona_id}/password")
def api_admin_password(
    persona_id: str, entrada: PasswordIn, persona=Depends(_persona)
):
    _exigir_admin(persona)
    _password_valida(entrada.password)
    if not db.obtener_persona(persona_id):
        raise db.PersonaNoEncontrada(f"No existe la persona {persona_id!r}.")
    db.guardar_credencial(persona_id, auth.hashear(entrada.password))
    db.agregar_log(
        "password_actualizada",
        detalle=persona_id,
        operador=persona["nombre"],
        identidad=persona["persona_id"],
        persona_id=persona["persona_id"],
    )
    return {"ok": True}


@app.post("/api/admin/personas/{persona_id}/desactivar")
def api_admin_desactivar(persona_id: str, persona=Depends(_persona)):
    _exigir_admin(persona)
    desactivada = db.desactivar_persona(persona_id)
    db.agregar_log(
        "persona_desactivada",
        detalle=persona_id,
        operador=persona["nombre"],
        identidad=persona["persona_id"],
        persona_id=persona["persona_id"],
    )
    return {"ok": True, "persona": _publica(desactivada)}


@app.post("/api/admin/sesiones-borrar")
def api_admin_borrar_sesiones(persona=Depends(_persona)):
    _exigir_admin(persona)
    borradas = db.eliminar_todas_las_sesiones()
    db.agregar_log(
        "sesiones_borradas",
        detalle=str(borradas),
        operador=persona["nombre"],
        identidad=persona["persona_id"],
        persona_id=persona["persona_id"],
    )
    return {"ok": True, "borradas": borradas}


# --- Panel --------------------------------------------------------
@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request, cuij: str | None = None):
    persona = _persona_opcional(request)
    if not persona:
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(_html_panel(persona, cuij=cuij))


# --- HTML ---------------------------------------------------------
def _e(valor):
    return html.escape(str(valor if valor is not None else ""))


_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0;
       background: #f2f4f7; color: #18202a; }
header { background: #1d3557; color: #fff; padding: 12px 20px; display: flex;
         align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
header h1 { font-size: 1.1rem; margin: 0; }
header .quien { font-size: .95rem; opacity: .95; }
header form { margin: 0; }
header button { background: transparent; border: 1px solid #ffffff88; color: #fff;
                padding: 6px 12px; border-radius: 6px; cursor: pointer; }
main { max-width: 1100px; margin: 0 auto; padding: 20px; }
.tarjeta { background: #fff; border-radius: 10px; padding: 22px; max-width: 420px;
           margin: 10vh auto; box-shadow: 0 8px 30px #0002; }
.tarjeta h1 { margin-top: 0; }
label { display: block; margin: 12px 0 4px; font-weight: 600; }
input[type=text], input[type=password], input[name=identificador], input[name=cuij] {
  width: 100%; padding: 10px; border: 1px solid #c9d1db; border-radius: 6px; font: inherit; }
button.principal, .tarjeta button { background: #1d3557; color: #fff; border: 0;
  padding: 10px 16px; border-radius: 6px; cursor: pointer; font: inherit; }
button.principal:hover, .tarjeta button:hover { background: #2a4a78; }
.error { color: #b00020; background: #ffe9ec; padding: 8px 10px; border-radius: 6px; }
.resumen { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
.resumen div { background: #fff; border-radius: 8px; padding: 12px 16px; min-width: 150px;
               box-shadow: 0 2px 10px #0001; }
.resumen strong { display: block; font-size: 1.4rem; }
section { background: #fff; border-radius: 10px; padding: 18px; margin-bottom: 18px;
          box-shadow: 0 2px 10px #0001; overflow-x: auto; }
section h2 { margin-top: 0; font-size: 1rem; }
table { width: 100%; border-collapse: collapse; font-size: .92rem; }
th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid #e6e9ee; vertical-align: top; }
th { color: #556; font-weight: 600; }
td button { background: #e8eef7; border: 1px solid #b9c8dd; color: #1d3557;
            padding: 5px 9px; border-radius: 5px; cursor: pointer; margin: 1px; }
td button:hover { background: #d7e3f4; }
a { color: #1d4f91; }
pre { background: #0f1720; color: #e6edf3; padding: 12px; border-radius: 8px;
      overflow-x: auto; font-size: .85rem; }
textarea { width: 100%; min-height: 90px; padding: 10px; border: 1px solid #c9d1db;
           border-radius: 6px; font: inherit; }
.aviso { color: #556; }
"""

_JS = """
async function pedir(url, opciones) {
  const r = await fetch(url, opciones || {});
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    alert(data.detail || data.error || 'Error');
    return null;
  }
  location.reload();
  return data;
}
function subir(e) {
  e.preventDefault();
  return pedir('/api/documentos', {method: 'POST', body: new FormData(e.target)});
}
function guardarNotas() {
  const boton = document.getElementById('guardar-notas');
  if (!boton) return;
  const notas = document.getElementById('notas').value;
  return pedir('/api/ficha/' + encodeURIComponent(boton.dataset.cuij), {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({datos: {notas: notas}})
  });
}
"""


def _html_login(error=""):
    aviso = f'<p class="error">{_e(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Portal del Estudio</title><style>{_CSS}</style></head>
<body><main class="tarjeta">
<h1>Portal del Estudio</h1>
<p class="aviso">Entrá con tu usuario o mail y tu contraseña.</p>
{aviso}
<form method="post" action="/login">
<label for="identificador">Usuario o mail</label>
<input id="identificador" name="identificador" autocomplete="username" required autofocus>
<label for="password">Contraseña</label>
<input id="password" name="password" type="password" autocomplete="current-password" required>
<p><button type="submit">Entrar</button></p>
</form>
</main></body></html>"""


def _html_panel(persona, cuij=None):
    datos = db.leer_estado()
    cedulas = datos.get("cedulas", [])
    pendientes = datos.get("pendientes", [])
    entradas = db.leer_log(limite=20)

    filas = []
    for cedula in cedulas:
        id_cedula = str(cedula.get("id") or "")
        estado = str(cedula.get("estado") or "generada")
        identidad = str(cedula.get("identidad_cadena") or "sin fijar")
        enlace_ficha = ""
        if cedula.get("cuij"):
            enlace_ficha = (
                f'<br><a href="/panel?cuij={quote(str(cedula["cuij"]), safe="")}">ver ficha</a>'
            )
        filas.append(
            "<tr>"
            f"<td>{_e(id_cedula)}</td>"
            f"<td>{_e(cedula.get('caratula'))}{enlace_ficha}</td>"
            f"<td>{_e(cedula.get('cuij'))}</td>"
            f"<td>{_e(estado)}</td>"
            f"<td>{_e(identidad)}</td>"
            "</tr>"
        )
    if not filas:
        filas.append('<tr><td colspan="5" class="aviso">Todavía no hay cédulas.</td></tr>')

    log_filas = []
    for entrada in entradas:
        log_filas.append(
            "<tr>"
            f"<td>{_e(entrada.get('fecha_hora'))}</td>"
            f"<td>{_e(entrada.get('accion'))}</td>"
            f"<td>{_e(entrada.get('operador'))}</td>"
            f"<td>{_e(entrada.get('identidad'))}</td>"
            f"<td>{_e(entrada.get('id_cedula') or entrada.get('cuij'))}</td>"
            f"<td>{_e(entrada.get('detalle'))}</td>"
            "</tr>"
        )
    if not log_filas:
        log_filas.append('<tr><td colspan="6" class="aviso">Sin movimientos.</td></tr>')

    ficha_html = ""
    if cuij:
        ficha = db.leer_ficha(cuij)
        documentos = db.listar_documentos(cuij=cuij)
        if ficha is None:
            ficha_html = f'<p class="aviso">No hay ficha para {_e(cuij)}.</p>'
        else:
            import json

            documentos_html = "".join(
                f'<li><a href="/api/documentos/{quote(str(d.get("id") or ""), safe="")}">'
                f'{_e(d.get("nombre"))}</a> '
                f'<span class="aviso">({_e(d.get("tamano"))} bytes)</span></li>'
                for d in documentos
            ) or '<li class="aviso">Sin documentos.</li>'
            notas = ficha.get("notas", "")
            ficha_html = (
                f"<h2>Ficha {_e(cuij)}</h2>"
                f"<pre>{_e(json.dumps(ficha, ensure_ascii=False, indent=2))}</pre>"
                f'<label for="notas">Notas</label>'
                f'<textarea id="notas">{_e(notas)}</textarea>'
                f'<p><button id="guardar-notas" data-cuij="{_e(cuij)}" '
                f'onclick="guardarNotas()">Guardar notas</button></p>'
                f"<h2>Documentos</h2><ul>{documentos_html}</ul>"
            )
        ficha_html += (
            '<h2>Subir un PDF</h2>'
            '<form onsubmit="subir(event)">'
            f'<input type="hidden" name="cuij" value="{_e(cuij or "")}">'
            '<input type="file" name="archivo" accept="application/pdf" required> '
            '<button type="submit">Subir</button>'
            "</form>"
        )

    nombre = _e(persona.get("nombre") or persona.get("persona_id"))
    persona_id = _e(persona.get("persona_id"))
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Portal del Estudio</title><style>{_CSS}</style></head>
<body>
<header>
  <h1>Portal del Estudio</h1>
  <div class="quien">Trabajando: <strong>{nombre}</strong> ({persona_id})</div>
  <form method="post" action="/logout"><button type="submit">Salir</button></form>
</header>
<main>
  <div class="resumen">
    <div><strong>{len(cedulas)}</strong>cédulas</div>
    <div><strong>{len(pendientes)}</strong>pendientes</div>
  </div>

  <section>
    <h2>Cédulas</h2>
    <table>
      <thead><tr><th>Id</th><th>Carátula</th><th>CUIJ</th><th>Estado</th><th>Identidad</th></tr></thead>
      <tbody>{''.join(filas)}</tbody>
    </table>
  </section>

  <section>
    <h2>Buscar ficha</h2>
    <form method="get" action="/panel">
      <label for="cuij">CUIJ</label>
      <input id="cuij" name="cuij" value="{_e(cuij or '')}" placeholder="21-00000001-0">
      <p><button type="submit">Buscar</button></p>
    </form>
    {ficha_html}
  </section>

  <section>
    <h2>Últimos movimientos</h2>
    <table>
      <thead><tr><th>Fecha</th><th>Acción</th><th>Operador</th><th>Identidad</th><th>Cédula/CUIJ</th><th>Detalle</th></tr></thead>
      <tbody>{''.join(log_filas)}</tbody>
    </table>
  </section>
</main>
<script>{_JS}</script>
</body></html>"""


if __name__ == "__main__":
    import uvicorn

    db.inicializar()
    if not db.listar_personas():
        print("No hay personas en la base. Corré: python portal_admin.py init")

    host = str(db.config_portal("PORTAL_HOST", "127.0.0.1")).strip()
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"PORTAL_HOST={host!r} no es loopback: se usa 127.0.0.1.")
        print("Para entrar desde otra máquina, poné Tailscale Serve delante.")
        host = "127.0.0.1"
    puerto = int(db.config_portal("PORTAL_PUERTO", 8100))

    print("=" * 52)
    print("  Portal del Estudio - Segovia")
    print(f"  http://127.0.0.1:{puerto}")
    print("  (podés minimizar esta ventana)")
    print("=" * 52)
    uvicorn.run(app, host=host, port=puerto, log_level="warning")
