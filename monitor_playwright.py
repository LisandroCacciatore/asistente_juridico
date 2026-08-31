# -*- coding: utf-8 -*-
# ============================================================
#  MONITOR_PLAYWRIGHT.PY — Lee SISFE con Playwright y genera
#  las cédulas (Nivel 1, sin IA). Port del monitor.py de Selenium.
# ------------------------------------------------------------
#  Reusa TU lógica probada:
#    - extraccion_decretos.py  (aislar el texto de cada decreto)
#    - expediente_utils.py     (deducir juzgado/juez)
#    - cedulas.py              (destinatarios, clasificación)
#    - generar_cedula.py       (arma el PDF + registra en estado.json)
#
#  Estrategia de lectura: descarga el "Expediente Digital" completo
#  una vez por expediente con novedades y extrae de ahí cada decreto
#  (igual que el monitor viejo, sin bajar documento por documento).
#
#  ⚠ Los selectores de SISFE hay que validarlos contra el portal real
#    (marcados con ⬅ VALIDAR). El reCAPTCHA es puerta humana.
# ============================================================

import os
import re
import sys
import json
from datetime import datetime
from datetime import timedelta as _timedelta

# Consola Windows a prueba de Unicode
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from playwright.sync_api import sync_playwright

# Silencia el aviso "Could not get FontBBox..." de pdfminer/pdfplumber:
# es ruido sobre métricas de fuente, no afecta la extracción de texto.
import logging
logging.getLogger("pdfminer").setLevel(logging.ERROR)

from config import (
    SISFE_USUARIO, ARCHIVO_REGISTRO, ARCHIVO_ESTADO, CARPETA_EXP_DIGITAL,
)
from expediente_utils import datos_del_juzgado
from extraccion_decretos import es_cedula_ya_presentada, extraer_texto_decreto
import cedulas
import generar_cedula
import estado

# --- Constantes SISFE -------------------------------------------
SISFE_LOGIN = "https://sisfe.justiciasantafe.gov.ar/login-matriculado"
SISFE_BUSCAR = "https://sisfe.justiciasantafe.gov.ar/buscar-expediente"
SISFE_DETALLE = "https://sisfe.justiciasantafe.gov.ar/detalle-expediente/{id}"
SISFE_PARTES = "https://sisfe.justiciasantafe.gov.ar/nueva-notificacion-expediente/{id}"
DIAS_NOVEDADES = "10"
CARPETA_BASE = os.path.dirname(os.path.abspath(__file__))
PERFIL_SISFE = os.path.join(CARPETA_BASE, "chrome_profile_sisfe")


# ============================================================
#  REGISTRO ANTI-DUPLICADOS (JSON) — igual que el monitor viejo
# ============================================================
def cargar_registro():
    if os.path.exists(ARCHIVO_REGISTRO):
        with open(ARCHIVO_REGISTRO, encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_registro(registro):
    os.makedirs(os.path.dirname(ARCHIVO_REGISTRO), exist_ok=True)
    with open(ARCHIVO_REGISTRO, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)

def decreto_ya_procesado(registro, cuij, id_decreto):
    return cuij in registro and id_decreto in registro[cuij]

def marcar_como_procesado(registro, cuij, id_decreto, archivos):
    registro.setdefault(cuij, {})[id_decreto] = {
        "fecha_proceso": datetime.now().isoformat(), "archivos": archivos,
    }

def cargar_estado():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO, encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_estado(estado):
    os.makedirs(os.path.dirname(ARCHIVO_ESTADO), exist_ok=True)
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

def expediente_sin_novedades(estado, cuij, cant, ultimo):
    prev = estado.get(cuij)
    return bool(prev) and prev.get("cantidad_movimientos") == cant and prev.get("ultimo_movimiento") == ultimo

def actualizar_estado_expediente(estado, cuij, cant, ultimo):
    estado[cuij] = {"cantidad_movimientos": cant, "ultimo_movimiento": ultimo,
                    "ultima_visita": datetime.now().isoformat()}


def pausa(msg):
    print("\n  " + "─" * 55)
    print("  ACCIÓN TUYA")
    print("  " + msg)
    input("  >>> Cuando termines, presioná ENTER para continuar... ")
    print("")


# ============================================================
#  NAVEGADOR (perfil persistente para reCAPTCHA)
# ============================================================
def abrir_sisfe(p, usar_chrome=True):
    os.makedirs(PERFIL_SISFE, exist_ok=True)
    os.makedirs(CARPETA_EXP_DIGITAL, exist_ok=True)
    kwargs = dict(
        user_data_dir=PERFIL_SISFE, headless=False, accept_downloads=True,
        downloads_path=CARPETA_EXP_DIGITAL, viewport={"width": 1280, "height": 900},
    )
    if usar_chrome:
        kwargs["channel"] = "chrome"
    return p.chromium.launch_persistent_context(**kwargs)


def login_sisfe(page):
    """Login con selectores por id (del codegen). El password y el
    reCAPTCHA los completás vos: es puerta humana. Con el perfil
    persistente, muchas veces ya vas a estar adentro."""
    page.goto(SISFE_BUSCAR)
    page.wait_for_timeout(1500)
    # ¿Ya logueado? Si la página de búsqueda cargó, seguimos.
    if "login" not in page.url and page.locator("#localidad, table").count() > 0:
        print("  ✓ Sesión activa (perfil de Chrome)")
        return

    page.goto(SISFE_LOGIN)
    page.wait_for_timeout(1000)
    try:
        page.locator("#circunscripcion").select_option("2")   # Rosario ⬅ VALIDAR valor
        page.locator("#colegio").select_option("0")           # Abogados ⬅ VALIDAR valor
        page.locator("#matricula").fill(SISFE_USUARIO)
    except Exception:
        print("  ⚠ No pude precargar los campos de login — completá a mano.")

    pausa("Ingresá tu CONTRASEÑA de SISFE, resolvé el reCAPTCHA y hacé clic en INGRESAR.")


# ============================================================
#  BÚSQUEDA DE EXPEDIENTES CON NOVEDADES
# ============================================================
def obtener_expedientes(page):
    expedientes = []
    page.goto(SISFE_BUSCAR)
    page.wait_for_timeout(2500)

    # Filtro de "novedades últimos X días" — selector real capturado con
    # codegen: hay que DESPLEGAR "Filtros de Búsqueda" primero (está
    # colapsado por defecto), recién ahí el campo #diasNovedades es visible.
    try:
        page.get_by_text(re.compile("Filtros de Búsqueda", re.I)).first.click(timeout=5000)
        page.wait_for_timeout(500)
    except Exception:
        pass  # puede que ya esté desplegado

    try:
        campo = page.locator("#diasNovedades")
        campo.click(timeout=5000)
        campo.fill(DIAS_NOVEDADES)
        print(f"  ✓ Filtro: novedades últimos {DIAS_NOVEDADES} días")
    except Exception:
        print("  ⚠ No encontré el campo de días — se busca sin ese filtro")

    try:
        page.get_by_role("button", name=re.compile("Efectuar la búsqueda", re.I)).click()
    except Exception:
        page.get_by_text(re.compile("Efectuar la búsqueda", re.I)).first.click()
    page.wait_for_timeout(3500)

    filas = page.locator("table tbody tr")
    for i in range(filas.count()):
        fila = filas.nth(i)
        try:
            texto = fila.inner_text()
            m = re.search(r'21-\d{8}-\d', texto)
            if not m:
                continue
            cuij = m.group(0)
            id_sisfe = None
            try:
                href = fila.locator("a").first.get_attribute("href")
                mm = re.search(r'/(\d{8,})', href or "")
                if mm:
                    id_sisfe = mm.group(1)
            except Exception:
                pass
            expedientes.append({"cuij": cuij, "id_sisfe": id_sisfe, "texto": texto})
        except Exception:
            continue

    print(f"  ✓ Expedientes con novedades: {len(expedientes)}")
    return expedientes


# ============================================================
#  DESCARGA + LECTURA DEL EXPEDIENTE DIGITAL
# ============================================================
def descargar_expediente_digital(page):
    """Clic en 'Descargar Expediente Digital', captura la descarga con
    expect_download, extrae el texto con pdfplumber (páginas unidas con
    '\\x0c') y devuelve el texto completo."""
    try:
        import pdfplumber
    except ImportError:
        print("    ⚠ Falta pdfplumber. Ejecutá: pip install pdfplumber")
        return None

    try:
        with page.expect_download(timeout=45000) as di:
            page.get_by_text(re.compile("Descargar Expediente Digital", re.I)).first.click()
        download = di.value
        ruta = download.path()   # archivo temporal de Playwright
        paginas = []
        with pdfplumber.open(ruta) as pdf:
            for pg in pdf.pages:
                paginas.append(pg.extract_text() or "")
        return ("\x0c".join(paginas)).strip() or None
    except Exception as e:
        print(f"    ⚠ No se pudo descargar/leer el Expediente Digital: {type(e).__name__}")
        return None


# ============================================================
#  DECRETOS NUEVOS EN LA TABLA DE MOVIMIENTOS
# ============================================================
def obtener_decretos_nuevos(page, id_exp, registro, cuij, estado):
    decretos = []
    filas = page.locator("table tbody tr")
    cant = filas.count()
    ultimo = filas.nth(cant - 1).inner_text() if cant else ""
    print(f"    Movimientos en la tabla: {cant}")

    if estado is not None and cuij and expediente_sin_novedades(estado, cuij, cant, ultimo):
        print("    → Sin novedades desde la última visita, se saltea")
        return decretos

    # Primera pasada: detectar decretos/sentencias pendientes por su ícono
    hoy = datetime.now()
    limite_fecha = hoy - _timedelta(days=int(DIAS_NOVEDADES))
    pendientes = []
    for i in range(cant):
        fila = filas.nth(i)
        try:
            html = fila.inner_html()
            if "fa-user-check" in html:          # ya notificado por el juzgado
                continue
            es_decreto = "fa-shield-alt" in html   # escudo verde
            es_sentencia = "fa-gavel" in html      # martillo
            if not (es_decreto or es_sentencia):
                continue
            texto = fila.inner_text()
            if es_cedula_ya_presentada(texto):     # cédula ya presentada por el estudio
                continue
            fecha = ""
            fm = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
            if fm:
                fecha = fm.group(1)

            # Filtro de RECENCIA: el "buscar-expediente" de SISFE marca el
            # expediente ENTERO como "con novedades" si tuvo cualquier
            # movimiento reciente, pero la tabla de movimientos trae TODO
            # el historial. Sin este filtro, la primera corrida procesa
            # años de decretos viejos. Se descarta lo anterior a
            # DIAS_NOVEDADES días atrás.
            if fecha:
                try:
                    fecha_dt = datetime.strptime(fecha, "%d/%m/%Y")
                    if fecha_dt < limite_fecha:
                        continue
                except ValueError:
                    pass  # fecha no parseable: no se descarta por las dudas

            novedad = texto.replace(fecha, "").strip().split("\n")[0]
            id_dec = f"dec_{id_exp}_{fecha.replace('/', '-')}_{i}"
            if registro is not None and cuij and decreto_ya_procesado(registro, cuij, id_dec):
                continue
            pendientes.append({"id": id_dec, "fecha": fecha, "novedad": novedad, "es_sentencia": es_sentencia})
        except Exception:
            continue

    if not pendientes:
        if estado is not None and cuij:
            actualizar_estado_expediente(estado, cuij, cant, ultimo)
        return decretos

    print(f"    Descargando Expediente Digital para {len(pendientes)} decreto(s)...")
    texto_completo = descargar_expediente_digital(page)
    if not texto_completo:
        print("    ⚠ No se pudo leer — se reintenta el próximo ciclo")
        return decretos

    for pnd in pendientes:
        texto_dec, fecha_propia, ambiguo = extraer_texto_decreto(texto_completo, fecha_decreto=pnd["fecha"])
        if ambiguo or not texto_dec:
            continue

        # Filtro de MERO TRÁMITE: reusa la regla que ya tenías escrita
        # (AGREGUESE, TENGASE PRESENTE, PASE A FALLO, etc. no generan
        # cédula, salvo que el decreto diga expresamente "Notifíquese").
        if cedulas.es_decreto_sin_notificacion(texto_dec, titulo=pnd["novedad"]):
            continue

        fecha_aud = hora_aud = None
        am = re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s*(?:a\s+las\s+)?(\d{1,2}[:.]\d{2})\s*(?:hs|horas)', texto_dec, re.I)
        if am:
            fecha_aud = am.group(1)
            hora_aud = am.group(2).replace(".", ":") + " hs."
        decretos.append({
            "id": pnd["id"], "fecha": pnd["fecha"],
            "fecha_decreto_texto": fecha_propia or pnd["fecha"],
            "novedad": pnd["novedad"], "texto": texto_dec,
            "es_sentencia": pnd["es_sentencia"],
            "fecha_audiencia": fecha_aud, "hora_audiencia": hora_aud,
        })

    if estado is not None and cuij:
        actualizar_estado_expediente(estado, cuij, cant, ultimo)
    return decretos


def obtener_partes_expediente(page, id_exp):
    partes = []
    try:
        page.goto(SISFE_PARTES.format(id=id_exp))
        page.wait_for_timeout(2500)
        filas = page.locator("table tbody tr")
        for i in range(filas.count()):
            celdas = filas.nth(i).locator("td")
            if celdas.count() >= 3:
                caracter = celdas.nth(1).inner_text().strip()
                nombre = re.sub(r'\s*\([^)]*\)\s*$', '', celdas.nth(2).inner_text().strip()).strip()
                if nombre:
                    partes.append({"nombre": nombre, "domicilio": "", "rol": caracter.lower()})
    except Exception as e:
        print(f"    No se pudieron leer las partes: {type(e).__name__}")
    return partes


# ============================================================
#  DATOS DEL EXPEDIENTE + GENERACIÓN DE CÉDULAS
# ============================================================
def procesar_expediente(page, exp, registro, estado):
    id_exp = exp["id_sisfe"]
    cuij = exp["cuij"]
    if not id_exp:
        print(f"  ⚠ {cuij}: sin id de SISFE, se omite")
        return

    page.goto(SISFE_DETALLE.format(id=id_exp))
    page.wait_for_timeout(2500)
    body = page.locator("body").inner_text()

    caratula = ""
    cm = re.search(r'([A-ZÁÉÍÓÚÑ ,\.]+C/[A-ZÁÉÍÓÚÑ ,\.]+S/[A-ZÁÉÍÓÚÑ ]+)', body)
    if cm:
        caratula = cm.group(1).strip()
    radicado = ""
    jm = re.search(r'Radicado en:\s*(.+)', body)
    if jm:
        radicado = jm.group(1).strip()

    decretos = obtener_decretos_nuevos(page, id_exp, registro, cuij, estado)
    if not decretos:
        return
    partes = obtener_partes_expediente(page, id_exp)

    for dec in decretos:
        # A quién notificar (regla de cedulas.py) + domicilio conocido
        destinatarios_partes = cedulas.determinar_destinatarios(dec["texto"], partes) if partes else []

        # Filtro de CAJAS: solo van en auto regulatorio de honorarios o
        # sentencia homologatoria (regla que ya existía en cedulas.py,
        # nunca se estaba llamando desde acá).
        va_a_cajas = cedulas.notifica_a_cajas(dec["texto"], dec.get("novedad", ""))
        if not va_a_cajas:
            destinatarios_partes = [
                pt for pt in destinatarios_partes if not cedulas.es_caja(pt["nombre"])
            ]

        destinatarios = []
        for pt in destinatarios_partes:
            dom = ""
            try:
                dom = cedulas.domicilio_para_demandada(caratula) or ""
            except Exception:
                dom = ""
            destinatarios.append({"nombre": pt["nombre"], "domicilio": dom})
        if not destinatarios:
            destinatarios = [{"nombre": "", "domicilio": ""}]  # a completar

        # No se genera el PDF todavía: queda como PENDIENTE con el texto
        # completo y una sugerencia de tipo (por tus reglas), para que
        # el abogado elija el tipo definitivo desde el dashboard.
        tipo_sugerido = generar_cedula.clasificar_por_reglas(dec["texto"], dec.get("novedad", ""))
        pendiente = {
            "id": dec["id"],
            "caratula": caratula, "cuij": cuij, "radicado": radicado,
            "ciudad": "Rosario",
            "fecha_decreto": dec["fecha_decreto_texto"],
            "texto_decreto": dec["texto"], "novedad": dec["novedad"],
            "destinatarios": destinatarios,
            "fecha_audiencia": dec.get("fecha_audiencia") or "",
            "hora_audiencia": dec.get("hora_audiencia") or "",
            "tipo_sugerido": tipo_sugerido,
        }
        try:
            estado.agregar_pendiente(pendiente)
            marcar_como_procesado(registro, cuij, dec["id"], [])
            print(f"    → Pendiente de clasificar: {dec['novedad'][:50]} (sugerido: {tipo_sugerido})")
        except Exception as e:
            print(f"    ⚠ Error registrando pendiente: {type(e).__name__}: {e}")


# ============================================================
#  CICLO PRINCIPAL
# ============================================================
def ciclo(usar_chrome=True):
    registro = cargar_registro()
    estado = cargar_estado()
    with sync_playwright() as p:
        ctx = abrir_sisfe(p, usar_chrome=usar_chrome)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            print("  Ingresando a SISFE…")
            login_sisfe(page)
            expedientes = obtener_expedientes(page)
            for exp in expedientes:
                print(f"\n  Expediente {exp['cuij']}")
                try:
                    procesar_expediente(page, exp, registro, estado)
                except Exception as e:
                    print(f"    ⚠ Error: {type(e).__name__}: {e}")
        finally:
            guardar_registro(registro)
            guardar_estado(estado)
            ctx.close()
    print("\n  ✓ Ciclo terminado. Revisá el dashboard.")


if __name__ == "__main__":
    import sys as _sys
    import time as _time
    from datetime import datetime as _dt
    from config import INTERVALO_MINUTOS, HORARIO_INICIO, HORARIO_FIN, DIAS_HABILES

    modo_continuo = "--una-vez" not in _sys.argv

    if not modo_continuo:
        ciclo()
    else:
        print(f"  Modo continuo: revisa cada {INTERVALO_MINUTOS} min, de "
              f"{HORARIO_INICIO} a {HORARIO_FIN}, días hábiles (lun-vie).")
        print("  La primera vez pide login (como siempre); después, mientras la\n"
              "  sesión de SISFE no expire, revisa solo — sin pedirte nada.")
        print("  Para detenerlo: Ctrl+C en esta ventana.\n")
        try:
            while True:
                ahora = _dt.now()
                en_horario = (
                    ahora.weekday() in DIAS_HABILES
                    and HORARIO_INICIO <= ahora.strftime("%H:%M") <= HORARIO_FIN
                )
                if en_horario:
                    try:
                        ciclo()
                    except Exception as e:
                        print(f"  ⚠ Error en el ciclo: {type(e).__name__}: {e}")
                else:
                    print(f"  Fuera de horario ({ahora.strftime('%H:%M')}) — esperando...")
                _time.sleep(INTERVALO_MINUTOS * 60)
        except KeyboardInterrupt:
            print("\n  Detenido.")
