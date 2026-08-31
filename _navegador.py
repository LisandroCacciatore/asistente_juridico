# ============================================================
#  _NAVEGADOR.PY — Motor compartido del navegador (Playwright)
# ------------------------------------------------------------
#  Abre Chrome con un perfil persistente (igual criterio que el
#  monitor de SISFE): la sesión queda guardada, así no hay que
#  loguearse de nuevo cada vez. Lo usan firma.py y meta_juridico.py.
# ============================================================

import os
import sys
import logging
from contextlib import contextmanager
from playwright.sync_api import sync_playwright

from config_portales import PERFIL_CHROME, CARPETA_DESCARGAS

logger = logging.getLogger("AsistenteJuridico.Navegador")


# --- Consola Windows a prueba de Unicode ---------------------------
# La consola de Windows usa cp1252 por defecto y NO puede imprimir
# símbolos como ✓ ✗ ⚠ ↳: cualquier print con ellos lanzaba
# UnicodeEncodeError ('charmap' codec can't encode...). Forzamos UTF-8
# con errors="replace" para que nunca crashee. Se ejecuta al importar
# este módulo, que lo importan firma.py, meta_juridico.py y (vía ellos)
# el servidor, así que cubre todos los caminos.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@contextmanager
def abrir_navegador(usar_chrome=True, descargas=None, headless=False):
    """
    Abre un navegador con perfil persistente y devuelve (contexto, pagina).

    usar_chrome : True usa el Chrome instalado de Santiago (channel="chrome"),
                  con su perfil. False usa el Chromium de Playwright (para pruebas).
    descargas   : carpeta donde aceptar las descargas (PDF firmado, etc.).
    headless    : False = ventana visible (necesario: la firma la hacés vos a mano).
    """
    carpeta_descargas = descargas or CARPETA_DESCARGAS
    os.makedirs(PERFIL_CHROME, exist_ok=True)
    os.makedirs(carpeta_descargas, exist_ok=True)

    with sync_playwright() as p:
        kwargs = dict(
            user_data_dir=PERFIL_CHROME,
            headless=headless,
            accept_downloads=True,
            downloads_path=carpeta_descargas,
            viewport={"width": 1280, "height": 900},
        )
        if usar_chrome:
            kwargs["channel"] = "chrome"   # usa el Chrome real, no el Chromium de PW

        try:
            contexto = p.chromium.launch_persistent_context(**kwargs)
        except Exception as err:
            if usar_chrome and "channel" in kwargs:
                msg = (
                    f"No se pudo lanzar Chrome con el canal del sistema ({err}). "
                    "Reintentando con Chromium integrado… Puede requerir volver a "
                    "loguearse en FirmAr y Meta Jurídico porque el perfil persistente "
                    "solo funciona con Chrome."
                )
                print(f"  ⚠ {msg}")
                logger.warning(msg)
                kwargs.pop("channel", None)
                contexto = p.chromium.launch_persistent_context(**kwargs)
            else:
                raise err

        pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
        try:
            yield contexto, pagina
        finally:
            contexto.close()


def pausa_humana(mensaje):
    """
    Frena el script y espera a que Santiago complete un paso a mano
    (contraseña de firma, token, código 2FA) y presione ENTER.
    Es agnóstico al método: sirve con firma web o con token físico.
    """
    print("")
    print("  ┌───────────────────────────────────────────────────────────┐")
    print("  │  ACCIÓN TUYA                                               │")
    print("  └───────────────────────────────────────────────────────────┘")
    print(f"  {mensaje}")
    input("  >>> Cuando termines, volvé acá y presioná ENTER para continuar... ")
    print("")
