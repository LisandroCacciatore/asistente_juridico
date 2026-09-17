# -*- coding: utf-8 -*-
# ============================================================
#  SERVIDOR.PY — Agente local (FastAPI). Puente entre el
#                dashboard (HTML) y los scripts de Playwright.
# ------------------------------------------------------------
#  La pausa humana se resuelve por HTTP: el trabajo de Playwright
#  corre en segundo plano; cuando llega a la firma o al 2FA, el
#  dashboard muestra un botón "Ya está → continuar" que la destraba.
#
#  ARRANCAR:
#     python servidor.py
#  Luego abrir http://localhost:8000
# ============================================================

import os
import sys
import uuid
import threading
import traceback
from urllib.parse import urlsplit

# Consola Windows a prueba de Unicode (ver nota en _navegador.py).
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from firma import firmar, firmar_lote
from meta_juridico import subir, ExpedienteNoEncontrado
import estado
import sesion
import generar_cedula
import acciones
import mail_gmail

app = FastAPI(title="Asistente Jurídico — Estudio Segovia")
BASE = os.path.dirname(os.path.abspath(__file__))

# CORS abierto SIN credentials: permite que el dashboard funcione también
# embebido (webview/preview). El middleware anti-CSRF de abajo sigue
# protegiendo las mutaciones: exige Origin == Host, y deja pasar los
# requests sin Origin (scripts locales) y Origin "null" (webviews locales
# de confianza). Un sitio externo que intente POSTear queda bloqueado.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _proteger_csrf(request: Request, call_next):
    """Anti-CSRF mínimo (Fase 0).

    El dashboard corre en localhost y dispara acciones que tocan portales
    (firmar, subir, continuar). Un sitio web malicioso abierto en el mismo
    navegador podría mandar un <form> cross-site a http://localhost:8000
    sin que CORS lo frene (los forms simples no hacen preflight).

    Defensa: en requests con mutación (POST/PUT/PATCH/DELETE), si el
    navegador manda el header Origin, su host debe coincidir con el Host
    del request. Los requests sin Origin (curl, scripts locales, el propio
    fetch same-origin cuando el servidor corre en otra IP) no se tocan:
    el navegador SIEMPRE manda Origin en un POST cross-site.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin:
            host = request.headers.get("host", "")
            try:
                origen_host = urlsplit(origin).netloc
            except ValueError:
                origen_host = ""
            if origen_host and origen_host != host:
                return JSONResponse(
                    {"ok": False, "error": "Origen no permitido"},
                    status_code=403,
                )
    return await call_next(request)

# --- Registro de trabajos en curso -------------------------------
# job_id -> {status, message, event, result, error, tipo, id_cedula}
JOBS = {}


def _pausar_factory(job_id):
    """Devuelve una función de pausa que, en vez de esperar ENTER en
    consola, marca el trabajo como 'esperando' y bloquea hasta que el
    dashboard llame a /api/continuar/{job_id}. Se puede llamar varias
    veces dentro de un mismo trabajo (ej: login + PIN por documento
    en el modo lote)."""
    def pausar(mensaje):
        job = JOBS[job_id]
        job["message"] = mensaje
        job["status"] = "esperando"
        job["event"].clear()
        job["event"].wait()          # se destraba desde el dashboard
        job["status"] = "corriendo"
        job["message"] = ""
    return pausar


def _lanzar(tipo, id_cedula, trabajo):
    """Crea un job y corre `trabajo(pausar)` en un hilo aparte."""
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {
        "status": "corriendo", "message": "", "event": threading.Event(),
        "result": None, "error": None, "tipo": tipo, "id_cedula": id_cedula,
    }

    def correr():
        job = JOBS[job_id]
        try:
            job["result"] = trabajo(_pausar_factory(job_id))
            job["status"] = "listo"
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
            traceback.print_exc()

    threading.Thread(target=correr, daemon=True).start()
    return job_id


# --- Modelos de entrada ------------------------------------------
class DatosFirma(BaseModel):
    id_cedula: str
    ruta_pdf: str
    identidad: str | None = None

class DatosSubida(BaseModel):
    id_cedula: str
    ruta_pdf: str
    cuij: str
    caratula: str | None = None

class ItemLote(BaseModel):
    id_cedula: str
    ruta_pdf: str
    identidad: str | None = None

class DatosFirmaLote(BaseModel):
    items: list[ItemLote]

class DatosGenerarDesdePendiente(BaseModel):
    id_pendiente: str
    tipo: str

class DatosAccion(BaseModel):
    datos: dict = {}

class DatosDestinatarios(BaseModel):
    texto: str = ""
    domicilio: str | None = None


class DatosSesion(BaseModel):
    operador: str
    identidad: str | None = None


# --- Dashboard ---------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open(os.path.join(BASE, "asistente_juridico.html"), encoding="utf-8") as f:
        return f.read()


# --- Lista de cédulas (lee estado.json) --------------------------
@app.get("/api/cedulas")
def api_cedulas():
    return estado.cargar()


# --- Quién está trabajando (SPEC D18 y D19) -----------------------
# El panel lo consulta al abrir y en cada refresco (que además marca
# actividad: si nadie mira el panel por 12 horas, la jornada vence y
# vuelve a preguntar).
#
# OJO: mientras el asistente corra local, esto es una DECLARACIÓN, no un
# login (SPEC D23). El login de verdad llega cuando el panel se sirva
# desde el hub, y recién ahí el log deja de ser "lo que alguien dijo ser".
@app.get("/api/sesion")
def api_sesion():
    return sesion.estado_para_el_panel(tocar=True)


@app.post("/api/sesion")
def api_declarar_sesion(d: DatosSesion):
    try:
        sesion.declarar(d.operador, d.identidad)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    # Queda asentado quién entró, con qué identidad y desde qué máquina.
    estado.registrar_log("sesion_iniciada", "", detalle=f"operador {d.operador}")
    return {"ok": True, **sesion.estado_para_el_panel()}


@app.delete("/api/sesion")
def api_cerrar_sesion():
    sesion.cerrar()
    return {"ok": True, **sesion.estado_para_el_panel()}


# --- Log de acciones (para la sección "Actividad") ----------------
@app.get("/api/log")
def api_log(limite: int = 30):
    return estado.leer_log(limite=limite)


# --- Confirmar el tipo de un pendiente y generar la cédula --------
@app.post("/api/generar_desde_pendiente")
def api_generar_desde_pendiente(d: DatosGenerarDesdePendiente):
    pendiente = estado.obtener_pendiente(d.id_pendiente)
    if not pendiente:
        return {"ok": False, "error": "Ese pendiente ya no está (¿generado o eliminado?)"}

    entrada = dict(pendiente)
    entrada["tipo"] = d.tipo
    entrada.pop("tipo_sugerido", None)

    try:
        regs = generar_cedula.generar(entrada)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    estado.eliminar_pendiente(d.id_pendiente)
    return {"ok": True, "generadas": [r["id"] for r in regs]}


# --- Firmar (una cédula) ------------------------------------------
@app.post("/api/firmar")
def api_firmar(d: DatosFirma):
    def trabajo(pausar):
        # Con qué identidad y con qué perfil: cada uno firma con su Firma
        # Digital y su sesión (SPEC D18 y D24). Antes de abrir el portal se
        # confirma en pantalla con qué identidad se va a actuar (D19).
        # La regla de la cadena (D25): si la cédula ya es de alguien, se firma
        # con esa identidad o no se firma.
        identidad = acciones.verificar_cadena(
            d.id_cedula, sesion.identidad_para_el_acto(d.identidad))
        ruta_firmada = firmar(
            d.ruta_pdf,
            pausar=sesion.pausar_con_identidad(pausar, identidad),
            perfil=sesion.perfil_de(identidad),
        )
        if ruta_firmada:
            # La cédula queda de esta identidad (D25): la notificación va a
            # tener que ser con la misma.
            estado.fijar_cadena(d.id_cedula, identidad)
            estado.marcar_firmada(d.id_cedula, ruta_firmada, identidad=identidad)
        return {"ruta_firmada": ruta_firmada}
    job_id = _lanzar("firma", d.id_cedula, trabajo)
    return {"job_id": job_id}


# --- Firmar en lote (varias cédulas, una sola ventana) ------------
@app.post("/api/firmar_lote")
def api_firmar_lote(d: DatosFirmaLote):
    items = [{"id_cedula": it.id_cedula, "ruta_pdf": it.ruta_pdf} for it in d.items]

    def trabajo(pausar):
        identidad = sesion.identidad_para_el_acto()

        # Cada cédula del lote tiene que ser de la misma identidad (D25): se
        # firman todas en una sola sesión de FirmAr, así que no se puede
        # mezclar gente en el mismo lote. Si alguna es de otro, se frena acá.
        for it in items:
            identidad = acciones.verificar_cadena(it["id_cedula"], identidad)

        def on_resultado(id_cedula, ruta_firmada):
            # se guarda en estado.json apenas termina CADA documento,
            # no al final del lote (si se corta a mitad de camino, no
            # se pierde lo ya firmado).
            if ruta_firmada:
                estado.fijar_cadena(id_cedula, identidad)
                estado.marcar_firmada(id_cedula, ruta_firmada, identidad=identidad)
        resultados = firmar_lote(
            items,
            pausar=sesion.pausar_con_identidad(pausar, identidad),
            on_resultado=on_resultado,
            perfil=sesion.perfil_de(identidad),
        )
        return {"resultados": resultados}

    job_id = _lanzar("firma_lote", "lote", trabajo)
    return {"job_id": job_id}


# --- Subir a Meta Jurídico -----------------------------------------
@app.post("/api/subir")
def api_subir(d: DatosSubida):
    def trabajo(pausar):
        try:
            ok = subir(d.ruta_pdf, d.cuij, caratula=d.caratula, pausar=pausar)
        except ExpedienteNoEncontrado as e:
            # No es un tropiezo de automatización: el expediente no
            # existe en Meta Jurídico. No caer al modo manual — marcar
            # "Solicita Revisión" para que el abogado lo resuelva a
            # mano, sin riesgo de crear un expediente duplicado.
            estado.marcar_atencion(d.id_cedula, str(e), etiqueta="Solicita Revisión")
            return {"ok": False, "requiere_revision": True, "motivo": str(e)}
        if ok:
            estado.marcar_presentada(d.id_cedula)
        return {"ok": ok}
    job_id = _lanzar("subida", d.id_cedula, trabajo)
    return {"job_id": job_id}


# --- Destinatarios de una cédula (paso previo, sin generar nada) ---
# El panel pide esto ANTES de generar: lee el decreto pegado y devuelve
# a quién habría que notificar, para que el abogado destilde lo que no
# va (D8). Es sólo parseo de texto: no hay job, no hay portal, no hay
# archivos. Si el texto no alcanza, el panel muestra el motivo.
@app.post("/api/destinatarios")
def api_destinatarios(d: DatosDestinatarios):
    try:
        return acciones.ejecutar("destinatarios", {"texto": d.texto, "domicilio": d.domicilio or ""})
    except acciones.AccionError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": "No pude leer el texto: " + str(e)[:200]}


# --- Estado de un trabajo (el dashboard lo consulta) -------------
@app.get("/api/estado/{job_id}")
def api_estado(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"status": "desconocido"}
    resp = {"status": job["status"], "message": job["message"], "tipo": job["tipo"]}
    if job["status"] == "listo":
        resp["result"] = job["result"]
    if job["status"] == "error":
        resp["error"] = job["error"]
    return resp


# --- Continuar (el botón "Ya está" del dashboard) ----------------
@app.post("/api/continuar/{job_id}")
def api_continuar(job_id: str):
    job = JOBS.get(job_id)
    if job:
        job["event"].set()
        return {"ok": True}
    return {"ok": False}


# --- Acciones del secretario (las skills del estudio) ------------
# Motor local (scripts del repo) o motor "secretario" (Hermes con la
# skill cargada). Corre en un job: el dashboard muestra el avance y
# las puertas humanas se destraban desde ahí.
@app.post("/api/skill/{accion}")
def api_skill(accion: str, d: DatosAccion):
    def trabajo(pausar):
        return acciones.ejecutar(accion, d.datos or {}, pausar=pausar)

    job_id = _lanzar("accion:" + accion, accion, trabajo)
    return {"job_id": job_id}


# --- Mail: bandeja y borradores ----------------------------------
# El dashboard NUNCA envía: muestra la bandeja y los borradores que
# preparó el secretario. El envío es un acto del abogado, en Gmail.
CONSULTA_BANDEJA = "in:inbox -category:promotions -category:social newer_than:30d"


def _error_mail(e):
    """Traduce un fallo de Gmail a algo accionable para el abogado."""
    t = str(e)
    if "No hay token" in t:
        return "Falta autorizar la casilla de Gmail en esta máquina."
    if isinstance(e, FileNotFoundError):
        return "Falta autorizar la casilla de Gmail en esta máquina."
    if "invalid_grant" in t or "RefreshError" in type(e).__name__:
        return "La sesión de Gmail venció: hay que volver a autorizar la casilla."
    return "No pude leer la casilla: " + t[:180]


@app.get("/api/mail/bandeja")
def api_mail_bandeja(max: int = 8):
    try:
        return {"cuenta": mail_gmail.cuenta(),
                "mails": mail_gmail.buscar(CONSULTA_BANDEJA, max)}
    except Exception as e:
        traceback.print_exc()
        return {"error": _error_mail(e)}


@app.get("/api/mail/borradores")
def api_mail_borradores(max: int = 8):
    try:
        return {"cuenta": mail_gmail.cuenta(),
                "borradores": mail_gmail.listar_borradores(max)}
    except Exception as e:
        traceback.print_exc()
        return {"error": _error_mail(e)}


if __name__ == "__main__":
    print("=" * 52)
    print("  Asistente Jurídico — Estudio Segovia")
    print("  Abrí http://localhost:8000 en el navegador")
    print("  (podés minimizar esta ventana)")
    print("=" * 52)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
