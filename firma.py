# -*- coding: utf-8 -*-
# ============================================================
#  FIRMA.PY — Firma digital en FirmAr, con pausa humana.
# ------------------------------------------------------------
#  Dos modos:
#    firmar(ruta_pdf, ...)        -> un solo documento (ya validado).
#    firmar_lote(items, ...)      -> varios documentos EN UNA SOLA
#                                     ventana de Chrome: login una vez,
#                                     y una cola de documentos donde
#                                     cada uno pide su propio PIN.
#
#  NO automatiza: login (CUIL/contraseña/OTP), PIN, ni el clic de
#  FIRMAR. Todo lo demás (adjuntar el PDF, descargar el firmado,
#  pasar al siguiente documento) es automático.
# ============================================================

import os
import re
import sys
from urllib.parse import urljoin

from config_portales import FIRMA_URL, SUFIJO_FIRMADO, FIRMAR_SELECTOR_SUBIR
from _navegador import abrir_navegador, pausa_humana


# ============================================================
#  Helpers reusados por firmar() y firmar_lote()
# ============================================================

def _adjuntar_pdf(page, ruta_pdf):
    """
    Intenta adjuntar el PDF con dos métodos: el selector CSS real
    capturado del inspector, y si falla, el botón por su texto.
    Devuelve True si lo logró.
    """
    for intento, hacer_clic in enumerate([
        lambda: page.click(FIRMAR_SELECTOR_SUBIR, timeout=8000),
        lambda: page.get_by_role("button", name=re.compile("subir documentos", re.I)).click(timeout=8000),
    ], start=1):
        try:
            with page.expect_file_chooser(timeout=10000) as fc_info:
                hacer_clic()
            fc_info.value.set_files(ruta_pdf)
            print(f"  ✓ PDF cargado en FirmAr (intento {intento})")
            return True
        except Exception as e:
            print(f"  ⚠ Intento {intento} de adjuntar falló ({type(e).__name__})")
    return False


def _descargar_firmado(page, destino):
    """
    Busca el botón "Descargar documento" en la pantalla de éxito y trae
    el archivo directo, reusando la sesión ya autenticada del navegador
    (robusto ante target="_blank"). Guarda en `destino` y lo devuelve,
    o None si no lo consiguió.
    """
    try:
        boton = page.get_by_role("button", name=re.compile("descargar documento", re.I))
        href = boton.get_attribute("href", timeout=6000)
        if href:
            url = urljoin(page.url, href)
            resp = page.context.request.get(url)
            if resp.ok:
                with open(destino, "wb") as f:
                    f.write(resp.body())
                print(f"  ✓ Cédula firmada guardada en:\n    {destino}\n")
                return destino
            print(f"  ⚠ El portal respondió {resp.status} al pedir el documento firmado.")
    except Exception as e:
        print(f"  ⚠ No pude ubicar el botón de descarga automáticamente ({type(e).__name__}).")
    return None


def _volver_a_firmar_documento(page):
    """Entre un documento y el siguiente (modo lote): vuelve a la
    pantalla de carga en blanco haciendo clic en 'FIRMAR DOCUMENTO'
    del menú superior."""
    try:
        page.get_by_text("FIRMAR DOCUMENTO", exact=False).first.click(timeout=8000)
        page.wait_for_timeout(800)
        return True
    except Exception as e:
        print(f"  ⚠ No pude volver solo a 'Firmar documento' ({type(e).__name__}).")
        return False


# ============================================================
#  Modo individual (ya validado en producción)
# ============================================================

def firmar(ruta_pdf, usar_chrome=True, headless=False, pausar=None):
    pausar = pausar or pausa_humana
    if not os.path.isfile(ruta_pdf):
        print(f"  ✗ No encuentro el archivo: {ruta_pdf}")
        return None

    ruta_pdf = os.path.abspath(ruta_pdf)
    nombre = os.path.basename(ruta_pdf)
    destino = os.path.join(
        os.path.dirname(ruta_pdf),
        os.path.splitext(nombre)[0] + SUFIJO_FIRMADO + ".pdf",
    )
    print(f"\n  Firmando: {nombre}")

    with abrir_navegador(usar_chrome=usar_chrome, headless=headless) as (ctx, page):
        print("  Abriendo portal de firma…")
        page.goto(FIRMA_URL)

        pausar(
            "Ingresá en FirmAr: CUIL, contraseña, OTP y Acceder.\n"
            "  Cuando llegues a la pantalla 'Firmar documento', volvé para continuar."
        )

        adjuntado = _adjuntar_pdf(page, ruta_pdf)

        mensaje_firma = (
            "Ingresá tu PIN y hacé clic en FIRMAR.\n"
            "  Cuando veas la pantalla 'Documento firmado', volvé para continuar\n"
            "  (el script descarga el PDF firmado solo)."
        )
        if adjuntado:
            pausar("El PDF ya está cargado en FirmAr.\n  " + mensaje_firma)
        else:
            pausar(f"Subí manualmente el documento a firmar:\n  {ruta_pdf}\n  " + mensaje_firma)

        resultado = _descargar_firmado(page, destino)
        if resultado:
            return resultado

    print(f"  ↳ Si descargaste el PDF firmado, movelo a mano a:\n    {destino}\n")
    return None


# ============================================================
#  Modo lote — NUEVO: varios documentos, una sola ventana
# ============================================================

def firmar_lote(items, usar_chrome=True, headless=False, pausar=None, on_resultado=None):
    """
    items: lista de dicts [{"id_cedula": ..., "ruta_pdf": ...}, ...]
    on_resultado: callback opcional on_resultado(id_cedula, ruta_firmada_o_None),
                  se llama apenas termina CADA documento (no al final del lote),
                  para que el llamador pueda ir guardando en estado.json.

    Devuelve dict {id_cedula: ruta_firmada_o_None} con todos los resultados.
    """
    pausar = pausar or pausa_humana
    resultados = {}
    total = len(items)

    # Filtramos de entrada los que no tienen archivo, para no interrumpir
    # el lote a mitad de camino por un PDF faltante.
    validos = []
    for it in items:
        ruta = it.get("ruta_pdf")
        if ruta and os.path.isfile(ruta):
            validos.append(it)
        else:
            print(f"  ✗ {it.get('id_cedula')}: no encuentro el archivo ({ruta})")
            resultados[it.get("id_cedula")] = None
            if on_resultado:
                on_resultado(it.get("id_cedula"), None)

    if not validos:
        print("  ⚠ Ningún documento válido para firmar en el lote.")
        return resultados

    with abrir_navegador(usar_chrome=usar_chrome, headless=headless) as (ctx, page):
        print(f"\n  Firmando en lote: {len(validos)} documento(s).")
        print("  Abriendo portal de firma…")
        page.goto(FIRMA_URL)

        # --- Login: UNA sola vez para todo el lote ------------------
        pausar(
            "Ingresá en FirmAr: CUIL, contraseña, OTP y Acceder.\n"
            "  Cuando llegues a la pantalla 'Firmar documento', volvé para continuar.\n"
            f"  (vas a firmar {len(validos)} documento(s) en esta misma ventana)."
        )

        for i, it in enumerate(validos, start=1):
            id_cedula = it["id_cedula"]
            ruta_pdf = os.path.abspath(it["ruta_pdf"])
            nombre = os.path.basename(ruta_pdf)
            destino = os.path.join(
                os.path.dirname(ruta_pdf),
                os.path.splitext(nombre)[0] + SUFIJO_FIRMADO + ".pdf",
            )
            print(f"\n  [{i}/{total}] Firmando: {nombre}")

            adjuntado = _adjuntar_pdf(page, ruta_pdf)

            mensaje_firma = (
                f"Documento {i} de {total}: {nombre}\n"
                "  Ingresá tu PIN y hacé clic en FIRMAR.\n"
                "  Cuando veas 'Documento firmado', volvé para continuar."
            )
            if adjuntado:
                pausar(mensaje_firma)
            else:
                pausar(f"Subí manualmente:\n  {ruta_pdf}\n  " + mensaje_firma)

            resultado = _descargar_firmado(page, destino)
            resultados[id_cedula] = resultado
            if on_resultado:
                on_resultado(id_cedula, resultado)

            if not resultado:
                print(f"  ⚠ {id_cedula}: no se pudo confirmar el firmado automáticamente.")

            # Preparar la pantalla para el próximo documento (si queda alguno).
            if i < total:
                if not _volver_a_firmar_documento(page):
                    pausar(
                        "Volvé manualmente a 'FIRMAR DOCUMENTO' en el menú de arriba\n"
                        "  para cargar el próximo documento, y continuá."
                    )

    firmados = sum(1 for v in resultados.values() if v)
    print(f"\n  ✓ Lote terminado: {firmados}/{total} firmados correctamente.\n")
    return resultados


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('  Uso: python firma.py "ruta\\a\\la\\cedula.pdf" [otro.pdf ...]')
        sys.exit(1)
    if len(sys.argv) == 2:
        firmar(sys.argv[1])
    else:
        items = [{"id_cedula": f"doc{i}", "ruta_pdf": p} for i, p in enumerate(sys.argv[1:], start=1)]
        firmar_lote(items)
