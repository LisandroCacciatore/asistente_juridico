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

# Consola Windows a prueba de Unicode (ver nota en _navegador.py).
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from firma import firmar, firmar_lote
from meta_juridico import subir, ExpedienteNoEncontrado
import estado
import generar_cedula

app = FastAPI(title="Asistente Jurídico — Estudio Segovia")
BASE = os.path.dirname(os.path.abspath(__file__))

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

class DatosSubida(BaseModel):
    id_cedula: str
    ruta_pdf: str
    cuij: str
    caratula: str | None = None

class ItemLote(BaseModel):
    id_cedula: str
    ruta_pdf: str

class DatosFirmaLote(BaseModel):
    items: list[ItemLote]

class DatosGenerarDesdePendiente(BaseModel):
    id_pendiente: str
    tipo: str


# --- Dashboard ---------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open(os.path.join(BASE, "asistente_juridico.html"), encoding="utf-8") as f:
        return f.read()


# --- Lista de cédulas (lee estado.json) --------------------------
@app.get("/api/cedulas")
def api_cedulas():
    return estado.cargar()


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
        ruta_firmada = firmar(d.ruta_pdf, pausar=pausar)
        if ruta_firmada:
            estado.marcar_firmada(d.id_cedula, ruta_firmada)
        return {"ruta_firmada": ruta_firmada}
    job_id = _lanzar("firma", d.id_cedula, trabajo)
    return {"job_id": job_id}


# --- Firmar en lote (varias cédulas, una sola ventana) ------------
@app.post("/api/firmar_lote")
def api_firmar_lote(d: DatosFirmaLote):
    items = [{"id_cedula": it.id_cedula, "ruta_pdf": it.ruta_pdf} for it in d.items]

    def trabajo(pausar):
        def on_resultado(id_cedula, ruta_firmada):
            # se guarda en estado.json apenas termina CADA documento,
            # no al final del lote (si se corta a mitad de camino, no
            # se pierde lo ya firmado).
            if ruta_firmada:
                estado.marcar_firmada(id_cedula, ruta_firmada)
        resultados = firmar_lote(items, pausar=pausar, on_resultado=on_resultado)
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


if __name__ == "__main__":
    print("=" * 52)
    print("  Asistente Jurídico — Estudio Segovia")
    print("  Abrí http://localhost:8000 en el navegador")
    print("  (podés minimizar esta ventana)")
    print("=" * 52)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
