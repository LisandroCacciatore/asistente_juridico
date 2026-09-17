# -*- coding: utf-8 -*-
# ============================================================
#  CONFIG.EXAMPLE.PY — Plantilla de configuración por máquina
# ------------------------------------------------------------
#  ⬅ NO editar este archivo. Copialo a `config.py` y completalo:
#
#     copy config.example.py config.py
#
#  config.py NO se sube al repo (está en .gitignore): cada máquina
#  (Lisandro, el socio, el hub) tiene el suyo con sus datos.
#
#  Todas las claves que el código importa están acá. Si falta una,
#  el sistema crashea al importar (varias se importan a nivel de
#  módulo, no adentro de las funciones).
# ============================================================

import os as _os

_CARPETA_BASE = _os.path.dirname(_os.path.abspath(__file__))

# --- SISFE (monitor_playwright.py) ---------------------------
# Tu número de matrícula (solo eso; la contraseña se ingresa a mano).
SISFE_USUARIO = "000000"

# Registros del monitor (rutas relativas a esta carpeta).
ARCHIVO_REGISTRO = _os.path.join(_CARPETA_BASE, "cedulas_procesadas.json")
ARCHIVO_ESTADO = _os.path.join(_CARPETA_BASE, "estado_expedientes.json")
CARPETA_EXP_DIGITAL = _os.path.join(_CARPETA_BASE, "ExpedientesDigitales")

# --- Modo continuo del monitor (monitor_playwright.py) --------
INTERVALO_MINUTOS = 10
HORARIO_INICIO = "08:00"
HORARIO_FIN = "18:00"
DIAS_HABILES = [0, 1, 2, 3, 4]   # lunes a viernes (datetime.weekday)

# Cuánto se espera a que alguien escriba la contraseña de SISFE antes de
# dar el ciclo por perdido. Solo aplica al modo continuo: si nadie está
# adelante de la máquina, el ciclo se saltea y el próximo vuelve a
# pedir el login, en vez de quedar esperando ENTER toda la jornada.
ESPERA_LOGIN_MINUTOS = 20

# --- Personas del estudio (sesion.py) -------------------------
# Quién puede operar el asistente y con qué identidad actúa en los
# portales. Cada uno tiene su propio acceso al SISFE y a FirmAr, así que
# lo normal es que la identidad sea la misma persona que está operando.
#
#   mail      : con el que entra al asistente. Cada uno entra con el suyo
#               (el vacío no bloquea: mientras no lo tengas, entra con el
#               nombre).
#   matricula : la del SISFE. Si todavía no la tenés, dejala vacía: el
#               sistema muestra el campo vacío, nunca un valor inventado.
#   firma     : cómo identificar su Firma Digital (el CUIL con el que firma).
#   perfil    : la carpeta del perfil de Chrome de esa persona. La sesión
#               del SISFE y la de FirmAr son personales y no se comparten.
#
# ⚠ "Socio" es provisorio: reemplazalo por el nombre real cuando lo sepas.
PERSONAS = {
    "Santiago": {"mail": "", "matricula": SISFE_USUARIO, "firma": "",
                 "perfil": "chrome_profile_portales"},
    "Jr":       {"mail": "", "matricula": "",            "firma": "",
                 "perfil": "chrome_profile_jr"},
    "Socio":    {"mail": "", "matricula": "",            "firma": "",
                 "perfil": "chrome_profile_socio"},
}

# Cuándo vence la declaración de quién está trabajando:
SESION_VENCE_AL_CAMBIAR_EL_DIA = True    # nadie declara quién es y sigue
                                         # valiendo al otro día
SESION_HORAS_INACTIVIDAD = 12            # cubre la máquina que quedó abierta

# --- Cédulas (generar_cedula.py) ------------------------------
# Carpeta genérica y transitoria para los PDF: se borran al
# presentarse en Meta Jurídico (ver estado.marcar_presentada).
CARPETA_CEDULAS_TEMP = _os.path.join(_CARPETA_BASE, "cedulas_temp")

# --- Archivo por cliente (expediente_utils.py — LEGACY) -------
# Estas claves ya NO se usan para las cédulas nuevas (van a
# CARPETA_CEDULAS_TEMP), pero expediente_utils las importa a
# nivel de módulo: si faltan, crashea TODO el pipeline.
# Dejá la ruta base aunque no uses el archivo por cliente.
RUTA_ESTUDIO = _os.path.join(_CARPETA_BASE, "ESTUDIO JURIDICO")
RAMAS = {
    "LABORAL": "Laboral",
    # "CIVIL": "Civil",
    # "FAMILIA": "Familia",
}
CLASIFICACION = {
    "LABORAL": ["accidente", "laboral", "despido", "honorarios"],
    # "CIVIL": ["cobro", "daños", "ejecución"],
}

# --- Juzgados: juez/secretario por fuero y nominación ---------
# Clave: f"{FUERO} {nominacion}" (ej: "LABORAL 3", "CIVIL 1", "FAMILIA 8").
# Si un juzgado no está, la cédula sale con juez/secretario en blanco.
#
# DEJALO VACÍO si no necesitás pisar nada: los 44 juzgados de Rosario
# (Laboral 1-10, Civil 1-22, Familia 1-12) se leen solos de
# skills/juzgados_rosario.json. Lo que pongas acá tiene prioridad sobre el
# JSON, así que usalo solo para corregir un juzgado puntual.
JUZGADOS = {
    # "LABORAL 3": {
    #     "juez": "Nombre del Juez",
    #     "secretario": "Nombre del Secretario",
    #     "cargo_juez": "JUEZ",
    #     "cargo_secretario": "SECRETARIO",
    # },
}

# --- Domicilios conocidos de ART demandadas (cedulas.py) -------
# Clave: texto que aparece en la carátula (se compara normalizado).
DOMICILIOS_ART = {
    # "ART EJEMPLO S.A.": "Domicilio de la ART - Ciudad",
}

# --- Destinatarios cuando la demandada es la Provincia ---------
# (primer decreto / traslado: Gobernador + Fiscalía de Estado)
DESTINATARIOS_PROVINCIA_1ER_DECRETO = [
    # {"nombre": "Sr. Gobernador de la Provincia de Santa Fe",
    #  "domicilio": "Domicilio oficial"},
    # {"nombre": "Fiscalía de Estado de la Provincia",
    #  "domicilio": "Domicilio oficial"},
]

# --- Formato de salida de las cédulas --------------------------
# "pdf" (por defecto) o "docx" (genera los .docx históricos).
FORMATO_SALIDA = "pdf"
