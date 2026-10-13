# -*- coding: utf-8 -*-
"""Meta Jurídico está fuera del circuito (spec D1): este test lo sostiene.

Desde el 16/09/2026 la cédula firmada va directo al SISFE. El módulo
`meta_juridico.py` queda guardado en el repo (D1 dice "no se borra, no se
usa"), pero nada del circuito puede volver a colgar de él.

El 24/09/2026 se sacó lo último que quedaba: el import en `servidor.py`,
su modelo `DatosSubida` y la ruta `POST /api/subir`, que era código muerto
(el panel llama a `/api/skill/notificar_sisfe`, nunca a esa ruta) y que
igual obligaba a importar el módulo dormido al arrancar el servidor.

Estos tests existen para que no vuelva por descuido.
"""
import ast
import os
import sys
from pathlib import Path

RAIZ = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Rutas y carpetas que no son código del producto.
IGNORAR = {"__pycache__", ".git", ".venv", "venv", "node_modules",
           ".pytest_cache", "dev", "tests", "cedulas_temp"}

RUTA_MUERTA = "/api/subir"


def _fuente(nombre):
    return (RAIZ / nombre).read_text(encoding="utf-8")


def _rutas_declaradas(fuente):
    """Todos los paths que el servidor declara con @app.<metodo>(...).

    Se lee con AST y no buscando el texto: el comentario que explica la
    eliminación de la ruta menciona `/api/subir` a propósito, y una
    búsqueda de texto lo tomaría como si la ruta siguiera ahí.
    """
    rutas = []
    for nodo in ast.walk(ast.parse(fuente)):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in nodo.decorator_list:
            if (isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.args
                    and isinstance(dec.args[0], ast.Constant)
                    and isinstance(dec.args[0].value, str)):
                rutas.append(dec.args[0].value)
    return rutas


def _importa_meta_juridico(fuente):
    """¿El módulo importa meta_juridico (de cualquier forma)?"""
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.Import):
            if any(a.name == "meta_juridico" for a in nodo.names):
                return True
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.module == "meta_juridico":
                return True
    return False


def _modulos_de_producto():
    for p in sorted(RAIZ.rglob("*.py")):
        rel = p.relative_to(RAIZ)
        if any(parte in IGNORAR for parte in rel.parts):
            continue
        yield p


# ============================================================
#  El servidor no cuelga del módulo dormido
# ============================================================

def test_el_servidor_no_importa_meta_juridico():
    assert not _importa_meta_juridico(_fuente("servidor.py")), (
        "servidor.py volvió a importar meta_juridico: Meta está fuera del "
        "circuito (D1) y el panel no lo usa."
    )


def test_la_ruta_api_subir_no_existe():
    rutas = _rutas_declaradas(_fuente("servidor.py"))
    assert RUTA_MUERTA not in rutas, (
        f"{RUTA_MUERTA} volvió a aparecer. El único camino de la subida es "
        "POST /api/skill/notificar_sisfe."
    )


def test_ningun_modulo_de_producto_importa_meta_juridico():
    culpables = [str(p.relative_to(RAIZ)) for p in _modulos_de_producto()
                 if _importa_meta_juridico(p.read_text(encoding="utf-8"))]
    assert culpables == [], (
        f"Estos módulos importan meta_juridico: {culpables}. El módulo "
        "queda guardado (D1) pero nadie del circuito puede depender de él."
    )


# ============================================================
#  El panel tampoco lo llama
# ============================================================

def test_el_panel_no_llama_a_la_ruta_muerta():
    html = _fuente("asistente_juridico.html")
    assert RUTA_MUERTA not in html, (
        f"El dashboard volvió a llamar a {RUTA_MUERTA}."
    )


# ============================================================
#  Lo que D1 manda conservar
# ============================================================

def test_el_modulo_dormido_sigue_en_el_repo():
    """D1: `meta_juridico.py` no se borra. Sólo se deja de usar."""
    assert (RAIZ / "meta_juridico.py").is_file()


def test_la_subida_tiene_un_solo_camino():
    """La acción del panel y su implementación tienen que seguir atadas."""
    from_acciones = _fuente("acciones.py")
    assert 'if accion == "notificar_sisfe":' in from_acciones
    assert (RAIZ / "sisfe_notificar.py").is_file()


# ============================================================
#  Nota sobre "Solicita Revisión" (no es un olvido)
# ============================================================

def test_marcar_atencion_sigue_disponible():
    """`estado.marcar_atencion` se conserva aunque hoy no la llame nadie.

    La ruta de Meta era su único llamador y se eliminó, pero la función
    queda como capacidad del registro (y el panel sigue dibujando la
    sección «atención»). Ojo: que un fallo del SISFE NO la use es
    deliberado — ver
    tests/test_acciones_sisfe.py::test_si_el_portal_no_quedo_listo_avisa_y_no_marca_nada.
    """
    fuente = _fuente("estado.py")
    arbol = ast.parse(fuente)
    nombres = {n.name for n in ast.walk(arbol)
               if isinstance(n, ast.FunctionDef)}
    assert "marcar_atencion" in nombres
