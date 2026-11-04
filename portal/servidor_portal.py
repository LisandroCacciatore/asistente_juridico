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

import datetime
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

import estado

from . import auth, csrf, db, hub, permisos

MIN_LARGO_PASSWORD = 8

# --- Bloqueo de login (commit 6) -----------------------------------
#: Ventana en la que se cuentan los fallos y duración del bloqueo.
VENTANA_BLOQUEO_MIN = 15
BLOQUEO_MIN = 15

#: Fallos por identificador (exista o no) y por IP (umbral más alto: una
#: oficina entera puede compartir salida).
FALLOS_POR_IDENTIFICADOR = 5
FALLOS_POR_IP = 20

MENSAJE_LOGIN = "Usuario o contraseña incorrectos."

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
        # Token CSRF para la API: HMAC de PORTAL_SECRETO sobre la sesión. Sin
        # sesión no se exige (la dependencia ya responde 401).
        if request.url.path.startswith("/api/"):
            cookie = request.cookies.get(auth.NOMBRE_COOKIE)
            if cookie and not csrf.valido(cookie, request.headers.get("X-CSRF-Token")):
                return JSONResponse(
                    {"ok": False, "error": "Token CSRF inválido"}, status_code=403
                )
    return await call_next(request)


@app.middleware("http")
async def _cabeceras_seguridad(request: Request, call_next):
    """Cabeceras que el navegador no puede dejar de recibir.

    `nosniff` evita que el navegador adivine el tipo de archivo y ejecute
    como HTML algo que se sirvió como PDF. `DENY` impide embeber el portal
    en un iframe ajeno (clickjacking). `no-store` va en todo porque son
    datos de clientes. El CSP solo se arma para HTML (con un nonce por
    pedido para el script en línea) y para PDF. Se agregan al final, así
    también cubren las respuestas de error.
    """
    nonce = secrets.token_urlsafe(16)
    request.state.nonce = nonce
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
    respuesta.headers.setdefault("Cache-Control", "no-store")
    tipo = respuesta.headers.get("content-type", "")
    if "text/html" in tipo:
        respuesta.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'",
        )
    elif "application/pdf" in tipo:
        respuesta.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
    return respuesta


# --- Errores ------------------------------------------------------
@app.exception_handler(permisos.ErrorPermiso)
async def _error_permiso(request: Request, exc: permisos.ErrorPermiso):
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
    if persona.get("debe_cambiar"):
        # Mientras deba cambiar la clave, la API no responde nada más.
        raise HTTPException(
            status_code=403,
            detail="Hay que cambiar la contraseña antes de seguir (/cambiar-password).",
        )
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


def _cabecera(request, nombre):
    """Valor de una cabecera, tolerante a `dict` planos (tests)."""
    cabeceras = getattr(request, "headers", None)
    if cabeceras is None:
        return ""
    try:
        valor = cabeceras.get(nombre)
        if valor:
            return str(valor)
    except Exception:
        pass
    try:
        for clave, valor in cabeceras.items():
            if str(clave).lower() == nombre:
                return str(valor or "")
    except Exception:
        pass
    return ""


def _ip_cliente(request):
    """IP del cliente para la auditoría ('' si no se puede saber).

    Detrás de Tailscale Serve el peer es siempre 127.0.0.1, así que la IP real
    viene en X-Forwarded-For. Ese header se cree SOLO cuando la conexión directa
    es del proxy local: si el peer es otra máquina, el header lo escribió el
    cliente y se ignora. Se toma la ÚLTIMA entrada, que la agrega el proxy de
    confianza; las anteriores las puede inventar quien llama.
    """
    cliente = getattr(request, "client", None)
    peer = str(getattr(cliente, "host", "") or "")
    if peer == "127.0.0.1":
        reenviado = _cabecera(request, "x-forwarded-for")
        partes = [p.strip() for p in reenviado.split(",") if p.strip()]
        if partes:
            peer = partes[-1]
    return peer[:45]


def _registrar_log(persona, request, accion, id_cedula="", caratula="",
                   cuij="", detalle=""):
    """Deja en `log_acciones.jsonl` un acto sobre una CÉDULA.

    Escribe en el log real (`estado.registrar_log`), que es la única fuente de
    verdad. Solo para cédulas: login, logout y rechazos van a `auditoria`.
    Recibe la persona ya resuelta.
    """
    # `identidad_cadena` guarda el NOMBRE (ej. "Santiago"), no el persona_id.
    return estado.registrar_log(
        accion,
        id_cedula,
        caratula=caratula,
        cuij=cuij,
        detalle=detalle,
        identidad=permisos.identidad_de(persona),
        operador=persona.get("nombre", ""),
        usuario="portal",
        maquina=_ip_cliente(request),
    )


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
    persona = _persona_opcional(request)
    if persona:
        destino = "/cambiar-password" if persona.get("debe_cambiar") else "/panel"
        return RedirectResponse(destino, status_code=303)
    # Cookie anónima: de ahí sale el token del formulario de login.
    anon = request.cookies.get(csrf.NOMBRE_COOKIE_ANON) or secrets.token_urlsafe(24)
    respuesta = HTMLResponse(_html_login(csrf_token=csrf.token(anon)))
    respuesta.set_cookie(
        csrf.NOMBRE_COOKIE_ANON,
        anon,
        httponly=True,
        samesite="lax",
        secure=auth.cookie_segura(),
        path="/",
    )
    return respuesta


def _clave_intentos(identificador):
    """Clave de conteo por identificador (normalizado, exista o no)."""
    limpio = permisos.normalizar(identificador)[:80]
    return f"id:{limpio}" if limpio else ""


def _clave_ip_intentos(request):
    ip = _ip_cliente(request)
    return f"ip:{ip}" if ip else ""


def _desde_la_ventana():
    """Inicio de la ventana de conteo, en UTC como `db._ahora()`.

    Si acá se usara la hora local, la comparación de strings ISO quedaría
    corrida respecto de las fechas guardadas y el conteo daría 0.
    """
    ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        minutes=VENTANA_BLOQUEO_MIN
    )
    return ahora.isoformat(timespec="seconds")


def _clave_bloqueada(claves):
    """La clave que superó su umbral de fallos en la ventana, o None."""
    desde = _desde_la_ventana()
    db.podar_intentos(desde)
    for clave, tope in claves:
        if clave and db.contar_intentos(clave, desde) >= tope:
            return clave
    return None


@app.post("/login")
def login(
    request: Request,
    identificador: str = Form(...),
    password: str = Form(...),
    csrf_form: str = Form("", alias="csrf"),
):
    # Token del formulario: se deriva de la cookie anónima. Sin esa cookie
    # (cliente de API que no hizo GET /) no hay nada que validar.
    anon = request.cookies.get(csrf.NOMBRE_COOKIE_ANON)
    if anon and not csrf.valido(anon, csrf_form):
        return HTMLResponse(
            _html_login("El formulario venció. Volvé a intentar.", csrf.token(anon)),
            status_code=403,
        )

    claves = [
        (_clave_intentos(identificador), FALLOS_POR_IDENTIFICADOR),
        (_clave_ip_intentos(request), FALLOS_POR_IP),
    ]
    bloqueada = _clave_bloqueada(claves)
    if bloqueada:
        # Mismo trabajo que un fallo normal: si no, el tiempo delata el bloqueo.
        auth.quemar_tiempo(password)
        # Se audita una sola vez por clave y ventana: si no, cada intento
        # bloqueado suma una fila y cualquiera puede inflar la tabla.
        if not db.hay_auditoria(
            "login_bloqueado", _desde_la_ventana(), detalle=bloqueada[:80]
        ):
            db.registrar_auditoria(
                persona_id=str(identificador or "")[:80],
                accion="login_bloqueado",
                ip=_ip_cliente(request),
                detalle=bloqueada[:80],
            )
        return HTMLResponse(_html_login(MENSAJE_LOGIN), status_code=401)

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
        for clave, _tope in claves:
            if clave:
                db.registrar_intento(clave)
        db.registrar_auditoria(
            persona_id=identificador or "",
            accion="login_fallido",
            ip=_ip_cliente(request),
            detalle=str(identificador or ""),
        )
        return HTMLResponse(_html_login(MENSAJE_LOGIN), status_code=401)

    # Login correcto: se reinicia el contador del identificador.
    clave_identificador = _clave_intentos(identificador)
    if clave_identificador:
        db.limpiar_intentos(clave_identificador)
    db.registrar_auditoria(
        persona_id=persona["persona_id"],
        accion="login",
        ip=_ip_cliente(request),
        detalle="",
    )
    destino = "/cambiar-password" if persona.get("debe_cambiar") else "/panel"
    respuesta = RedirectResponse(destino, status_code=303)
    respuesta.set_cookie(auth.NOMBRE_COOKIE, cookie, **auth.opciones_cookie())
    return respuesta


@app.post("/logout")
def logout(request: Request):
    token = auth.verificar_cookie(request.cookies.get(auth.NOMBRE_COOKIE))
    # La persona se lee ANTES de cerrar la sesión: después ya no existe.
    persona = auth.persona_actual(request.cookies.get(auth.NOMBRE_COOKIE))
    if token:
        auth.cerrar_sesion(token)
        # Solo se audita un logout real: sin sesión no hay nada que cerrar y
        # un POST anónimo no puede llenar la tabla de auditoría.
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
def api_sesion(request: Request, persona=Depends(_persona)):
    cookie = request.cookies.get(auth.NOMBRE_COOKIE)
    return {
        "ok": True,
        "persona": _publica(persona),
        "csrf": csrf.token(cookie),
    }


@app.get("/api/salud")
def api_salud():
    try:
        db.contar_sesiones()
    except Exception:
        return JSONResponse({"ok": False, "error": "La base no responde."}, status_code=503)
    return {"ok": True, "portal": "estudio"}


# --- Lectura del estado real (solo lectura) ------------------------
def _limite(valor, tope=hub.LIMITE_MAXIMO):
    """`?limite=` acotado a 1..200 (0 o negativo no tiene sentido)."""
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return hub.LIMITE_POR_DEFECTO
    return max(1, min(numero, tope))


def _log_visible(persona, limite):
    """Actividad visible: filtro por identidad en Python y límite DESPUÉS.

    El filtro va en Python con `permisos.normalizar` (no en SQL): `lower()` de
    SQLite solo baja ASCII, así que "José" o "Peña" no coincidirían.
    """
    admin = permisos.es_administrador(persona)
    # `usuario` y `maquina` son el usuario de Windows y el nombre de la PC:
    # solo salen para un administrador.
    entradas = hub.actividad(incluir_origen=admin)
    if not admin:
        visibles = {permisos.normalizar(i) for i in permisos.identidades_de(persona)}
        entradas = [
            e for e in entradas if permisos.normalizar(e.get("identidad")) in visibles
        ]
    return entradas[: _limite(limite)]


@app.get("/api/portal/novedades")
def api_portal_novedades(limite: int = 50, persona=Depends(_persona)):
    """Cédulas recientes y —solo para un administrador— pendientes."""
    permisos.exigir(persona, permisos.LEER_ESTADO)
    datos = hub.estado()
    cedulas = permisos.filtrar_cedulas(datos["cedulas"], persona)
    cedulas = hub.ordenar_por_fecha(cedulas)[: _limite(limite)]
    # Los pendientes todavía no tienen identidad: los ve solo un admin.
    pendientes = (
        datos["pendientes"][: _limite(limite)]
        if permisos.es_administrador(persona)
        else []
    )
    return {"ok": True, "cedulas": cedulas, "pendientes": pendientes}


@app.get("/api/portal/actividad")
def api_portal_actividad(limite: int = 50, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_LOG)
    return {"ok": True, "entradas": _log_visible(persona, limite)}


# --- Cédulas ------------------------------------------------------
@app.get("/api/cedulas")
def api_cedulas(estado: str | None = None, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_ESTADO)
    cedulas = permisos.filtrar_cedulas(hub.cedulas(), persona)
    if estado:
        cedulas = [c for c in cedulas if c.get("estado") == estado]
    return {"ok": True, "cedulas": cedulas}


@app.get("/api/cedulas/{id_cedula}")
def api_cedula(id_cedula: str, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_ESTADO)
    cedula = hub.buscar_cedula(id_cedula)
    # 404 también cuando existe pero no es visible: un 403 confirmaría que la
    # cédula está ahí y de quién es.
    if cedula is None or not permisos.puede_ver_cedula(cedula, persona):
        raise HTTPException(
            status_code=404,
            detail=f"No existe la cédula {id_cedula!r} en el estado central.",
        )
    return {"ok": True, "cedula": cedula}


# --- Log ----------------------------------------------------------
@app.get("/api/log")
def api_log(limite: int = 50, persona=Depends(_persona)):
    permisos.exigir(persona, permisos.LEER_LOG)
    return {"ok": True, "entradas": _log_visible(persona, limite)}


# --- PDF firmado de una cédula (commit 5) --------------------------
def _normalizar(texto):
    """Comparación de CUIJ/carátula: sin espacios de más ni mayúsculas."""
    return " ".join(str(texto or "").split()).casefold()


def _id_seguro(id_cedula):
    """Id de cédula apto para nombrar una carpeta: letras, números y guiones."""
    limpio = re.sub(r"[^0-9A-Za-z-]+", "", str(id_cedula or ""))
    return limpio[:80]


def _tope_subida():
    """Tope de subida en bytes (PORTAL_MAX_SUBIDA_MB, mínimo 1 MB)."""
    try:
        max_mb = int(db.config_portal("PORTAL_MAX_SUBIDA_MB", 25))
    except (TypeError, ValueError):
        max_mb = 25
    return max(1, max_mb) * 1024 * 1024


def _solo_alfanumerico(texto):
    """Texto comparable: solo letras y dígitos, sin guiones ni espacios."""
    return re.sub(r"[^0-9A-Za-z]+", "", str(texto or "")).casefold()


def _cuij_en_el_pdf(pdf, cuij):
    """True si el CUIJ de la cédula aparece en el texto del PDF.

    None si no se pudo extraer texto (PDF escaneado o sin capa de texto): el
    endpoint lo convierte en un 400 con mensaje claro. Compara solo letras y
    dígitos, así "21-00000001-0" y "2100000001 0" cuentan igual.
    """
    esperado = _solo_alfanumerico(cuij)
    if not esperado:
        return None
    try:
        texto = "".join(pagina.extract_text() or "" for pagina in pdf.pages)
    except Exception:
        return None
    if not texto.strip():
        return None
    return esperado in _solo_alfanumerico(texto)


def _firmas_del_pdf(pdf):
    """Diccionarios de firma válidos del PDF (campo `/FT /Sig` → `/V`).

    En un PDF firmado de verdad, `/ByteRange` y `/Contents` NO están en el
    campo de firma: están en el diccionario al que apunta `/V`. Un campo sin
    `/V`, con `/ByteRange` que no son 4 enteros, o con `/Contents` vacío o
    todo en ceros (marcador sin firmar), no cuenta.

    OJO: esto es un control contra errores humanos, NO una validación
    criptográfica: no verifica el certificado ni la integridad del documento.
    """
    campos = []

    def visitar(objeto, profundidad=0):
        if profundidad > 8:
            return
        try:
            objeto = objeto.get_object()
        except Exception:
            return
        if not isinstance(objeto, dict):
            return
        if objeto.get("/FT") == "/Sig":
            campos.append(objeto)
        for clave in ("/AcroForm", "/Fields", "/Kids", "/Annots"):
            hijos = objeto.get(clave)
            if hijos is None:
                continue
            try:
                hijos = hijos.get_object()
            except Exception:
                pass
            if isinstance(hijos, list):
                for hijo in hijos:
                    visitar(hijo, profundidad + 1)
            else:
                visitar(hijos, profundidad + 1)

    visitar(pdf.trailer.get("/Root", {}))

    validas = []
    for campo in campos:
        firma = campo.get("/V")
        if firma is None:
            continue
        try:
            firma = firma.get_object()
        except Exception:
            continue
        if not isinstance(firma, dict):
            continue

        byte_range = firma.get("/ByteRange")
        try:
            byte_range = byte_range.get_object()
        except Exception:
            pass
        if not isinstance(byte_range, list) or len(byte_range) != 4:
            continue
        if not all(isinstance(valor, int) for valor in byte_range):
            continue

        contenido = firma.get("/Contents")
        try:
            contenido = contenido.get_object()
        except Exception:
            pass
        # pypdf puede devolver los bytes como ByteStringObject (PDF real) o
        # como TextStringObject (PDF reescrito por pypdf): se aceptan los dos.
        if isinstance(contenido, str):
            contenido = contenido.encode("latin-1", "ignore")
        if not isinstance(contenido, bytes) or not contenido:
            continue
        if not any(contenido):
            # Un marcador de firma sin firmar viene en ceros.
            continue

        validas.append(firma)
    return validas


def _sha_repetido(huella):
    """True si otra cédula ya apunta a un PDF con ese sha256."""
    objetivo = f"{huella}.pdf"
    datos = estado.cargar()
    return any(
        os.path.basename(str(c.get("ruta_firmada") or "")) == objetivo
        for c in datos.get("cedulas", [])
        if isinstance(c, dict)
    )


def _cedula_visible(id_cedula, persona):
    """La cédula en crudo, o 404 si no existe o no es visible.

    Se lee del estado real (`estado.obtener_cedula`), no del hub: el hub
    recorta campos y acá hacen falta `estado`, `ruta_firmada` y compañía.
    """
    cedula = estado.obtener_cedula(id_cedula)
    if cedula is None or not permisos.puede_ver_cedula(cedula, persona):
        raise HTTPException(
            status_code=404,
            detail=f"No existe la cédula {id_cedula!r} en el estado central.",
        )
    return cedula


@app.post("/api/portal/cedulas/{id_cedula}/subir")
def api_portal_subir_firmada(
    request: Request,
    id_cedula: str,
    archivo: UploadFile = File(...),
    cuij: str = Form(""),
    caratula: str = Form(""),
    persona=Depends(_persona),
):
    """Sube el PDF firmado de una cédula y la marca firmada.

    Orden: permisos → D25 → estado de la cédula → tamaño → cabecera → pypdf →
    CUIJ/carátula → firma → sha repetido. El archivo se deja en un temporal
    dentro de uploads y recién al final se mueve a su lugar definitivo.
    """
    permisos.exigir(persona, permisos.SUBIR_DOCUMENTO)
    cedula = _cedula_visible(id_cedula, persona)
    # D25: hay que poder actuar como la identidad de la cédula. El admin NO es
    # excepción: sin delegación explícita, 403.
    permisos.verificar_cadena(cedula, persona)

    if not str(cedula.get("identidad_cadena") or "").strip():
        raise HTTPException(400, "La cédula no tiene identidad fijada (D25).")
    if str(cedula.get("estado") or "") != "generada":
        raise HTTPException(
            status_code=409,
            detail=f"La cédula no está en estado 'generada' (está {cedula.get('estado')!r}).",
        )

    tope = _tope_subida()
    carpeta = os.path.join(db.ruta_uploads(), _id_seguro(id_cedula))
    temporal = os.path.join(
        db.ruta_uploads(), f".subiendo-{secrets.token_hex(8)}.pdf"
    )
    if not _dentro_de_uploads(carpeta) or not _dentro_de_uploads(temporal):
        raise HTTPException(
            status_code=400,
            detail="El id de la cédula no sirve para armar la carpeta de subida.",
        )
    os.makedirs(carpeta, exist_ok=True)

    sha = hashlib.sha256()
    total = 0
    try:
        with open(temporal, "wb") as salida:
            while True:
                bloque = archivo.file.read(1024 * 1024)
                if not bloque:
                    break
                total += len(bloque)
                if total > tope:
                    raise HTTPException(
                        status_code=413,
                        detail=f"El PDF supera el tope de {tope // (1024 * 1024)} MB.",
                    )
                sha.update(bloque)
                salida.write(bloque)

        with open(temporal, "rb") as control:
            if control.read(5) != b"%PDF-":
                raise HTTPException(
                    status_code=400,
                    detail="El archivo no empieza con la cabecera PDF (%PDF-).",
                )

        # pypdf se importa acá: el portal arranca sin pagar el costo si no se usa.
        from pypdf import PdfReader

        try:
            pdf = PdfReader(temporal)
            if pdf.is_encrypted:
                raise HTTPException(status_code=400, detail="El PDF está cifrado.")
            len(pdf.pages)  # fuerza a recorrer el documento
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"pypdf no puede abrir el PDF: {e}"
            )

        if _normalizar(cuij) != _normalizar(cedula.get("cuij")):
            raise HTTPException(
                status_code=400, detail="El CUIJ no coincide con el de la cédula."
            )
        if _normalizar(caratula) != _normalizar(cedula.get("caratula")):
            raise HTTPException(
                status_code=400, detail="La carátula no coincide con la de la cédula."
            )
        # El formulario es una confirmación: el CUIJ tiene que estar EN el PDF.
        en_pdf = _cuij_en_el_pdf(pdf, cedula.get("cuij"))
        if en_pdf is None:
            raise HTTPException(
                status_code=400,
                detail="No se pudo extraer texto del PDF para verificar el CUIJ.",
            )
        if not en_pdf:
            raise HTTPException(
                status_code=400,
                detail="El CUIJ de la cédula no aparece en el texto del PDF.",
            )
        if not _firmas_del_pdf(pdf):
            raise HTTPException(
                status_code=400,
                detail="El PDF no tiene una firma digital válida (/Sig con /V, "
                       "/ByteRange y /Contents firmados).",
            )

        huella = sha.hexdigest()
        if _sha_repetido(huella):
            raise HTTPException(
                status_code=409, detail="Ese PDF ya está cargado en otra cédula."
            )

        destino = os.path.join(carpeta, f"{huella}.pdf")
        if not _dentro_de_uploads(destino):
            raise HTTPException(
                status_code=400, detail="El destino queda fuera de PORTAL_UPLOADS."
            )
        os.replace(temporal, destino)
    except BaseException:
        if os.path.exists(temporal):
            os.remove(temporal)
        raise

    if not estado.marcar_firmada(
        id_cedula,
        destino,
        identidad=permisos.identidad_de(persona),
        solo_si_generada=True,
    ):
        # Perdió la carrera contra otro proceso: el archivo no queda colgado.
        os.remove(destino)
        raise HTTPException(
            status_code=409, detail="Otra persona ya subió el PDF de esta cédula."
        )

    _registrar_log(
        persona, request, "pdf_subido",
        id_cedula=id_cedula,
        cuij=str(cedula.get("cuij") or ""),
        detalle=huella,
    )
    # Sin `ruta`: la ruta del servidor no sale por HTTP.
    return {"ok": True, "id": id_cedula, "sha256": huella, "estado": "firmada"}


@app.get("/api/portal/cedulas/{id_cedula}/pdf")
def api_portal_pdf(id_cedula: str, persona=Depends(_persona)):
    """Sirve el PDF firmado de la cédula (404 uniforme si no es visible)."""
    permisos.exigir(persona, permisos.DESCARGAR_DOCUMENTO)
    cedula = _cedula_visible(id_cedula, persona)
    permisos.verificar_cadena(cedula, persona)
    ruta = str(cedula.get("ruta_firmada") or "")
    if not ruta or not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail="La cédula no tiene un PDF firmado.")
    if not _dentro_de_uploads(ruta):
        raise HTTPException(
            status_code=403, detail="El PDF está fuera de la carpeta del portal."
        )
    nombre = _id_seguro(id_cedula) or "cedula"
    return FileResponse(
        ruta,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre}.pdf"'},
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
def api_admin_crear_persona(
    entrada: PersonaIn, request: Request, persona=Depends(_persona)
):
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
        # Clave provisoria: se cambia en el primer ingreso.
        db.guardar_credencial(creada["persona_id"], hash_guardado, debe_cambiar=1)
    db.registrar_auditoria(
        persona_id=persona["persona_id"],
        accion="persona_creada",
        ip=_ip_cliente(request),
        detalle=creada["persona_id"],
    )
    return {"ok": True, "persona": _publica(creada)}


@app.put("/api/admin/personas/{persona_id}")
def api_admin_actualizar_persona(
    persona_id: str, entrada: PersonaUpdate, request: Request,
    persona=Depends(_persona)
):
    _exigir_admin(persona)
    actualizada = db.actualizar_persona(
        persona_id,
        nombre=entrada.nombre,
        mail=entrada.mail,
        matricula=entrada.matricula,
        activo=entrada.activo,
    )
    db.registrar_auditoria(
        persona_id=persona["persona_id"],
        accion="persona_actualizada",
        ip=_ip_cliente(request),
        detalle=persona_id,
    )
    return {"ok": True, "persona": _publica(actualizada)}


@app.post("/api/admin/personas/{persona_id}/password")
def api_admin_password(
    persona_id: str, entrada: PasswordIn, request: Request,
    persona=Depends(_persona)
):
    _exigir_admin(persona)
    _password_valida(entrada.password)
    if not db.obtener_persona(persona_id):
        raise db.PersonaNoEncontrada(f"No existe la persona {persona_id!r}.")
    db.guardar_credencial(
        persona_id, auth.hashear(entrada.password), debe_cambiar=1
    )
    db.registrar_auditoria(
        persona_id=persona["persona_id"],
        accion="password_actualizada",
        ip=_ip_cliente(request),
        detalle=persona_id,
    )
    return {"ok": True}


@app.post("/api/admin/personas/{persona_id}/desactivar")
def api_admin_desactivar(
    persona_id: str, request: Request, persona=Depends(_persona)
):
    _exigir_admin(persona)
    desactivada = db.desactivar_persona(persona_id)
    db.registrar_auditoria(
        persona_id=persona["persona_id"],
        accion="persona_desactivada",
        ip=_ip_cliente(request),
        detalle=persona_id,
    )
    return {"ok": True, "persona": _publica(desactivada)}


@app.post("/api/admin/sesiones-borrar")
def api_admin_borrar_sesiones(request: Request, persona=Depends(_persona)):
    _exigir_admin(persona)
    borradas = db.eliminar_todas_las_sesiones()
    db.registrar_auditoria(
        persona_id=persona["persona_id"],
        accion="sesiones_borradas",
        ip=_ip_cliente(request),
        detalle=str(borradas),
    )
    return {"ok": True, "borradas": borradas}


# --- Panel --------------------------------------------------------
@app.get("/cambiar-password", response_class=HTMLResponse)
def cambiar_password_form(request: Request, error: str = ""):
    persona = _persona_opcional(request)
    if not persona:
        return RedirectResponse("/", status_code=303)
    cookie = request.cookies.get(auth.NOMBRE_COOKIE)
    return HTMLResponse(
        _html_cambiar_password(persona, csrf.token(cookie), error)
    )


@app.post("/cambiar-password")
def cambiar_password(
    request: Request,
    actual: str = Form(...),
    nueva: str = Form(...),
    repetida: str = Form(""),
    csrf_form: str = Form("", alias="csrf"),
):
    cookie = request.cookies.get(auth.NOMBRE_COOKIE)
    persona = auth.persona_actual(cookie)
    if not persona:
        return RedirectResponse("/", status_code=303)
    if not csrf.valido(cookie, csrf_form):
        return HTMLResponse(
            _html_cambiar_password(
                persona, csrf.token(cookie), "La sesión del formulario venció."
            ),
            status_code=403,
        )
    if repetida and nueva != repetida:
        return HTMLResponse(
            _html_cambiar_password(
                persona, csrf.token(cookie), "Las contraseñas nuevas no coinciden."
            ),
            status_code=400,
        )
    ok, motivo, cuenta_como_fallo = auth.cambiar_password(
        persona["persona_id"], actual, nueva
    )
    if not ok:
        if cuenta_como_fallo:
            # Probar claves desde una sesión abierta también se bloquea.
            db.registrar_intento(
                "id:" + permisos.normalizar(persona["persona_id"])[:80]
            )
        return HTMLResponse(
            _html_cambiar_password(persona, csrf.token(cookie), motivo),
            status_code=400,
        )
    # Cambiar la clave cierra las otras sesiones de esa persona.
    token = auth.verificar_cookie(cookie)
    if token:
        db.eliminar_otras_sesiones(persona["persona_id"], auth.hash_token(token))
    db.registrar_auditoria(
        persona_id=persona["persona_id"],
        accion="password_cambiada",
        ip=_ip_cliente(request),
        detalle="",
    )
    return RedirectResponse("/panel", status_code=303)


@app.get("/panel", response_class=HTMLResponse)
def panel(request: Request):
    persona = _persona_opcional(request)
    if not persona:
        return RedirectResponse("/", status_code=303)
    if persona.get("debe_cambiar"):
        return RedirectResponse("/cambiar-password", status_code=303)
    cookie = request.cookies.get(auth.NOMBRE_COOKIE)
    return HTMLResponse(
        _html_panel(persona, csrf.token(cookie), request.state.nonce)
    )


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

def _html_login(error="", csrf_token=""):
    aviso = f'<p class="error">{_e(error)}</p>' if error else ""
    oculto = f'<input type="hidden" name="csrf" value="{_e(csrf_token)}">' 
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Portal del Estudio</title><style>{_CSS}</style></head>
<body><main class="tarjeta">
<h1>Portal del Estudio</h1>
<p class="aviso">Entrá con tu usuario o mail y tu contraseña.</p>
{aviso}
<form method="post" action="/login">
{oculto}
<label for="identificador">Usuario o mail</label>
<input id="identificador" name="identificador" autocomplete="username" required autofocus>
<label for="password">Contraseña</label>
<input id="password" name="password" type="password" autocomplete="current-password" required>
<p><button type="submit">Entrar</button></p>
</form>
</main></body></html>"""


def _html_cambiar_password(persona, csrf_token="", error=""):
    aviso = f'<p class="error">{_e(error)}</p>' if error else ""
    nombre = _e(persona.get("nombre") or persona.get("persona_id"))
    obligatorio = persona.get("debe_cambiar")
    titulo = (
        "Cambiá tu contraseña para seguir"
        if obligatorio
        else "Cambiar contraseña"
    )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cambiar contraseña</title><style>{_CSS}</style></head>
<body><main class="tarjeta">
<h1>{titulo}</h1>
<p class="aviso">{nombre}: la contraseña nueva tiene que tener al menos
{auth.LARGO_MINIMO_CAMBIO} caracteres y ser distinta de la anterior.</p>
{aviso}
<form method="post" action="/cambiar-password">
<input type="hidden" name="csrf" value="{_e(csrf_token)}">
<label for="actual">Contraseña actual</label>
<input id="actual" name="actual" type="password" autocomplete="current-password" required>
<label for="nueva">Contraseña nueva</label>
<input id="nueva" name="nueva" type="password" autocomplete="new-password" required>
<label for="repetida">Repetir la nueva</label>
<input id="repetida" name="repetida" type="password" autocomplete="new-password" required>
<p><button type="submit">Guardar</button></p>
</form>
<p class="aviso"><a href="/panel">Volver al panel</a></p>
</main></body></html>"""


def _puede_operar(cedula, persona):
    """True si la persona puede actuar como la identidad de esa cédula.

    Se calcula acá y se manda un booleano al HTML: la lista de delegaciones de
    cada persona no se expone en la página.
    """
    try:
        permisos.verificar_cadena(cedula, persona)
    except permisos.ErrorPermiso:
        return False
    return True


def _accion_de_la_cedula(cedula, persona, con_pdf):
    """Botón de subida, enlace de descarga o el motivo por el que no hay nada."""
    id_cedula = str(cedula.get("id") or "")
    estado_cedula = str(cedula.get("estado") or "generada")
    identidad = str(cedula.get("identidad_cadena") or "")

    if estado_cedula == "generada":
        if not _puede_operar(cedula, persona):
            return f'<span class="aviso">Cadena de {_e(identidad or "otra identidad")}</span>'
        cuij = str(cedula.get("cuij") or "")
        caratula = str(cedula.get("caratula") or "")
        return (
            f'<form class="subir" data-id="{_e(id_cedula)}" '
            f'data-cuij="{_e(cuij)}" data-caratula="{_e(caratula)}">'
            '<input type="file" name="archivo" accept="application/pdf" required>'
            '<button type="submit">Subir firmado</button>'
            "</form>"
        )
    if estado_cedula == "firmada" and id_cedula in con_pdf:
        return (
            '<a class="descarga" '
            f'href="/api/portal/cedulas/{quote(id_cedula, safe="")}/pdf">'
            "Descargar firmado</a>"
        )
    return ""


def _html_panel(persona, csrf_token="", nonce=""):
    datos = hub.estado()
    cedulas = hub.ordenar_por_fecha(permisos.filtrar_cedulas(datos["cedulas"], persona))
    # Los pendientes todavía no tienen identidad: solo los ve un administrador.
    pendientes = datos["pendientes"] if permisos.es_administrador(persona) else []
    entradas = _log_visible(persona, 20)
    con_pdf = hub.ids_con_pdf()

    filas = []
    for cedula in cedulas:
        id_cedula = str(cedula.get("id") or "")
        estado_cedula = str(cedula.get("estado") or "generada")
        identidad = str(cedula.get("identidad_cadena") or "sin fijar")
        filas.append(
            "<tr>"
            f"<td>{_e(id_cedula)}</td>"
            f"<td>{_e(cedula.get('caratula'))}</td>"
            f"<td>{_e(cedula.get('cuij'))}</td>"
            f"<td>{_e(estado_cedula)}</td>"
            f"<td>{_e(identidad)}</td>"
            f"<td>{_accion_de_la_cedula(cedula, persona, con_pdf)}</td>"
            "</tr>"
        )
    if not filas:
        filas.append(
            '<tr><td colspan="6" class="aviso">Todavía no hay cédulas.</td></tr>'
        )

    log_filas = []
    for entrada in entradas:
        log_filas.append(
            "<tr>"
            f"<td>{_e(entrada.get('fecha_hora'))}</td>"
            f"<td>{_e(entrada.get('accion'))}</td>"
            f"<td>{_e(entrada.get('operador'))}</td>"
            f"<td>{_e(entrada.get('identidad'))}</td>"
            f"<td>{_e(entrada.get('id') or entrada.get('cuij'))}</td>"
            f"<td>{_e(entrada.get('detalle'))}</td>"
            "</tr>"
        )
    if not log_filas:
        log_filas.append('<tr><td colspan="6" class="aviso">Sin movimientos.</td></tr>')

    pendientes_html = ""
    if pendientes:
        filas_pendientes = "".join(
            "<tr>"
            f"<td>{_e(p.get('id'))}</td>"
            f"<td>{_e(p.get('caratula'))}</td>"
            f"<td>{_e(p.get('cuij'))}</td>"
            f"<td>{_e(p.get('tipo_sugerido'))}</td>"
            f"<td>{_e(p.get('fecha_decreto'))}</td>"
            "</tr>"
            for p in pendientes
        )
        pendientes_html = (
            "<h3>Pendientes de clasificar</h3>"
            "<table><thead><tr><th>Id</th><th>Carátula</th><th>CUIJ</th>"
            "<th>Tipo sugerido</th><th>Fecha del decreto</th></tr></thead>"
            f"<tbody>{filas_pendientes}</tbody></table>"
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
  <form method="post" action="/logout"><input type="hidden" name="csrf" value="{_e(csrf_token)}"><button type="submit">Salir</button></form>
</header>
<main>
  <div class="resumen">
    <div><strong>{len(cedulas)}</strong>cédulas</div>
    <div><strong>{len(pendientes)}</strong>pendientes</div>
  </div>

  <p id="aviso" class="aviso" role="status"></p>

  <section>
    <h2>Novedades</h2>
    <table>
      <thead><tr><th>Id</th><th>Carátula</th><th>CUIJ</th><th>Estado</th><th>Identidad</th><th>Acciones</th></tr></thead>
      <tbody>{''.join(filas)}</tbody>
    </table>
    {pendientes_html}
  </section>

  <section>
    <h2>Actividad</h2>
    <table>
      <thead><tr><th>Fecha</th><th>Acción</th><th>Operador</th><th>Identidad</th><th>Cédula/CUIJ</th><th>Detalle</th></tr></thead>
      <tbody>{''.join(log_filas)}</tbody>
    </table>
  </section>
</main>
<script nonce="{_e(nonce)}">
(function () {{
  var aviso = document.getElementById('aviso');

  function mostrar(texto, esError) {{
    aviso.textContent = texto;
    aviso.className = esError ? 'error' : 'aviso';
  }}

  function mensajeDe(salida) {{
    if (salida && typeof salida.detail === 'string') {{ return salida.detail; }}
    if (salida && typeof salida.error === 'string') {{ return salida.error; }}
    return 'No se pudo subir el PDF.';
  }}

  document.querySelectorAll('form.subir').forEach(function (form) {{
    form.addEventListener('submit', function (evento) {{
      evento.preventDefault();
      var archivo = form.querySelector('input[type=file]').files[0];
      if (!archivo) {{ mostrar('Elegí el PDF firmado.', true); return; }}

      fetch('/api/sesion', {{ credentials: 'same-origin' }})
        .then(function (r) {{ return r.json(); }})
        .then(function (sesion) {{
          var cuerpo = new FormData();
          cuerpo.append('archivo', archivo);
          cuerpo.append('cuij', form.dataset.cuij || '');
          cuerpo.append('caratula', form.dataset.caratula || '');
          return fetch(
            '/api/portal/cedulas/' + encodeURIComponent(form.dataset.id) + '/subir',
            {{
              method: 'POST',
              credentials: 'same-origin',
              headers: {{ 'X-CSRF-Token': sesion.csrf || '' }},
              body: cuerpo
            }}
          );
        }})
        .then(function (respuesta) {{
          return respuesta.json().catch(function () {{ return {{}}; }})
            .then(function (salida) {{ return {{ ok: respuesta.ok, salida: salida }}; }});
        }})
        .then(function (resultado) {{
          if (resultado.ok) {{
            mostrar('PDF subido: la cédula quedó firmada.', false);
            setTimeout(function () {{ window.location.reload(); }}, 800);
          }} else {{
            mostrar(mensajeDe(resultado.salida), true);
          }}
        }})
        .catch(function () {{
          mostrar('No se pudo hablar con el servidor.', true);
        }});
    }});
  }});
}})();
</script>
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
