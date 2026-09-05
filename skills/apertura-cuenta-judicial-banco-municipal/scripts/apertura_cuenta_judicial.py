# -*- coding: utf-8 -*-
# ============================================================
#  APERTURA_CUENTA_JUDICIAL.PY — SISFE vía Playwright (migrado)
# ------------------------------------------------------------
#  Reemplaza la parte de "Claude in Chrome" de la skill
#  apertura-cuenta-judicial-banco-municipal: entra al SISFE con
#  el MISMO perfil Chrome que el monitor (chrome_profile_sisfe,
#  sesión ya logueada), busca el expediente por CUIJ, toma dos
#  capturas (ficha del expediente + pantalla de cuentas del Banco
#  Municipal) y arma un PDF de 2 páginas para adjuntar al mail de
#  solicitud de apertura de cuenta judicial.
#
#  NUNCA envía nada: entrega el PDF + los datos del borrador
#  (carátula, CUIJ) para que la capa superior (el secretario /
#  google-workspace) arme el borrador en Gmail.
#
#  Uso:
#    python apertura_cuenta_judicial.py --cuij 21-04255346-5 \
#        --out "C:/ruta/salida" [--caratula "BARROZO C/ ..." ]
#
#  ⚠ Selectores de SISFE marcados ⬅ VALIDAR: verificar contra el
#    portal real en la primera corrida (misma política que el
#    monitor).
# ============================================================

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]           # raíz del repo
PERFIL_SISFE = RAIZ / "chrome_profile_sisfe"          # misma sesión que el monitor
SISFE_BUSCAR = "https://sisfe.justiciasantafe.gov.ar/buscar-expediente"
SISFE_DETALLE = "https://sisfe.justiciasantafe.gov.ar/detalle-expediente/{id}"

_PATRON_CUIJ = re.compile(r"\b21-\d{8}-\d\b")
_PATRON_ID = re.compile(r"/detalle-expediente/(\d{8,})")
_PATRON_CARATULA = re.compile(
    r"([A-ZÁÉÍÓÚÑ ,\.]+C/[A-ZÁÉÍÓÚÑ ,\.]+S/[A-ZÁÉÍÓÚÑ ]+)")

# Consola Windows a prueba de Unicode (mismo fix que _navegador.py)
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def pausa_humana(mensaje):
    """Puerta humana: SISFE puede pedir login/reCAPTCHA. Santiago está en
    la máquina (secretario local) — completa a mano y presiona ENTER."""
    print("\n  ┌───────────────────────────────────────────────────┐")
    print("  │  ACCIÓN TUYA                                       │")
    print("  └───────────────────────────────────────────────────┘")
    print(f"  {mensaje}")
    input("  >>> Cuando termines, presioná ENTER para continuar... ")
    print("")


def _abrir_sisfe():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    kwargs = dict(
        user_data_dir=str(PERFIL_SISFE), headless=False,
        accept_downloads=True, viewport={"width": 1280, "height": 900},
    )
    try:
        kwargs["channel"] = "chrome"
        ctx = p.chromium.launch_persistent_context(**kwargs)
    except Exception:
        kwargs.pop("channel", None)
        ctx = p.chromium.launch_persistent_context(**kwargs)
    pagina = ctx.pages[0] if ctx.pages else ctx.new_page()
    return p, ctx, pagina


def _esta_logueado(page):
    """True si la página de búsqueda cargó con contenido (no redirige a login)."""
    try:
        page.goto(SISFE_BUSCAR)
        page.wait_for_timeout(2500)
        if "login" in page.url:
            return False
        body = page.locator("body").inner_text(timeout=8000)
        return ("expediente" in body.lower() or "cui" in body.lower() or "tabla" in body.lower())
    except Exception:
        return False


def _buscar_fila_por_cuij(page, cuij):
    """Busca el CUIJ en la tabla de la página de búsqueda. Devuelve
    (id_sisfe, texto_fila) o (None, None)."""
    try:
        filas = page.locator("table tbody tr")
        for i in range(filas.count()):
            try:
                texto = filas.nth(i).inner_text()
            except Exception:
                continue
            if cuij in texto:
                try:
                    href = filas.nth(i).locator("a").first.get_attribute("href") or ""
                except Exception:
                    href = ""
                m = _PATRON_ID.search(href)
                return (m.group(1) if m else None), texto
    except Exception:
        pass
    return None, None


def _buscar_por_cuij(page, cuij):
    """Intento 1: CUIJ en la lista actual. Intento 2: filtros de búsqueda
    (campo CUIJ + 'Efectuar la búsqueda'). Devuelve (id, texto_fila)."""
    # --- Intento 1: la lista ya cargada ---
    id_sisfe, texto = _buscar_fila_por_cuij(page, cuij)
    if id_sisfe:
        return id_sisfe, texto

    # --- Intento 2: filtros de búsqueda ---
    print(f"  → Buscando {cuij} con el buscador...")
    try:
        # expandir el panel de filtros si está colapsado (mismo criterio que el monitor)
        campo = page.locator("#diasNovedades")
        if campo.count() == 0 or not campo.is_visible():
            try:
                page.get_by_text(re.compile("Filtros de Búsqueda", re.I)).first.click(timeout=5000)
                page.wait_for_timeout(500)
            except Exception:
                pass
        # ⬅ VALIDAR: selector del campo CUIJ en el portal real
        campo_cuij = None
        for sel in ["input[name='cuij']", "input#cuij", "input[placeholder*='CUIJ' i]"]:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                campo_cuij = loc.first
                break
        if campo_cuij is None:
            # fallback: cualquier input visible dentro del panel de filtros
            # que no sea el de días (⬅ VALIDAR contra portal real)
            try:
                inputs = page.locator("input:visible")
                for i in range(inputs.count()):
                    inp = inputs.nth(i)
                    if inp.get_attribute("id") != "diasNovedades":
                        campo_cuij = inp
                        break
            except Exception:
                campo_cuij = None
        if campo_cuij is None:
            pausa_humana("No encontré el campo CUIJ del buscador. Completalo a mano\n"
                         "  (campo CUIJ + Efectuar la búsqueda) y volvé.")
        else:
            campo_cuij.fill(cuij)
            page.wait_for_timeout(300)
        try:
            page.get_by_role("button", name=re.compile("Efectuar la búsqueda", re.I)).click(timeout=5000)
        except Exception:
            try:
                page.get_by_text(re.compile("Efectuar la búsqueda", re.I)).first.click(timeout=5000)
            except Exception:
                pausa_humana("No encontré el botón 'Efectuar la búsqueda'. Accioná la\n"
                             "  búsqueda a mano y volvé.")
        page.wait_for_timeout(3500)
    except Exception as e:
        print(f"  ⚠ Error buscando por CUIJ: {type(e).__name__}: {e}")
        return None, None

    return _buscar_fila_por_cuij(page, cuij)


def _caratula_de_body(body):
    m = _PATRON_CARATULA.search(body or "")
    return m.group(1).strip() if m else ""


def _apellido_de_caratula(caratula):
    m = re.match(r"^\s*([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", caratula or "")
    return m.group(1).upper() if m else "EXPEDIENTE"


def capturar_expediente(cuij, carpeta_salida, caratula_conocida=""):
    """Flujo principal. Devuelve dict con rutas y datos, o lanza/retorna
    error legible."""
    os.makedirs(carpeta_salida, exist_ok=True)
    os.makedirs(PERFIL_SISFE, exist_ok=True)
    p, ctx, page = _abrir_sisfe()
    try:
        if not _esta_logueado(page):
            pausa_humana("Ingresá en SISFE (matrícula, contraseña, reCAPTCHA) hasta\n"
                         "  quedar en la página de búsqueda de expedientes.")

        id_sisfe, texto_fila = _buscar_por_cuij(page, cuij)
        if not id_sisfe:
            return {"ok": False,
                    "error": f"No encontré el expediente {cuij} en SISFE (¿CUIJ correcto?)"}

        print(f"  → Abriendo detalle del expediente (id {id_sisfe})...")
        page.goto(SISFE_DETALLE.format(id=id_sisfe))
        page.wait_for_timeout(3000)
        body = page.locator("body").inner_text(timeout=10000)

        caratula = _caratula_de_body(body) or caratula_conocida
        if caratula and cuij not in body and _apellido_de_caratula(caratula).lower() not in body.lower():
            return {"ok": False,
                    "error": f"La ficha no coincide con el CUIJ {cuij} — no sigo (error grave)"}

        # --- CAPTURA #1: ficha del expediente ---
        ruta1 = os.path.join(carpeta_salida, "_captura1_ficha.png")
        page.screenshot(path=ruta1, full_page=False)
        print("  ✓ Captura 1 (ficha del expediente)")

        # --- Botón "Ver cuenta judicial en el Banco Municipal de Rosario" ---
        try:
            page.get_by_text(re.compile("Ver cuenta judicial en el Banco Municipal", re.I)).first.click(timeout=8000)
        except Exception:
            try:
                page.get_by_role("button", name=re.compile("Banco Municipal", re.I)).click(timeout=8000)
            except Exception:
                return {"ok": False,
                        "error": "No encontré el botón 'Ver cuenta judicial en el Banco Municipal' en la ficha",
                        "caratula": caratula}
        page.wait_for_timeout(3000)

        # Puede abrirse en otra pestaña (SPA): usar la última página activa
        if len(ctx.pages) > 1:
            page = ctx.pages[-1]
            page.wait_for_timeout(1500)

        ruta2 = os.path.join(carpeta_salida, "_captura2_cuenta_bm.png")
        page.screenshot(path=ruta2, full_page=False)
        print("  ✓ Captura 2 (cuentas judiciales Banco Municipal)")

        # --- Armar el PDF (una captura por página) con reportlab ---
        cuij_limpio = re.sub(r"[^0-9-]", "", cuij) or "SINCUIJ"
        apellido = _apellido_de_caratula(caratula)
        nombre_pdf = f"CAPTURAS_APERTURA_CUENTA_{apellido}_{cuij_limpio}.pdf"
        ruta_pdf = os.path.join(carpeta_salida, nombre_pdf)
        _armar_pdf([ruta1, ruta2], ruta_pdf)

        return {
            "ok": True,
            "pdf": ruta_pdf,
            "caratula": caratula,
            "cuij": cuij,
            "destinatario": "suc80jud@bmros.com.ar",
            "asunto": "SOLICITUD DE APERTURA CUENTA JUDICIAL",
        }
    finally:
        ctx.close()
        p.stop()


def _armar_pdf(imagenes, ruta_pdf):
    """Une las capturas en un PDF A4 vertical, una imagen por página."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    c = canvas.Canvas(ruta_pdf, pagesize=A4)
    ancho, alto = A4
    margen = 1.5 * cm
    for img in imagenes:
        if not os.path.isfile(img):
            continue
        ir = ImageReader(img)
        iw, ih = ir.getSize()
        # escalar para que entre en la página manteniendo proporción
        escala = min((ancho - 2 * margen) / iw, (alto - 2 * margen) / ih)
        dw, dh = iw * escala, ih * escala
        c.drawImage(ir, (ancho - dw) / 2, (alto - dh) / 2, width=dw, height=dh)
        c.showPage()
    c.save()
    print(f"  ✓ PDF armado: {ruta_pdf}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Capturas SISFE para apertura de cuenta judicial (Banco Municipal de Rosario)")
    ap.add_argument("--cuij", required=True, help="CUIJ del expediente (21-XXXXXXXX-X)")
    ap.add_argument("--out", default=".", help="Carpeta de salida para capturas y PDF")
    ap.add_argument("--caratula", default="", help="Carátula conocida (opcional, para verificación)")
    args = ap.parse_args()

    if not _PATRON_CUIJ.fullmatch(args.cuij):
        print(f"  ✗ CUIJ con formato inválido: {args.cuij} (esperado 21-XXXXXXXX-X)")
        sys.exit(1)

    res = capturar_expediente(args.cuij, args.out, args.caratula)
    if res.get("ok"):
        print("\n  ✓ Listo. Para el borrador de Gmail (nunca se envía solo):")
        print(f"    to:       {res['destinatario']}")
        print(f"    subject:  {res['asunto']}")
        print(f"    caratula: {res['caratula']}")
        print(f"    cuij:     {res['cuij']}")
        print(f"    adjunto:  {res['pdf']}  (arrastrarlo a mano al borrador)")
    else:
        print(f"\n  ✗ {res.get('error', 'Error desconocido')}")
        sys.exit(2)
