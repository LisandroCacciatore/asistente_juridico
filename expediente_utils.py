# ============================================================
#  EXPEDIENTE_UTILS.PY - Utilidades para leer/clasificar expedientes
# ============================================================
#
#  Estas funciones NO dependen de Selenium: solo de texto ya obtenido
#  (de la tabla de movimientos, del "Radicado en:", de la carátula, etc.)
#  Por eso las usa tanto monitor.py (con el navegador) como la skill de
#  generación de cédulas desde un expediente pegado/subido en el chat
#  (sin navegador).

import os
import re

from config import RUTA_ESTUDIO, RAMAS, CLASIFICACION

ORDINALES = {
    "1ra": "1", "1era": "1", "1": "1", "primera": "1",
    "2da": "2", "2": "2", "segunda": "2",
    "3ra": "3", "3era": "3", "3": "3", "tercera": "3",
    "4ta": "4", "4": "4", "cuarta": "4",
    "5ta": "5", "5": "5", "quinta": "5",
    "6ta": "6", "6": "6", "sexta": "6",
    "7ma": "7", "7": "7", "septima": "7",
    "8va": "8", "8": "8", "octava": "8",
    "9na": "9", "9": "9", "novena": "9",
    "10ma": "10", "10": "10", "decima": "10",
    "11ra": "11", "11va": "11", "11": "11",
    "12da": "12", "12va": "12", "12": "12",
    "13ra": "13", "13va": "13", "13": "13",
    "14ta": "14", "14va": "14", "14": "14",
    "15ta": "15", "15va": "15", "15": "15",
    "16ta": "16", "16va": "16", "16": "16",
    "17ma": "17", "17va": "17", "17": "17",
    "18va": "18", "18": "18",
    "19na": "19", "19va": "19", "19": "19",
    "20ma": "20", "20va": "20", "20": "20",
    # Variantes que SISFE escribe de otras formas (vistas en expedientes
    # reales de Civil/Familia). Si falta la del ordinal que usa el portal,
    # el juzgado no se encuentra y la cédula sale sin juez ni secretario.
    "11ma": "11", "11na": "11",
    "12ma": "12", "12na": "12",
    "13ma": "13", "13na": "13",
    "14ma": "14", "14na": "14",
    "15ma": "15", "15na": "15",
    "16ma": "16", "16na": "16",
    "17na": "17", "17ta": "17",
    "18ma": "18", "18na": "18",
    "19ma": "19", "19ta": "19",
    "20na": "20", "20ta": "20",
}


def _juzgados():
    """Juez y secretario por juzgado.

    Los 44 juzgados de Rosario viven en skills/juzgados_rosario.json. Si
    config.JUZGADOS trae datos, mandan esos (una máquina puede querer pisar
    alguno); si está vacío, se lee el JSON. Antes había que copiar la lista a
    mano en config.py y las dos copias se podían desincronizar.
    """
    import json
    import os

    from config import JUZGADOS as _de_config

    if _de_config:
        return _de_config
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "skills", "juzgados_rosario.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f"    ⚠ No pude leer skills/juzgados_rosario.json ({e})")
        return {}


def datos_del_juzgado(texto_radicado):
    """
    Del campo 'Radicado en:' de SISFE (o de la cabecera del expediente
    digital) deduce el fuero y la nominación, y busca juez/secretario
    en el diccionario JUZGADOS de config.
    Ej: 'Juzg. 1ra. Inst. Laboral 5ta. Nom. SEC.UNICA' -> LABORAL 5
    Devuelve (nominacion, juez, secretario, cargo_juez, cargo_secretario)
    """
    JUZGADOS = _juzgados()

    if not texto_radicado:
        return "", "", "", "JUEZ", "SECRETARIO"

    t = texto_radicado.lower()

    # Fuero
    if "laboral" in t:
        fuero = "LABORAL"
    elif "civil" in t:
        fuero = "CIVIL"
    elif "familia" in t:
        fuero = "FAMILIA"
    else:
        fuero = ""

    # Nominación: el ordinal que aparece justo antes de "nom"
    # Incluye 'ª' (ordinal femenino, ej. "8ª Nom.") además de 'º'/'°', y
    # tolera punto(s) y espacio(s) en cualquier orden entre el ordinal y
    # "nom" — confirmado con texto real de SISFE: "Laboral 8ª . Nom."
    # (el punto va DESPUÉS del espacio, no antes).
    nominacion = ""
    m = re.search(r'([\wºª°]+)[\.\s]*nom', t)
    if m:
        ord_txt = m.group(1).replace("º", "").replace("ª", "").replace("°", "").strip()
        nominacion = ORDINALES.get(ord_txt, ord_txt)
    else:
        # Familia usa otro formato: "N° 8" en vez de "8ª Nom." — confirmado
        # con casos reales ("Juzg.Unipersonal de Familia N° 8 - ROSARIO").
        # El \b del principio evita que "en 8 días" o "Unipersonal" cuenten
        # como nominación; y el [°º]? opcional cubre el portal cuando escribe
        # "N 8" sin el símbolo de grado.
        m2 = re.search(r'\bn\s*[°º]?\s*(\d+)', t)
        if m2:
            nominacion = m2.group(1)

    clave = f"{fuero} {nominacion}".strip()
    datos = JUZGADOS.get(clave)
    if datos:
        return (
            nominacion,
            datos.get("juez", ""),
            datos.get("secretario", ""),
            datos.get("cargo_juez", "JUEZ"),
            datos.get("cargo_secretario", "SECRETARIO"),
        )

    if clave and fuero:
        print(f"    ⚠ Juzgado '{clave}' no está en skills/juzgados_rosario.json — juez/secretario en blanco")
    return nominacion, "", "", "JUEZ", "SECRETARIO"


def clasificar_expediente(caratula, juzgado=""):
    texto = (caratula + " " + juzgado).lower()
    for rama, palabras_clave in CLASIFICACION.items():
        for palabra in palabras_clave:
            if palabra.lower() in texto:
                return rama
    return None


def encontrar_carpeta_expediente(cuij, caratula, juzgado=""):
    """
    Busca la subcarpeta 'cédula <CUIJ>' dentro de la carpeta del cliente.
    Si no la encuentra, guarda en la raíz de ESTUDIO JURIDICO.
    """
    apellido = ""
    match = re.match(r'^(.+?)\s+[Cc]/\s*', caratula)
    if match:
        partes_nombre = match.group(1).strip().split()
        apellido = partes_nombre[0].lower() if partes_nombre else ""

    cuij_limpio = cuij.replace("-", "").replace(" ", "")

    # 1) Buscar carpeta con el CUIJ en todas las ramas
    for rama_nombre, rama_carpeta in RAMAS.items():
        ruta_rama = os.path.join(RUTA_ESTUDIO, rama_carpeta)
        if not os.path.exists(ruta_rama):
            continue
        for cliente_dir in os.listdir(ruta_rama):
            ruta_cliente = os.path.join(ruta_rama, cliente_dir)
            if not os.path.isdir(ruta_cliente):
                continue
            for sub in os.listdir(ruta_cliente):
                sub_limpio = sub.replace("-", "").replace(" ", "").replace("cédula", "").replace("cedula", "")
                if cuij_limpio in sub_limpio:
                    return os.path.join(ruta_cliente, sub)

    # 2) Clasificar por carátula y buscar carpeta del cliente
    rama = clasificar_expediente(caratula, juzgado)
    if rama and rama in RAMAS:
        ruta_rama = os.path.join(RUTA_ESTUDIO, RAMAS[rama])
        if os.path.exists(ruta_rama) and apellido:
            for cliente_dir in os.listdir(ruta_rama):
                if apellido in cliente_dir.lower():
                    ruta_cuij = os.path.join(ruta_rama, cliente_dir, f"cédula {cuij}")
                    os.makedirs(ruta_cuij, exist_ok=True)
                    return ruta_cuij

    # 3) Fallback: raíz del estudio
    print(f"  ⚠ No se encontró carpeta para CUIJ {cuij}. Guardando en raíz del estudio.")
    ruta_fallback = os.path.join(RUTA_ESTUDIO, f"cédula {cuij}")
    os.makedirs(ruta_fallback, exist_ok=True)
    return ruta_fallback
