# ============================================================
#  CONFIG_PORTALES.PY — Datos de los portales de firma y Meta Jurídico
# ------------------------------------------------------------
#  IMPORTANTE: acá NO va ninguna contraseña. La contraseña de firma
#  y el código 2FA los ingresás vos a mano en el navegador, nunca se
#  guardan. Este archivo solo tiene direcciones y rutas.
#
#  Pensado para correr en CUALQUIER máquina (esta, la de Santiago, o
#  cualquier otra): ninguna ruta está fija a un usuario de Windows en
#  particular. Se calculan solas al importar el archivo.
# ============================================================

import os as _os

_CARPETA_BASE = _os.path.dirname(_os.path.abspath(__file__))

# --- Direcciones de los portales ---------------------------------
# ⬅ Portal de firma: plataforma FirmAr de la Nación (autenticación por OTP).
FIRMA_URL = "https://firmar.gob.ar/firmador/#/"

# ⬅ Meta Jurídico — página de login (URL real, sin la cola de tracking).
META_URL = "https://app.metajuridico.com/signin"

# ⬅ URL directa al listado de expedientes (confirmada por grabación real:
# apareció como destino de un page.goto durante la captura con codegen).
META_EXPEDIENTES_URL = "https://app.metajuridico.com/expedient"


# --- Perfil de Chrome persistente --------------------------------
# Igual que en el monitor de SISFE: usamos un perfil propio para que
# las sesiones queden guardadas y no haya que volver a loguearse cada vez.
# Vive DENTRO de esta misma carpeta, así cada máquina (esta, la de
# Santiago, o cualquier otra) arma su propio perfil sin pisarse.
PERFIL_CHROME = _os.path.join(_CARPETA_BASE, "chrome_profile_portales")


# --- Carpeta donde el portal de firma descarga el PDF firmado -----
# El script vigila esta carpeta para detectar el PDF firmado apenas baja.
# os.path.expanduser("~") apunta siempre a "C:\Users\<el usuario que
# esté logueado>" en cualquier máquina, así que esto ya es correcto
# tanto para vos como para Santiago sin tocar nada.
CARPETA_DESCARGAS = _os.path.join(_os.path.expanduser("~"), "Downloads")


# --- Modo de espera en las puertas humanas -----------------------
#  "enter"     -> el script frena y espera a que presiones ENTER en la
#                 consola después de completar el paso a mano. (Recomendado:
#                 anda igual con contraseña web o con token físico.)
#  "descarga"  -> además, en la firma, detecta solo cuando baja el PDF firmado.
MODO_PAUSA = "enter"


# --- Selectores capturados del portal real ------------------------
# FirmAr: botón "SUBIR DOCUMENTOS" en la pantalla "Firmar documento".
# Sacado del inspector del navegador (no es un <button> nativo, es un
# div estilizado — por eso el selector es un camino CSS, no un rol).
FIRMAR_SELECTOR_SUBIR = (
    "#content > div > div > div:nth-child(2) > div > div > div > div "
    "> form > div:nth-child(1) > div > div"
)

# --- Sufijo para el PDF firmado ----------------------------------
SUFIJO_FIRMADO = "_FIRMADO"
