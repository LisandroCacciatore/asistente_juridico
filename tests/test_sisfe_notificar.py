# -*- coding: utf-8 -*-
"""SISFE: subir la cédula firmada y dejarla lista para notificar.

Cubre la Fase 6 del SPEC_CIRCUITO_v0.2.md (la secuencia que dictó
Santiago el 16/09/2026).

No hay sesión del SISFE acá, así que se prueba lo que NO necesita el
portal:

  1. la lógica pura (CUIJ, verificación del expediente, lectura de Partes),
  2. el armado del formulario sobre una página de mentira que imita la
     pantalla real —con su tabla de Partes y su botón Notificar—, y
  3. la regla que no se rompe: el módulo NUNCA toca el botón Notificar.

El punto 3 se verifica de dos maneras: leyendo el código con `ast` y,
sobre todo, corriendo el flujo de verdad contra la página de mentira y
comprobando que el botón quedó sin apretar después de completar todo.
"""
import ast
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import sisfe_notificar as sn  # noqa: E402


# ============================================================
#  Lógica pura
# ============================================================

@pytest.mark.parametrize("entrada, esperado", [
    ("21-04253894-6", "21-04253894-6"),
    ("CUIJ 21-04253894-6 (RIVAS)", "21-04253894-6"),
    ("21042538946", "21-04253894-6"),          # sin guiones, como se escribe a mano
    ("  21-04253894-6  ", "21-04253894-6"),
    ("", ""),
    (None, ""),
    ("123", ""),
])
def test_normalizar_cuij(entrada, esperado):
    assert sn.normalizar_cuij(entrada) == esperado


def test_verificar_expediente_el_mismo_no_avisa_nada():
    ok, avisos = sn.verificar_expediente(
        "21-04253894-6", "RIVAS JESUS IGNACIO C/ ASOCIART ART SA S/ ENFERMEDAD LABORAL",
        "21-04253894-6", "RIVAS JESUS IGNACIO C/ ASOCIART ART SA S/ ENFERMEDAD LABORAL",
    )
    assert ok is True
    assert avisos == []


def test_verificar_expediente_bloquea_si_el_cuij_no_coincide():
    """Notificar el expediente equivocado no se deshace con un botón."""
    ok, avisos = sn.verificar_expediente(
        "21-04253894-6", "RIVAS C/ ASOCIART", "21-99999999-9", "OTRO C/ OTRO",
    )
    assert ok is False
    assert "21-99999999-9" in avisos[0] and "21-04253894-6" in avisos[0]


def test_verificar_expediente_bloquea_si_no_puedo_leer_el_cuij_de_la_pantalla():
    ok, avisos = sn.verificar_expediente("21-04253894-6", "RIVAS C/ ASOCIART", "", "")
    assert ok is False
    assert "No pude leer el CUIJ" in avisos[0]


def test_verificar_expediente_la_caratula_distinta_avisa_pero_no_bloquea():
    """El portal escribe la carátula a su manera; bloquear por eso trabaría
    casos válidos. Avisa y decide el abogado."""
    ok, avisos = sn.verificar_expediente(
        "21-04253894-6", "RIVAS JESUS IGNACIO C/ ASOCIART ART SA S/ ENFERMEDAD LABORAL",
        "21-04253894-6", "RIVAS c/ ASOCIART ART S.A.",
    )
    assert ok is True
    assert len(avisos) == 1 and "carátula" in avisos[0].lower()


def test_verificar_expediente_la_puntuacion_no_cuenta_como_diferencia():
    ok, avisos = sn.verificar_expediente(
        "21-04253894-6", "RIVAS, JESÚS IGNACIO C/ ASOCIART ART SA S/ ENFERMEDAD LABORAL",
        "21-04253894-6", "RIVAS JESUS IGNACIO C/ ASOCIART ART SA S/ ENFERMEDAD LABORAL",
    )
    assert ok is True and avisos == []


@pytest.mark.parametrize("texto, nombre, codigo", [
    ("CAJA FORENSE-ROSARIO (CF02)", "CAJA FORENSE-ROSARIO", "CF02"),
    ("PEREYRA, FABIAN CARLOS (XXI100)", "PEREYRA, FABIAN CARLOS", "XXI100"),
    ("CAJA DE SEG.SOCIAL DE ABOGADOS Y PROCURA (CS01)",
     "CAJA DE SEG.SOCIAL DE ABOGADOS Y PROCURA", "CS01"),
    ("ART EJEMPLO S.A.", "ART EJEMPLO S.A.", ""),
])
def test_separar_codigo(texto, nombre, codigo):
    assert sn.separar_codigo(texto) == (nombre, codigo)


def test_descripcion_por_defecto_es_la_fecha():
    assert sn.descripcion_por_defecto(date(2026, 9, 16)) == "16/09/2026"
    assert sn.descripcion_por_defecto("una descripción") == "una descripción"


# --- Lectura de la tabla de Partes --------------------------------

FILAS_REALES = [
    # [tildar] | Carácter | Parte | Correo Electrónico  — tal cual la pantalla
    ["", "AUXILIAR DE JUSTICIA", "CAJA DE SEG.SOCIAL DE ABOGADOS Y PROCURA (CS01)", ""],
    ["", "AUXILIAR DE JUSTICIA", "CAJA FORENSE-ROSARIO (CF02)", ""],
    ["", "REPRESENTANTE", "LAMAS, ERICA GISELA (6372)", ""],
    ["", "REPRESENTANTE", "PEREYRA, FABIAN CARLOS (XXI100)", "FCPEREYRA@GMAIL.COM"],
]


def test_leer_partes_la_tabla_real_del_expediente():
    partes = sn.leer_partes(FILAS_REALES)
    assert len(partes) == 4
    assert [p["codigo"] for p in partes] == ["CS01", "CF02", "6372", "XXI100"]
    assert [p["caracter"] for p in partes] == [
        "AUXILIAR DE JUSTICIA", "AUXILIAR DE JUSTICIA", "REPRESENTANTE", "REPRESENTANTE"]
    # El correo va solo donde existe (D10): en esta tabla, solo Pereyra.
    assert [p["correo"] for p in partes] == ["", "", "", "FCPEREYRA@GMAIL.COM"]
    assert [p["fila"] for p in partes] == [0, 1, 2, 3]


def test_leer_partes_si_la_tabla_no_trae_columna_de_tilde():
    filas = [[c for c in f[1:]] for f in FILAS_REALES]   # sin la celda del tilde
    partes = sn.leer_partes(filas)
    assert len(partes) == 4
    assert partes[3]["correo"] == "FCPEREYRA@GMAIL.COM"
    assert partes[0]["codigo"] == "CS01"


def test_leer_partes_ignora_el_encabezado_si_viene_entre_las_filas():
    filas = [["", "Carácter", "Parte", "Correo Electrónico"]] + FILAS_REALES
    partes = sn.leer_partes(filas)
    assert len(partes) == 4
    assert all("Carácter" != p["parte"] for p in partes)


def test_leer_partes_no_inventa_nada_si_la_tabla_viene_vacia():
    assert sn.leer_partes([]) == []
    assert sn.leer_partes([[], [""], ["", ""]]) == []


def test_resumen_partes_marca_las_tildadas():
    partes = sn.leer_partes(FILAS_REALES)
    texto = sn.resumen_partes(partes, tildadas={0, 2})
    assert "☑ AUXILIAR DE JUSTICIA: CAJA DE SEG.SOCIAL DE ABOGADOS Y PROCURA (CS01)" in texto
    assert "☐ REPRESENTANTE: PEREYRA, FABIAN CARLOS (XXI100) → FCPEREYRA@GMAIL.COM" in texto


# ============================================================
#  La regla que no se rompe: nunca se aprieta Notificar
# ============================================================

def _textos_de_los_clics(fuente):
    """Todos los textos literales que se usan como blanco de un .click()."""
    arbol = ast.parse(fuente)
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "click"):
            continue
        for hijo in ast.walk(nodo):
            if isinstance(hijo, ast.Constant) and isinstance(hijo.value, str):
                yield hijo.value


def test_el_modulo_no_aprieta_ningun_boton_final():
    """Si alguien agrega mañana un clic en Notificar, este test lo frena."""
    fuente = (RAIZ / "sisfe_notificar.py").read_text(encoding="utf-8")
    culpables = [t for t in _textos_de_los_clics(fuente)
                 if any(b in t.lower() for b in sn.BOTONES_FINALES)]
    assert culpables == [], f"El módulo no puede apretar estos botones: {culpables}"


def test_el_modulo_declara_los_botones_que_no_toca():
    assert sn.BOTONES_FINALES == ("notificar", "presentar", "confirmar", "enviar")


# ============================================================
#  El formulario, de verdad, contra una página de mentira
# ============================================================

PAGINA_FALSA = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>SIN NOTIFICAR</title></head>
<body>
  <h1>Nueva Cédula</h1>

  <!-- Una tabla cualquiera, para probar que se elige la de Partes y no ésta -->
  <table id="movimientos">
    <thead><tr><th>Movimiento</th><th>Fecha</th></tr></thead>
    <tbody><tr><td>Decreto</td><td>21/05/2026</td></tr></tbody>
  </table>

  <label for="descripcion">Descripción genérica</label>
  <input id="descripcion" name="descripcion" type="text">

  <label for="archivo">Adjuntar</label>
  <input id="archivo" name="archivo" type="file">

  <table id="partes">
    <thead>
      <tr><th></th><th>Carácter</th><th>Parte</th><th>Correo Electrónico</th></tr>
    </thead>
    <tbody>
      <tr><td><input type="checkbox" id="p0"></td>
          <td>AUXILIAR DE JUSTICIA</td>
          <td>CAJA DE SEG.SOCIAL DE ABOGADOS Y PROCURA (CS01)</td><td></td></tr>
      <tr><td><input type="checkbox" id="p1"></td>
          <td>AUXILIAR DE JUSTICIA</td><td>CAJA FORENSE-ROSARIO (CF02)</td><td></td></tr>
      <tr><td><input type="checkbox" id="p2"></td>
          <td>REPRESENTANTE</td><td>LAMAS, ERICA GISELA (6372)</td><td></td></tr>
      <tr><td><input type="checkbox" id="p3"></td>
          <td>REPRESENTANTE</td><td>PEREYRA, FABIAN CARLOS (XXI100)</td>
          <td>FCPEREYRA@GMAIL.COM</td></tr>
    </tbody>
  </table>

  <button id="notificar" onclick="window.__clics=(window.__clics||0)+1;
          document.title='NOTIFICADO';">Notificar</button>
</body></html>
"""


@pytest.fixture(scope="module")
def navegador():
    """Chromium de Playwright (sin perfil persistente: no toca el Chrome
    de nadie).

    Si en ESTE Python no está bajado el navegador, se saltea en vez de
    romper: el repo corre con el Python del sistema, que sí lo tiene
    (el venv de Hermes puede tener otra versión de Playwright y otro
    build de Chromium). Un skip se ve; un error taparía los otros tests.
    """
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        # Solo el ARRANQUE del navegador puede saltear el test. Si el
        # except envolviera también el yield, cualquier fallo de un test
        # terminaría convertido en un skip silencioso.
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"Chromium de Playwright no disponible en este Python: {str(e)[:120]}")
        try:
            yield b
        finally:
            b.close()


def _abrir_pagina_falsa(navegador, tmp_path):
    html = tmp_path / "sisfe_falso.html"
    html.write_text(PAGINA_FALSA, encoding="utf-8")
    page = navegador.new_page()
    page.goto(html.as_uri())
    return page


def _pdf_firmado(tmp_path):
    pdf = tmp_path / "cedula_FIRMADO.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% cedula firmada de prueba\n")
    return str(pdf)


def test_completa_el_formulario_sobre_la_pantalla_de_mentira(navegador, tmp_path):
    page = _abrir_pagina_falsa(navegador, tmp_path)
    pausas = []
    try:
        r = sn.cargar_en_pagina(
            page, _pdf_firmado(tmp_path), "16/09/2026",
            pausar=pausas.append,
        )

        # Descripción (la genérica que pidió Santiago: la fecha)
        assert r["descripcion_ok"] is True
        assert page.locator("#descripcion").input_value() == "16/09/2026"

        # El PDF firmado quedó adjunto de verdad en el input de archivo
        assert r["adjuntado"] is True
        assert page.locator("#archivo").evaluate("el => el.files.length") == 1

        # Leyó la tabla de PARTES (no la de movimientos) y las 4 con su código
        assert [p["codigo"] for p in r["partes"]] == ["CS01", "CF02", "6372", "XXI100"]
        assert r["tildadas"] == [0, 1, 2, 3]
        assert r["avisos"] == []

        # Y todo quedó tildado en la pantalla
        assert page.locator("#partes input:checked").count() == 4
    finally:
        page.close()


def test_no_aprieta_notificar_ni_con_todo_cargado(navegador, tmp_path):
    """La regla del proyecto: el acto irreversible es del abogado.

    Se comprueba sobre la página real de mentira, no leyendo el código:
    después de completar todo, el botón sigue sin apretar.
    """
    page = _abrir_pagina_falsa(navegador, tmp_path)
    try:
        sn.cargar_en_pagina(page, _pdf_firmado(tmp_path), "16/09/2026",
                            pausar=lambda m: None)
        assert page.title() == "SIN NOTIFICAR"
        assert page.evaluate("window.__clics || 0") == 0
        assert page.locator("#notificar").is_visible()
    finally:
        page.close()


def test_tilda_solo_las_partes_confirmadas(navegador, tmp_path):
    """El abogado destilda: lo que no se tildó, no se tildó."""
    page = _abrir_pagina_falsa(navegador, tmp_path)
    try:
        r = sn.cargar_en_pagina(
            page, _pdf_firmado(tmp_path), "16/09/2026",
            elegir=lambda partes: [p["fila"] for p in partes if p["codigo"] != "6372"],
            pausar=lambda m: None,
        )
        assert r["tildadas"] == [0, 1, 3]
        assert page.locator("#p2").is_checked() is False
        assert page.locator("#p0").is_checked() is True
        assert page.locator("#p3").is_checked() is True
    finally:
        page.close()


def test_avisa_en_vez_de_seguir_si_no_encuentra_los_campos(navegador, tmp_path):
    """Una pantalla que no es la de Nueva Cédula: no rompe, avisa."""
    html = tmp_path / "otra_pantalla.html"
    html.write_text("<!DOCTYPE html><html><body><h1>Otra cosa</h1></body></html>",
                    encoding="utf-8")
    page = navegador.new_page()
    try:
        page.goto(html.as_uri())
        r = sn.cargar_en_pagina(page, _pdf_firmado(tmp_path), "16/09/2026",
                                pausar=lambda m: None)
        assert r["adjuntado"] is False
        assert r["tildadas"] == []
        assert any("Descripción" in a for a in r["avisos"])
        assert any("Partes" in a for a in r["avisos"])
    finally:
        page.close()
