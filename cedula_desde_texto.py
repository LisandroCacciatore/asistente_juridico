# -*- coding: utf-8 -*-
# ============================================================
#  CEDULA_DESDE_TEXTO.PY — Reglas de la skill "cedula-sisfe"
#  portadas al repo (unificación: un solo motor de cédulas).
# ------------------------------------------------------------
#  La skill de Claude generaba cédulas a partir de un DECRETO o
#  SENTENCIA que Santiago pega a mano (sin pasar por el monitor
#  de SISFE). El repo ya genera los PDF (cedulas_pdf.py) y
#  clasifica por reglas (cedulas.py / generar_cedula.py). Este
#  módulo aporta lo que faltaba:
#
#    1. Detección de SENTENCIA y su recorte para la cédula
#       (encabezado + […] + parte resolutiva — nunca transcribir
#       una sentencia completa en una cédula).
#    2. Parseo del texto pegado: carátula, CUIJ, fecha, juzgado.
#    3. Formato de nombre de archivo preferido por Santiago:
#       "Cédula a {DESTINATARIO} decreto fecha {DD-MM-AA}.pdf".
#
#  Uso (flujo del secretario):
#    from cedula_desde_texto import (
#        es_sentencia, recortar_sentencia, extraer_caratula,
#        extraer_cuij, extraer_fecha_decreto, nombre_archivo_santiago,
#    )
#
#  Las PARTES destinatarias no salen de este módulo: las lee el
#  motor Playwright del repo (SISFE) o las pega Santiago.
# ============================================================

import os
import re

# Meses en español (misma base que extraccion_decretos.py)
MESES_NOMBRE = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}

_PATRON_CUIJ = re.compile(r"\b21-\d{8}-\d\b")
_PATRON_CARATULA = re.compile(r"^\s*([^\n]{0,160}?)\s+[Cc]/[^\n]*?[Ss]/", re.M)
# Fecha tipo "ROSARIO, 04 de Agosto de 2026" o "RAFAELA, 22 de julio de 2026"
_PATRON_FECHA = re.compile(
    r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+de\s+(\d{4})"
)
_PATRON_SENTENCIA = re.compile(
    r"\bY\s+VISTOS\b.*?\bCONSIDERANDO\b", re.S | re.I
)
_PATRON_RESOLUTIVA = re.compile(
    r"(?:Por\s+(?:ello|lo\s+expuesto|todo\s+lo\s+expuesto|los\s+fundamentos)[^.]*?,\s*)?"
    r"(?:FALLO|RESUELVO|SE\s+RESUELVE)\s*:",
    re.S | re.I,
)


# ============================================================
#  1. Sentencias: detección y recorte
# ============================================================

def es_sentencia(texto):
    """True si el texto pegado es una sentencia/resolución de fondo y NO
    un decreto común. Señales: Y VISTOS + CONSIDERANDO + parte resolutiva
    (FALLO/RESUELVO/SE RESUELVE), o relato (DE LOS QUE RESULTA) con
    condena, o texto muy largo con estructura de sentencia."""
    if not texto:
        return False
    t = texto
    tiene_vistos = bool(re.search(r"\bY\s+VISTOS\b", t, re.I))
    tiene_considerando = bool(re.search(r"\bCONSIDERANDO\b", t, re.I))
    tiene_resolutiva = bool(re.search(
        r"\b(FALLO|RESUELVO|SE\s+RESUELVE)\s*:", t, re.I))
    if tiene_vistos and tiene_considerando and tiene_resolutiva:
        return True
    if "DE LOS QUE RESULTA" in t.upper() and tiene_resolutiva:
        return True
    # Texto muy largo (> ~3500 caracteres) con estructura de resolución
    if len(t) > 3500 and tiene_considerando and tiene_resolutiva:
        return True
    return False


def recortar_sentencia(texto):
    """Arma el texto a transcribir en la cédula cuando es sentencia:
    encabezado + párrafo '[…]' + parte resolutiva completa. Nada más.
    Devuelve el texto recortado, o el texto original si no parece
    sentencia (por las dudas, no se toca)."""
    if not es_sentencia(texto):
        return texto

    t = texto.strip()

    # --- Parte resolutiva: desde la frase de cierre de considerandos ---
    m = _PATRON_RESOLUTIVA.search(t)
    if not m:
        # sin marca clara: devolver todo (no arriesgar a cortar mal)
        return t
    inicio_resolutiva = m.start()
    resolutiva = t[inicio_resolutiva:].strip()
    # limpiar saltos de línea rotos dentro de la resolutiva
    resolutiva = re.sub(r"(?<![.!?])\n+", " ", resolutiva)
    resolutiva = re.sub(r"[ \t]+", " ", resolutiva)

    # --- Encabezado: desde el inicio hasta antes de la resolutiva ---
    encabezado = t[:inicio_resolutiva].strip()
    # El encabezado útil es solo la apertura de autos (Y VISTOS + carátula +
    # juzgado). Se corta donde empieza el relato ("DE LOS QUE RESULTA") o,
    # si no hay relato, donde empieza el "CONSIDERANDO". El que aparezca
    # primero gana (el DQR siempre precede a los considerandos).
    cortes = []
    m_dqr = re.search(r"\bDE\s+LOS\s+QUE\s+RESULTA\b", encabezado, re.I)
    if m_dqr:
        cortes.append(m_dqr.start())
    m_cons = re.search(r"\bCONSIDERANDO\b", encabezado, re.I)
    if m_cons:
        cortes.append(m_cons.start())
    if cortes:
        encabezado = encabezado[: min(cortes)].strip()
    encabezado = re.sub(r"\s+", " ", encabezado)

    return f"{encabezado}\n\n[…]\n\n{resolutiva}"


# ============================================================
#  2. Parseo del texto pegado
# ============================================================

def extraer_caratula(texto):
    """Carátula con formato 'ACTOR C/ DEMANDADO S/ OBJETO'. Primero busca
    la que va entre comillas ('caratulados: "X C/ Y S/ Z"'), que es como
    aparece en los decretos/sentencias reales; si no, la primera línea con
    el patrón C/ ... S/ recortando prefijos tipo 'Y VISTOS:'. Devuelve ''
    si no la encuentra."""
    # 1) Entre comillas (formato real de los autos)
    for m in re.finditer(r'"([^"]{5,240})"', texto):
        candidato = m.group(1).strip()
        if re.search(r"\s+[Cc]/\s+", candidato) and re.search(r"\s+[Ss]/\s+", candidato):
            return _limpiar_caratula(candidato)
    # 2) Primera línea con el patrón, sin prefijos de autos
    for linea in texto.splitlines():
        if re.search(r"\s+[Cc]/\s+", linea) and re.search(r"\s+[Ss]/\s+", linea):
            return _limpiar_caratula(linea.strip())
    return ""


def _limpiar_caratula(car):
    car = _PATRON_CUIJ.sub("", car).strip()
    car = re.sub(r"\s*[-–—]\s*[A-ZÁÉÍÓÚÑ ]*SUMARISIMO.*$", "", car, flags=re.I).strip()
    # quitar prefijos tipo "Y VISTOS:", "Estos autos caratulados", etc.
    car = re.sub(r'^.*?(?:caratulados?|autos)\s*[":]\s*', "", car, flags=re.I).strip()
    car = car.strip('"').strip()
    car = re.sub(r"\s+", " ", car).strip()
    return car
    


def extraer_cuij(texto):
    """Primer CUIJ con formato 21-XXXXXXXX-X."""
    m = _PATRON_CUIJ.search(texto)
    return m.group(0) if m else ""


def extraer_fecha_decreto(texto):
    """Fecha del encabezado ('ROSARIO, 04 de Agosto de 2026') → '04/08/2026'.
    Busca el patrón '<día> de <mes> de <año>' en las primeras líneas.
    Devuelve '' si no la encuentra."""
    primeras = "\n".join(texto.splitlines()[:15])
    m = _PATRON_FECHA.search(primeras)
    if not m:
        return ""
    dia, mes_nombre, anio = m.group(1), m.group(2).lower(), m.group(3)
    mes_num = MESES_NOMBRE.get(mes_nombre)
    if not mes_num:
        return ""
    return f"{int(dia):02d}/{mes_num:02d}/{anio}"


def extraer_juzgado(texto):
    """Línea tipo 'JUZGADO DE 1RA. INST. LABORAL 2DA. NOM.' de RAFAELA,
    o 'Laboral 3ª Nom. — Rosario'. Devuelve lo que encuentre, '' si no."""
    patrones = [
        re.compile(r"JUZGADO[^\n]{0,120}", re.I),
        re.compile(r"(?:Juzg\.|Laboral|Civil|Familia)[^\n]{0,100}?Nom[^\n]{0,60}", re.I),
    ]
    for p in patrones:
        m = p.search(texto)
        if m:
            return m.group(0).strip()
    return ""


# Ciudades con juzgados en Santa Fe (para no confundir la ciudad con
# cualquier otra palabra del decreto).
CIUDADES_SF = [
    "VILLA GOBERNADOR GALVEZ", "CAÑADA DE GOMEZ", "VENADO TUERTO",
    "SAN LORENZO", "RECONQUISTA", "SUNCHALES", "ESPERANZA", "MELINCUE",
    "RAFAELA", "ROSARIO", "CASILDA", "FIRMAT", "RUFINO", "SANTA FE",
]

_FUEROS_TXT = {
    "LABORAL": r"\blaboral\b|\bdel\s+trabajo\b",
    "CIVIL": r"\bcivil\b",
    "COMERCIAL": r"\bcomercial\b",
    "CONTRACTUAL": r"\bcontractual\b",
    "FAMILIA": r"\bfamilia\b|\bfamiliar\b",
}


def extraer_ciudad(texto):
    """Ciudad de la cabecera: 'ROSARIO, 04 de Agosto de 2026', 'en la ciudad
    de RAFAELA', 'CIUDAD DE ROSARIO'. Devuelve '' si no la encuentra.

    Importa porque el encabezado de la cédula dice la ciudad del juzgado, y
    los decretos de Rafaela no son los de Rosario.
    """
    if not texto:
        return ""
    t = texto.upper()
    m = re.search(
        r"CIUDAD\s+DE\s+([A-ZÁÉÍÓÚÑÜ]+(?:\s+[A-ZÁÉÍÓÚÑÜ]+){0,2})"
        r"(?=\s*[,.\-]|\s+A\s+CARGO|\s*$)", t)
    if m and len(m.group(1).strip()) >= 4:
        return m.group(1).strip()
    for ciudad in CIUDADES_SF:
        if re.search(rf"\b{re.escape(ciudad)}\b", t):
            return ciudad
    return ""


def extraer_fuero(texto):
    """Fuero del juzgado: LABORAL / CIVIL / COMERCIAL / CONTRACTUAL / FAMILIA.

    Mira primero la línea del juzgado (donde no se confunde con citas de
    códigos) y después todo el texto. Devuelve '' si no lo encuentra, para
    que la plantilla use su valor por defecto.
    """
    if not texto:
        return ""
    for zona in (extraer_juzgado(texto) or "", texto):
        z = zona.lower()
        for fuero, patron in _FUEROS_TXT.items():
            if re.search(patron, z):
                return fuero
    return ""


# ============================================================
#  3. Formato de nombre de archivo (preferencia de Santiago)
# ============================================================

def _sanitizar(texto, largo=60):
    """Quita caracteres inválidos para nombre de archivo en Windows."""
    if not texto:
        return ""
    t = re.sub(r'[<>:"/\\|?*]', "", texto)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:largo].strip()


def nombre_archivo_santiago(destinatario, fecha_decreto):
    """'Cédula a {DESTINATARIO} decreto fecha {DD-MM-AA}.pdf'.
    fecha_decreto en formato dd/mm/aaaa → se usa como DD-MM-AA (año de 2
    dígitos, preferencia de Santiago). Si no hay fecha, se usa 'hoy'."""
    dest = _sanitizar(destinatario or "DESTINATARIO", 60)
    f = (fecha_decreto or "").replace("/", "-")
    if f:
        # '04-08-2026' -> '04-08-26'
        partes = f.split("-")
        if len(partes) == 3 and len(partes[2]) == 4:
            f = f"{partes[0]}-{partes[1]}-{partes[2][2:]}"
    else:
        f = _hoy_dd_mm_aa()
    return f"Cédula a {dest} decreto fecha {f}.pdf"


def _hoy_dd_mm_aa():
    import datetime
    return datetime.date.today().strftime("%d-%m-%y")


# ============================================================
#  Demo / prueba rápida (python cedula_desde_texto.py)
# ============================================================

if __name__ == "__main__":
    ejemplo_sentencia = """En la ciudad de Rosario, a los 4 días del mes de agosto de 2026, se reúne el Tribunal...

Y VISTOS: Estos autos caratulados "GONZALEZ c/ ART EJEMPLO S/ ACCIDENTE LABORAL" CUIJ 21-00000001-0, de trámite por ante este Juzgado...

DE LOS QUE RESULTA: Que se presenta la parte actora iniciando demanda...

CONSIDERANDO: Que corresponde analizar...

Por ello, y de conformidad con la normativa citada, FALLO: 1) Haciendo lugar a la demanda interpuesta por GONZALEZ contra ART EJEMPLO S.A., condenando a esta última a abonar la suma de PESOS... 2) Con costas a la demandada. Insértese, regístrese y hágase saber. Notifíquese."""

    print("es_sentencia:", es_sentencia(ejemplo_sentencia))
    rec = recortar_sentencia(ejemplo_sentencia)
    print("recorte OK:", "FALLO:" in rec and "[…]" in rec and "DE LOS QUE RESULTA" not in rec)
    print("--- recorte ---")
    print(rec[:300], "...")
    print("caratula:", extraer_caratula(ejemplo_sentencia))
    print("cuij:", extraer_cuij(ejemplo_sentencia))
    print("fecha:", extraer_fecha_decreto("ROSARIO, 04 de Agosto de 2026.-"))
    print("nombre:", nombre_archivo_santiago("FISCALÍA DE ESTADO PROVINCIAL", "04/08/2026"))
