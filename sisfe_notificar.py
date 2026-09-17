# -*- coding: utf-8 -*-
# ============================================================
#  SISFE_NOTIFICAR.PY — Sube la cédula FIRMADA al SISFE.
# ------------------------------------------------------------
#  Es el paso que cierra el circuito: cédula → firma (FirmAr) →
#  ACÁ. Meta Jurídico salió del circuito (SPEC D1).
#
#  USO (desde CMD):
#     python sisfe_notificar.py "ruta\a\cedula_FIRMADO.pdf" "21-04253894-6" ["CARATULA..."]
#
#  QUÉ HACE (la secuencia que dictó Santiago, 16/09/2026):
#     1) Abre el SISFE en Chrome con perfil persistente.
#     2) FRENA para que ingreses la contraseña y el reCAPTCHA (puerta humana).
#     3) Busca el expediente POR CUIJ y verifica carátula + CUIJ.
#     4) "Nueva Cédula".
#     5) Completa la Descripción genérica (por defecto, la fecha de hoy).
#     6) Adjunta el PDF firmado.
#     7) Lee las PARTES de la tabla del expediente y las tilda.
#     8) FRENA: el clic en NOTIFICAR es tuyo.
#
#  REGLA QUE NO SE ROMPE — igual que la del mail:
#     Este módulo NO notifica. Deja todo cargado y se detiene. El
#     resultado que devuelve SIEMPRE trae notificado=False. Ningún
#     camino de código toca los botones de BOTONES_FINALES.
#
#  Sobre los selectores: el portal no se puede mirar sin sesión, así
#  que cada paso intenta el camino automático y, si no lo encuentra,
#  FRENA y te pide que lo hagas a mano (nunca sigue a ciegas, nunca
#  inventa). Los que faltan confirmar están marcados ⬅ VALIDAR.
# ============================================================

import os
import re
import sys
import unicodedata
from datetime import date

# Consola Windows a prueba de Unicode (ver nota en _navegador.py).
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from _navegador import abrir_navegador, pausa_humana


# --- URLs del SISFE ------------------------------------------------
SISFE_LOGIN = "https://sisfe.justiciasantafe.gov.ar/login-matriculado"
SISFE_BUSCAR = "https://sisfe.justiciasantafe.gov.ar/buscar-expediente"
# La URL que pasó Santiago: el buscador del módulo de notificaciones
# resuelve el CUIJ en esta dirección, con un id PROPIO DEL SISFE (que
# NO es el CUIJ: 10067855763 para el CUIJ 21-04253894-6).
SISFE_NOTIF_ENTRADA = "https://sisfe.justiciasantafe.gov.ar/buscar-notificacion-expediente/{id}"
# El formulario en sí. Ya lo usaba el monitor para leer las Partes.
SISFE_NOTIF_NUEVA = "https://sisfe.justiciasantafe.gov.ar/nueva-notificacion-expediente/{id}"

# Botones que este módulo NUNCA toca. Existe para que quede a la vista
# al leer el código y para que el test lo verifique (hay un test que
# recorre el archivo y falla si alguno aparece en un clic).
BOTONES_FINALES = ("notificar", "presentar", "confirmar", "enviar")

# Los caracteres que usa el SISFE en la tabla PARTES. Sirven para
# reconocer CUÁL de todas las tablas de la pantalla es la de partes.
CARACTERES_CONOCIDOS = (
    "auxiliar de justicia", "representante", "perito", "actor",
    "demandado", "letrado", "fiscal", "defensor", "querellante",
)


# ============================================================
#  LÓGICA PURA (sin navegador — es lo que corren los tests)
# ============================================================

_RE_CUIJ = re.compile(r"\b(\d{2}-\d{8}-\d)\b")


def normalizar_cuij(texto):
    """Devuelve el CUIJ con el formato 21-04253894-6, o "" si no hay.

    Acepta el texto suelto, con espacios o sin los guiones: lo que se
    escribe a mano casi nunca viene prolijo, y comparar el CUIJ es la
    única defensa real contra notificar el expediente equivocado.
    """
    if not texto:
        return ""
    m = _RE_CUIJ.search(str(texto))
    if m:
        return m.group(1)
    digitos = re.sub(r"\D", "", str(texto))
    if len(digitos) == 11:
        return f"{digitos[:2]}-{digitos[2:10]}-{digitos[10]}"
    return ""


def _clave(texto):
    """Normaliza para comparar: sin acentos, sin puntuación, minúsculas."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^A-Za-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def verificar_expediente(cuij_esperado, caratula_esperada, cuij_portal, caratula_portal):
    """¿Es el expediente correcto? Devuelve (ok, avisos).

    El CUIJ manda: si no coincide, NO se sigue. Notificar el expediente
    equivocado no se deshace con un botón.

    La carátula en cambio AVISA, no bloquea: el portal la escribe con su
    propio criterio (recortada, con otro orden) y bloquear por eso
    trabaría casos válidos. Quien decide es el abogado, que ve el aviso.
    """
    avisos = []
    esperado = normalizar_cuij(cuij_esperado)
    portal = normalizar_cuij(cuij_portal)

    if not portal:
        return False, [
            f"No pude leer el CUIJ de la pantalla del SISFE (la cédula es de "
            f"{esperado or cuij_esperado}). No sigo: no puedo confirmar que sea el mismo expediente."
        ]
    if esperado and esperado != portal:
        return False, [
            f"El expediente abierto es {portal} y la cédula es de {esperado}. "
            "No sigo: estaría notificando el expediente equivocado."
        ]
    if caratula_esperada and caratula_portal and _clave(caratula_esperada) != _clave(caratula_portal):
        avisos.append(
            f'La carátula de la pantalla («{caratula_portal}») no coincide con la de la cédula '
            f'(«{caratula_esperada}»). El CUIJ sí coincide: revisá que sea el mismo juicio.'
        )
    return True, avisos


_RE_CODIGO = re.compile(r"\(([^)]+)\)\s*$")


def separar_codigo(parte):
    """Separa «CAJA FORENSE-ROSARIO (CF02)» en (nombre, código).

    El código entre paréntesis es la matrícula de caja: es el mismo dato
    que ya usa la skill de boletas, y es lo que hace reconocible una parte
    sin depender de cómo esté escrita.
    """
    m = _RE_CODIGO.search(str(parte or ""))
    if not m:
        return str(parte or "").strip(), ""
    return str(parte)[:m.start()].strip(), m.group(1).strip()


def leer_partes(filas):
    """Convierte las filas de la tabla PARTES en datos.

    `filas` es una lista de listas de textos (una por <tr>). La primera
    celda es el tilde: puede venir vacía (un checkbox) y por eso se
    descarta. La tabla real trae 4 columnas:
    [tildar] | Carácter | Parte | Correo Electrónico
    """
    partes = []
    for i, celdas in enumerate(filas):
        textos = [(c or "").strip() for c in (celdas or [])]
        if textos and not textos[0]:        # celda del tilde
            textos = textos[1:]
        if len(textos) < 2:
            continue
        caracter, parte_txt = textos[0], textos[1]
        correo = textos[2] if len(textos) > 2 else ""

        # Si el <tbody> no existe, entre las filas viene el encabezado:
        # se descarta, o «Carácter | Parte | Correo» quedaría como si
        # fuera una parte del expediente.
        if _clave(caracter) in ("caracter", "caracteres"):
            continue

        # Si el correo vino en la columna de la parte, la tabla no traía
        # la columna del tilde y quedó todo corrido: se acomoda.
        if "@" in parte_txt and not correo:
            correo, parte_txt, caracter = parte_txt, caracter, ""

        nombre, codigo = separar_codigo(parte_txt)
        if not (nombre or caracter):
            continue
        partes.append({
            "fila": i, "caracter": caracter, "parte": nombre,
            "codigo": codigo, "correo": correo,
        })
    return partes


def descripcion_por_defecto(fecha=None):
    """La Descripción genérica que pidió Santiago: la fecha."""
    f = fecha or date.today()
    if isinstance(f, str):
        return f
    return f.strftime("%d/%m/%Y")


def resumen_partes(partes, tildadas=None):
    """Texto corto para mostrar/avisar (ej. en la pausa humana)."""
    if not partes:
        return "  (no pude leer la tabla de partes — tildalas a mano)"
    lineas = []
    for p in partes:
        marca = "☑" if (tildadas is None or p["fila"] in tildadas) else "☐"
        cod = f" ({p['codigo']})" if p["codigo"] else ""
        mail = f" → {p['correo']}" if p["correo"] else ""
        lineas.append(f"  {marca} {p['caracter']}: {p['parte']}{cod}{mail}")
    return "\n".join(lineas)


# ============================================================
#  PÁGINA (Playwright) — todo con salida humana si no encuentra
# ============================================================

def _tabla_de_partes(page):
    """Cuál de las tablas de la pantalla es la de Partes.

    Primero por el encabezado (Carácter + Parte); si no, por los
    caracteres que usa el SISFE. Se prueban las dos porque no sabemos
    si el encabezado dice exactamente eso (⬅ VALIDAR).
    """
    tablas = page.locator("table")
    for i in range(tablas.count()):
        try:
            txt = _clave(tablas.nth(i).inner_text())
        except Exception:
            continue
        if "caracter" in txt and "parte" in txt:
            return tablas.nth(i)
    for i in range(tablas.count()):
        try:
            txt = _clave(tablas.nth(i).inner_text())
        except Exception:
            continue
        if any(c in txt for c in CARACTERES_CONOCIDOS):
            return tablas.nth(i)
    return None


def _leer_partes_de_tabla(tabla):
    """Lee las filas de la tabla de partes (texto de cada celda)."""
    filas = tabla.locator("tbody tr")
    if filas.count() == 0:
        filas = tabla.locator("tr")
    crudas = []
    for i in range(filas.count()):
        try:
            celdas = filas.nth(i).locator("td")
            n = celdas.count()
            textos = [celdas.nth(j).inner_text() for j in range(n)] if n \
                else [filas.nth(i).inner_text()]
        except Exception:
            textos = []
        crudas.append(textos)
    return leer_partes(crudas)


def _tildar(tabla, parte):
    """Tilda una fila: por su checkbox y, si no hay, por la celda."""
    try:
        fila = tabla.locator("tbody tr").nth(parte["fila"])
        if fila.count() == 0:
            fila = tabla.locator("tr").nth(parte["fila"])
        casilla = fila.locator('input[type="checkbox"]')
        if casilla.count():
            casilla.first.check(timeout=5000)
            return True
        fila.locator("td").first.click(timeout=5000)
        return True
    except Exception:
        return False


def _completar_descripcion(page, descripcion):
    """Escribe la Descripción genérica. True si la pudo escribir."""
    lugares = [
        lambda: page.get_by_label(re.compile("descripci", re.I)).first,
        lambda: page.locator('textarea[name*="descrip" i]').first,
        lambda: page.locator('input[name*="descrip" i]').first,
        lambda: page.locator("textarea").first,
    ]
    for buscar in lugares:
        try:
            campo = buscar()
            if campo.count() == 0:
                continue
            campo.fill(descripcion, timeout=6000)
            return True
        except Exception:
            continue
    return False


def _adjuntar(page, ruta_pdf):
    """Adjunta el PDF firmado. True si lo logró.

    Dos caminos, y en ese orden: el <input type="file"> real (como en
    Meta Jurídico, que está confirmado) y el botón que abre el diálogo
    de Windows. Si ninguno anda, el que llama ofrece hacerlo a mano.
    """
    try:
        entrada = page.locator('input[type="file"]')
        if entrada.count():
            entrada.first.set_input_files(ruta_pdf, timeout=15000)
            return True
    except Exception:
        pass
    try:
        with page.expect_file_chooser(timeout=8000) as fc:
            page.get_by_role(
                "button", name=re.compile("adjunt|archivo|seleccionar|cargar|subir", re.I)
            ).first.click(timeout=6000)
        fc.value.set_files(ruta_pdf)
        return True
    except Exception:
        return False


def _leer_encabezado(page):
    """Carátula y CUIJ que muestra la pantalla, para verificar el expediente."""
    try:
        body = page.locator("body").inner_text()
    except Exception:
        return "", ""
    cuij = ""
    m = _RE_CUIJ.search(body)
    if m:
        cuij = m.group(1)
    caratula = ""
    m2 = re.search(r"([A-ZÁÉÍÓÚÑ ,\.]{3,}C/[A-ZÁÉÍÓÚÑ ,\.]{3,}S/[A-ZÁÉÍÓÚÑ ]+)", body)
    if m2:
        caratula = m2.group(1).strip()
    return caratula, cuij


def cargar_en_pagina(page, ruta_pdf, descripcion, elegir=None, pausar=None):
    """Completa el formulario de Nueva Cédula. NO navega y NO notifica.

    Está separado de `subir()` a propósito: así se puede probar contra
    una página de mentira (los tests lo hacen) sin tocar el portal.

    elegir : callback elegir(partes) -> lista de índices de fila a tildar.
             Por defecto, todas (y el abogado destilda en la pantalla).
    """
    pausar = pausar or pausa_humana
    resultado = {"descripcion": descripcion, "descripcion_ok": False,
                 "adjuntado": False, "partes": [], "tildadas": [], "avisos": []}

    if _completar_descripcion(page, descripcion):
        resultado["descripcion_ok"] = True
    else:
        resultado["avisos"].append(
            "No encontré el campo de Descripción genérica: completalo a mano "
            f'con «{descripcion}».'
        )

    if _adjuntar(page, ruta_pdf):
        resultado["adjuntado"] = True
    else:
        resultado["avisos"].append("No pude adjuntar el PDF solo.")

    tabla = _tabla_de_partes(page)
    if tabla is None:
        resultado["avisos"].append(
            "No encontré la tabla de Partes en esta pantalla."
        )
        elegidas = []
    else:
        partes = _leer_partes_de_tabla(tabla)
        resultado["partes"] = partes
        if not partes:
            resultado["avisos"].append("La tabla de Partes vino vacía.")
        elegidas = elegir(partes) if elegir else [p["fila"] for p in partes]
        for p in partes:
            if p["fila"] in elegidas:
                if _tildar(tabla, p):
                    resultado["tildadas"].append(p["fila"])
                else:
                    resultado["avisos"].append(
                        f"No pude tildar «{p['parte']}»: tildala a mano."
                    )

        # Verificación: si la tabla tiene casillas reales, el número de
        # tildadas tiene que dar. Si no da, se avisa (el abogado lo ve
        # antes de notificar) en vez de seguir como si nada.
        try:
            casillas = tabla.locator('input[type="checkbox"]').count()
            if casillas:
                marcadas = tabla.locator('input[type="checkbox"]:checked').count()
                if marcadas != len(elegidas):
                    resultado["avisos"].append(
                        f"Quedaron {marcadas} partes tildadas y esperaba {len(elegidas)}: "
                        "revisá los tildes antes de notificar."
                    )
        except Exception:
            pass

    print(f"  ✓ Descripción: {descripcion}" if resultado["descripcion_ok"]
          else "  ⚠ Descripción: a mano")
    print(f"  ✓ PDF adjuntado" if resultado["adjuntado"] else "  ⚠ PDF: a subir a mano")
    print("  Partes del expediente:")
    print(resumen_partes(resultado["partes"], set(resultado["tildadas"])))
    for a in resultado["avisos"]:
        print(f"  ⚠ {a}")
    return resultado


# ============================================================
#  FLUJO COMPLETO (abre el navegador)
# ============================================================

def _entrar(page, pausar):
    """Deja la sesión de SISFE iniciada. True si quedó adentro."""
    page.goto(SISFE_BUSCAR)
    page.wait_for_timeout(1800)
    if "login" not in page.url and page.locator("#localidad, table").count() > 0:
        print("  ✓ Sesión de SISFE activa (perfil de Chrome)")
        return True

    page.goto(SISFE_LOGIN)
    page.wait_for_timeout(1200)
    try:
        matricula = config_matricula()
        if matricula:
            page.locator("#matricula").fill(matricula)
            print(f"  ✓ Matrícula precargada ({matricula})")
    except Exception:
        print("  ⚠ No pude precargar la matrícula — completala a mano.")
    pausar("Ingresá tu CONTRASEÑA de SISFE, resolvé el reCAPTCHA y hacé clic en INGRESAR.")

    page.wait_for_timeout(1200)
    if "login" in page.url:
        print("  ✗ Todavía estás en la pantalla de login — no sigo.")
        return False
    print("  ✓ Adentro del SISFE")
    return True


def config_matricula():
    """La matrícula de esta máquina (config.py), si está."""
    try:
        from config import SISFE_USUARIO
        return SISFE_USUARIO
    except Exception:
        return ""


def _id_del_expediente(page, cuij, pausar):
    """El id interno del SISFE para ese CUIJ (o "" si no lo consiguió).

    El id NO se deduce del CUIJ: se busca. Primero por el buscador y, si
    no aparece, se le pide a la persona que deje el expediente abierto en
    la pantalla y se lee de la URL.
    """
    try:
        page.goto(SISFE_BUSCAR)
        page.wait_for_timeout(2500)
        campo = None
        for loc in (page.locator("#cuij"), page.locator('input[name*="cuij" i]'),
                    page.get_by_label(re.compile("cuij", re.I)).first):
            try:
                if loc.count():
                    campo = loc.first
                    break
            except Exception:
                continue
        if campo is not None:
            campo.fill(cuij, timeout=6000)
            try:
                page.get_by_role(
                    "button", name=re.compile("Efectuar la búsqueda", re.I)
                ).click(timeout=6000)
            except Exception:
                campo.press("Enter")
            page.wait_for_timeout(3500)
            filas = page.locator("table tbody tr")
            for i in range(min(filas.count(), 20)):
                try:
                    href = filas.nth(i).locator("a").first.get_attribute("href") or ""
                except Exception:
                    href = ""
                m = re.search(r"/(\d{8,})", href)
                if m:
                    print(f"  ✓ Expediente encontrado: id SISFE {m.group(1)}")
                    return m.group(1)
    except Exception as e:
        print(f"  ⚠ La búsqueda por CUIJ no salió sola ({type(e).__name__}).")

    pausar(
        f"No pude encontrar el expediente {cuij} solo.\n"
        "  Buscalo en el SISFE y dejá abierta la pantalla del expediente\n"
        "  (la dirección tiene que ser .../expediente/<número>)."
    )
    m = re.search(r"/(\d{8,})", page.url or "")
    if m:
        print(f"  ✓ id SISFE leído de la pantalla: {m.group(1)}")
        return m.group(1)
    return ""


def subir(ruta_pdf, cuij, caratula=None, descripcion=None, usar_chrome=True,
          pausar=None, elegir=None, perfil=None):
    """Sube la cédula firmada al SISFE y deja todo listo para notificar.

    Devuelve un dict con el detalle. `notificado` SIEMPRE es False: el
    clic final es del abogado.

    `perfil` es la carpeta del perfil de Chrome de la persona que actúa
    (SPEC D24): la sesión del SISFE es personal, no de la máquina.
    """
    pausar = pausar or pausa_humana
    devolver = {
        "ok": False, "cuij": normalizar_cuij(cuij), "caratula_portal": "",
        "id_sisfe": "", "descripcion": descripcion or descripcion_por_defecto(),
        "adjuntado": False, "partes": [], "tildadas": [], "avisos": [],
        "notificado": False,
    }

    if not os.path.isfile(ruta_pdf):
        devolver["avisos"].append(f"No encuentro el PDF firmado: {ruta_pdf}")
        return devolver
    ruta_pdf = os.path.abspath(ruta_pdf)
    cuij = normalizar_cuij(cuij) or (cuij or "").strip()

    print("\n  Subiendo al SISFE:")
    print(f"    Archivo     : {os.path.basename(ruta_pdf)}")
    print(f"    CUIJ        : {cuij or '(sin CUIJ)'}")
    print(f"    Carátula    : {caratula or '(no provista)'}")
    print(f"    Descripción : {devolver['descripcion']}")

    with abrir_navegador(usar_chrome=usar_chrome, perfil=perfil) as (ctx, page):
        if not _entrar(page, pausar):
            devolver["avisos"].append("No se inició la sesión del SISFE.")
            return devolver

        id_exp = _id_del_expediente(page, cuij, pausar)
        if not id_exp:
            devolver["avisos"].append(
                "No conseguí el id del expediente en el SISFE (hace falta para notificar)."
            )
            return devolver
        devolver["id_sisfe"] = id_exp

        page.goto(SISFE_NOTIF_ENTRADA.format(id=id_exp))
        page.wait_for_timeout(2500)
        caratula_portal, cuij_portal = _leer_encabezado(page)
        devolver["caratula_portal"] = caratula_portal

        ok, avisos = verificar_expediente(cuij, caratula, cuij_portal, caratula_portal)
        devolver["avisos"].extend(avisos)
        for a in avisos:
            print(f"  ⚠ {a}")
        if not ok:
            return devolver

        # "Nueva Cédula": por el botón y, si no está, entrando directo al
        # formulario (la URL ya la usa el monitor para leer las partes).
        try:
            page.get_by_role(
                "button", name=re.compile("nueva c[eé]dula", re.I)
            ).first.click(timeout=8000)
            page.wait_for_timeout(2500)
        except Exception:
            print("  ⚠ No encontré el botón «Nueva Cédula» — entro por la dirección.")
            page.goto(SISFE_NOTIF_NUEVA.format(id=id_exp))
            page.wait_for_timeout(2500)

        resultado = cargar_en_pagina(
            page, ruta_pdf, devolver["descripcion"], elegir=elegir, pausar=pausar
        )
        for clave in ("descripcion", "adjuntado", "partes", "tildadas"):
            devolver[clave] = resultado[clave]
        devolver["avisos"].extend(resultado["avisos"])

        # --- Puerta humana final -------------------------------------
        # Acá se termina lo automático. El SISFE notifica cuando VOS
        # apretás NOTIFICAR: este módulo no lo hace ni lo va a hacer.
        pausar(
            "Todo cargado en la Nueva Cédula del SISFE:\n"
            f"  · Descripción: {devolver['descripcion']}\n"
            f"  · Cédula firmada: {os.path.basename(ruta_pdf)}\n"
            f"  · Partes tildadas: {len(devolver['tildadas'])} de {len(devolver['partes'])}\n"
            "  Revisá la pantalla y apretá vos NOTIFICAR.\n"
            "  Cuando el SISFE te confirme la notificación, volvé acá."
        )
        devolver["ok"] = True
        print("\n  ✓ Cargado y esperando tu clic en NOTIFICAR.\n")
        return devolver


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('  Uso: python sisfe_notificar.py "ruta\\a\\cedula_FIRMADO.pdf" "21-04253894-6" ["CARATULA"]')
        sys.exit(1)
    r = subir(sys.argv[1], sys.argv[2], caratula=(sys.argv[3] if len(sys.argv) > 3 else None))
    if not r["ok"]:
        print("  ✗ No quedó listo: " + " ".join(r["avisos"]))
        sys.exit(2)
