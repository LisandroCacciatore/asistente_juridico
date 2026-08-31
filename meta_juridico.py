# -*- coding: utf-8 -*-
# ============================================================
#  META_JURIDICO.PY — Sube el PDF firmado al expediente en Meta
#                     Jurídico. Frena para el 2FA y deja la
#                     CONFIRMACIÓN FINAL en tus manos.
# ------------------------------------------------------------
#  USO (desde CMD):
#     python meta_juridico.py "ruta\a\cedula_FIRMADO.pdf" "21-00000001-0" "GONZALEZ..."
#                              └─ PDF firmado ─┘            └─ CUIJ ─┘      └─ carátula (opcional) ─┘
#
#  QUÉ HACE:
#     1) Abre Meta Jurídico en tu Chrome (perfil persistente).
#     2) FRENA para que ingreses el 2FA (SMS / app / mail).
#     3) Busca el expediente por APELLIDO en el buscador real (dentro
#        de <main>, el último si hay más de uno), navegando por el
#        menú "Expedientes" y disparando la búsqueda con el botón
#        "search" (confirmado por grabación real).
#     4) Si no encuentra NINGÚN resultado, no cae al modo manual —
#        lanza ExpedienteNoEncontrado (el servidor lo marca "Solicita
#        Revisión" en el dashboard, sin riesgo de crear un duplicado).
#     5) Si lo encuentra: adjunta el PDF firmado directo al
#        input[name="file"] real (confirmado por grabación).
#     6) FRENA antes de presentar: vos revisás y confirmás la subida.
# ============================================================

import os
import sys

from config_portales import META_URL, META_EXPEDIENTES_URL
from _navegador import abrir_navegador, pausa_humana


class ExpedienteNoEncontrado(Exception):
    """La búsqueda en Meta Jurídico no devolvió ningún resultado — el
    expediente no existe ahí (distinto de un tropiezo de automatización).
    """
    pass


def subir(ruta_pdf, cuij, caratula=None, usar_chrome=True, pausar=None):
    pausar = pausar or pausa_humana
    if not os.path.isfile(ruta_pdf):
        print(f"  ✗ No encuentro el PDF firmado: {ruta_pdf}")
        return False

    ruta_pdf = os.path.abspath(ruta_pdf)
    print(f"\n  Subiendo a Meta Jurídico:")
    print(f"    Archivo  : {os.path.basename(ruta_pdf)}")
    print(f"    CUIJ     : {cuij}")
    print(f"    Carátula : {caratula or '(no provista)'}")

    with abrir_navegador(usar_chrome=usar_chrome) as (ctx, page):
        print("  Abriendo Meta Jurídico…")
        page.goto(META_URL)

        pausar(
            "Si Meta Jurídico pide login, ingresá tu mail y contraseña, y el\n"
            "  código de verificación que te llega por mail."
        )

        adjuntado = False
        apellido = (caratula or "").split()[0] if caratula else cuij
        try:
            # Navegar por el menú (como en la grabación real), no goto()
            # directo — en una SPA, cargar la URL de una sola vez puede
            # saltear inicialización que sí ocurre al navegar por clic.
            print("    → yendo a Expedientes...")
            page.get_by_text("Expedientes", exact=False).first.click(timeout=15000)
            page.wait_for_timeout(800)

            print(f"    → buscando '{apellido}'...")
            buscador = page.get_by_role("main").get_by_role("textbox", name="Buscar").last
            buscador.fill(apellido, timeout=8000)

            # El botón real que dispara la búsqueda se llama "search"
            # (confirmado por grabación). Enter como respaldo si no está.
            try:
                page.get_by_role("button", name="search").click(timeout=5000)
            except Exception:
                buscador.press("Enter")
            page.wait_for_timeout(1500)

            if "/expedient/details" not in page.url:
                texto_buscar = caratula or apellido
                print("    → revisando si hay resultados...")
                listado = page.get_by_label("Listado de expedientes")
                try:
                    listado.wait_for(timeout=3000)
                    hay_resultados = listado.locator(":scope *").count() > 0
                except Exception:
                    hay_resultados = False

                if not hay_resultados:
                    raise ExpedienteNoEncontrado(
                        f"No se encontró ningún expediente para '{texto_buscar}' en Meta Jurídico"
                    )

                print("    → clic en la fila del resultado...")
                # La fila del resultado vive en el contenedor "Listado de
                # expedientes" (confirmado por grabación) — acotar ahí
                # evita matchear texto en cualquier otra parte de la página.
                page.get_by_label("Listado de expedientes").get_by_text(
                    texto_buscar, exact=False
                ).first.click(timeout=10000)

            print("    → Abrir expediente...")
            page.get_by_role("button", name="Abrir expediente").click(timeout=10000)
            print("    → Adjuntos...")
            page.get_by_role("button", name="Adjuntos").click(timeout=10000)
            print("    → Cargar archivos...")
            page.get_by_role("button", name="upload Cargar archivos", exact=True).click(timeout=10000)

            # El input de archivo es real y directo (confirmado por
            # grabación): input[name="file"]. No es un selector de
            # Windows — se le pasa el archivo sin rodeos.
            print("    → adjuntando el PDF...")
            page.locator('input[name="file"]').set_input_files(ruta_pdf, timeout=10000)
            print("  ✓ PDF firmado adjuntado")
            adjuntado = True
        except ExpedienteNoEncontrado:
            # No es un tropiezo de automatización: el expediente
            # genuinamente no existe en Meta Jurídico con ese nombre.
            # No caer al modo manual (evita que alguien termine creando
            # un expediente nuevo y duplicado) — se relanza para que el
            # servidor lo marque como "Solicita Revisión".
            raise
        except Exception as e:
            print(f"  ⚠ No pude completar la carga automática ({type(e).__name__}): {e}")

        if not adjuntado:
            pausar(
                f"Abrí en Meta Jurídico el expediente {caratula or f'CUIJ {cuij}'},\n"
                f"  entrá a la solapa Adjuntos y cargá el archivo:\n  {ruta_pdf}\n"
                "  Cuando esté adjunto (sin presentar), volvé para continuar."
            )

        pausar(
            "Revisá que el expediente y el archivo sean los correctos\n"
            "  y apretá vos el botón de PRESENTAR / CONFIRMAR en Meta Jurídico."
        )
        print("  ✓ Listo. Cédula presentada en el expediente.\n")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('  Uso: python meta_juridico.py "ruta\\a\\cedula_FIRMADO.pdf" "CUIJ" ["Carátula"]')
        sys.exit(1)
    subir(sys.argv[1], sys.argv[2], caratula=(sys.argv[3] if len(sys.argv) > 3 else None))
