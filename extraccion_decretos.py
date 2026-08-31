# ============================================================
#  EXTRACCION_DECRETOS.PY - Aislar el texto de un decreto puntual
#  dentro del texto completo de un Expediente Digital
# ============================================================
#
#  Sin dependencias de Selenium: trabaja sobre texto plano (ya sea
#  descargado por monitor.py, o pegado/subido a mano en el chat).
#  Reutilizado por monitor.py y por la skill de generación de cédulas.

import re

MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}
PATRON_FECHA_CABECERA = re.compile(
    r'ROSARIO,?\s*(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', re.IGNORECASE
)
PATRON_HEADING_CEDULA = re.compile(r'^\s*C[ÉE]DULA\b', re.IGNORECASE)
PATRON_CEDULA_INLINE = re.compile(r'\n\s*C[ÉE]DULA\s*\n', re.IGNORECASE)


def es_cedula_ya_presentada(novedad):
    """
    Detecta movimientos que son cédulas ya presentadas por el estudio
    (no decretos del juzgado). Patrones: 'A: <destinatario>' o
    'Agregada al expediente:'.
    """
    # Anclado al inicio de línea: las cédulas presentadas figuran como
    # "A: <destinatario>". Sin el ancla, un decreto tipo "TRASLADO A: la
    # contraria" daba falso positivo y se salteaba sin generar cédula.
    if re.search(r'(?m)^\s*A:\s*\S', novedad):
        return True
    if "agregada al expediente" in novedad.lower():
        return True
    return False


def _fecha_variantes(fecha_dd_mm_aaaa):
    """De '04/05/2026' devuelve {'4 de mayo de 2026', '04 de mayo de 2026'}."""
    try:
        dia, mes, anio = fecha_dd_mm_aaaa.split("/")
        dia_i = int(dia)
        mes_nombre = MESES[int(mes)]
        return {
            f"{dia_i} de {mes_nombre} de {anio}".lower(),
            f"{dia_i:02d} de {mes_nombre} de {anio}".lower(),
        }
    except Exception:
        return set()


def _limpiar_bloque(texto):
    """Saca líneas de carátula/juzgado repetidas y colapsa espacios."""
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    utiles = []
    for l in lineas:
        if re.search(r'\sC/\s.*\sS/\s', " " + l + " "):
            continue
        if re.search(r'Juzg\.|Inst\.|Nom\.$', l):
            continue
        utiles.append(l)
    return re.sub(r'\s+', ' ', " ".join(utiles)).strip()


def _fecha_propia_del_bloque(texto):
    """
    Busca la fecha declarada al PRINCIPIO del bloque/página (la cabecera
    propia del documento, tipo 'ROSARIO, 12 de Junio de 2026'), ignorando
    fechas que puedan aparecer más adelante dentro del cuerpo del texto.
    """
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    cabecera = []
    total = 0
    for l in lineas:
        if re.search(r'\sC/\s.*\sS/\s', " " + l + " "):
            continue
        if re.search(r'Juzg\.|Inst\.|Nom\.$', l):
            continue
        cabecera.append(l)
        total += len(l)
        if total > 250:
            break
    texto_cab = " ".join(cabecera)
    m = PATRON_FECHA_CABECERA.search(texto_cab)
    if not m:
        return None
    dia_i = int(m.group(1))
    mes_nombre = m.group(2).lower()
    anio = m.group(3)
    return f"{dia_i} de {mes_nombre} de {anio}"


def _paginas_no_cedula(bloque):
    """
    Un bloque (separado por el marcador '*<id_expediente>*') puede traer
    varias PÁGINAS separadas por salto de página: el decreto en sí y, a
    continuación, una o más cédulas ya generadas y notificadas. Nos
    quedamos solo con las páginas que NO son, ellas mismas, una cédula
    (no arrancan con el encabezado "CÉDULA"), y truncamos cualquier
    cédula pegada sin salto de página detectable.
    """
    paginas = bloque.split("\x0c")
    resultado = []
    for p in paginas:
        p_strip = p.strip()
        if not p_strip:
            continue
        if PATRON_HEADING_CEDULA.match(p_strip):
            continue
        m = PATRON_CEDULA_INLINE.search(p_strip)
        if m:
            p_strip = p_strip[:m.start()].strip()
        resultado.append(p_strip)
    return resultado


def _formatear_fecha_propia(fecha_propia):
    """De '12 de junio de 2026' (interno, en minúsculas) a '12 de Junio de 2026' (para mostrar)."""
    if not fecha_propia:
        return ""
    partes = fecha_propia.split(" de ")
    if len(partes) != 3:
        return fecha_propia
    dia, mes, anio = partes
    return f"{dia} de {mes.capitalize()} de {anio}"


def listar_candidatos(texto_completo):
    """
    Devuelve la lista completa de (texto_pagina, fecha_propia) candidatos
    a decreto dentro del Expediente Digital, en el orden en que aparecen
    (de más antiguo a más nuevo). Útil para ubicar "los últimos N decretos"
    sin necesidad de conocer de antemano la fecha exacta de cada uno.
    """
    if not texto_completo:
        return []
    bloques = re.split(r'\*\d{6,}\*', texto_completo)
    bloques = [b.strip() for b in bloques if b.strip()]

    candidatos = []
    for b in bloques:
        for pagina in _paginas_no_cedula(b):
            fecha_propia = _fecha_propia_del_bloque(pagina)
            if fecha_propia:
                candidatos.append((_limpiar_bloque(pagina), _formatear_fecha_propia(fecha_propia)))
    return candidatos


def extraer_texto_decreto(texto_completo, fecha_decreto=None, debug=False):
    """
    Ubica, dentro del texto completo del Expediente Digital, el texto
    puntual del decreto de fecha `fecha_decreto` (dd/mm/aaaa, la fecha
    del movimiento en la tabla de SISFE).

    Devuelve (texto, fecha_propia, ambiguo):
      - (texto, "12 de Junio de 2026", False) -> extracción exitosa; la
        fecha propia es la que el documento declara en su encabezado
        ("ROSARIO, <fecha>"), que puede diferir de la fecha del
        movimiento en la tabla y es la que corresponde mostrar en la cédula.
      - (None, "", True)   -> hay 2+ documentos candidatos con la misma
                               fecha objetivo: no se puede elegir solo,
                               se debe marcar para revisión manual
      - (None, "", False)  -> no se encontró ningún candidato legible
    """
    if not texto_completo:
        return None, "", False

    bloques = re.split(r'\*\d{6,}\*', texto_completo)
    bloques = [b.strip() for b in bloques if b.strip()]

    candidatos = []
    for b in bloques:
        for pagina in _paginas_no_cedula(b):
            fecha_propia = _fecha_propia_del_bloque(pagina)
            if fecha_propia:
                candidatos.append((pagina, fecha_propia))

    if debug:
        print(f"    [debug] bloques={len(bloques)} candidatos={len(candidatos)}")

    if not candidatos:
        return None, "", False

    if fecha_decreto:
        variantes = _fecha_variantes(fecha_decreto)
        coincidencias = [(b, f) for b, f in candidatos if f in variantes]
        if len(coincidencias) == 1:
            b, f = coincidencias[0]
            return _limpiar_bloque(b), _formatear_fecha_propia(f), False
        if len(coincidencias) >= 2:
            print(f"    ⚠ AMBIGUO: {len(coincidencias)} documentos con fecha {fecha_decreto} — se marca para revisión manual")
            return None, "", True

    # Sin fecha objetivo (o sin coincidencia exacta): último candidato del expediente
    b, f = candidatos[-1]
    return _limpiar_bloque(b), _formatear_fecha_propia(f), False
