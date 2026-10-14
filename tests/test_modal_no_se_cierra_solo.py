# -*- coding: utf-8 -*-
"""El modal no se puede cerrar solo — regresión del "el botón no hace nada".

LA FALLA (reportada el 14/10)
Un clic en "Revisar y firmar" abre el modal... y el modal TAPA el botón que
acabás de apretar. Un segundo clic en ese mismo lugar —doble clic, o volver a
apretar porque pareció que no respondió— caía en el fondo, y el fondo cerraba
el modal. Duración medida en Chrome: ~150 ms. Invisible al ojo, y sin ningún
error en consola: para quien lo usa, el botón simplemente no hizo nada.

LA DEFENSA (en asistente_juridico.html)
El fondo solo cierra ante un clic DELIBERADO: empezado y terminado en el fondo,
que no sea parte de un doble clic, con el puntero movido desde que el modal se
abrió, y con un instante transcurrido. "Cerrar"/"Cancelar" cierran siempre.

QUÉ CUBREN ESTAS PRUEBAS
El contrato del código fuente: que esas condiciones estén, y que la versión
ingenua (`if(e.target===scrim) closeModal()`) no vuelva. Es una guarda barata
contra el retroceso, no una prueba de comportamiento.

QUÉ NO CUBREN (y no pueden, sin navegador)
El comportamiento real de los eventos, que es donde vive la falla. Eso se
verifica a mano, en Chrome de verdad:

    python servidor.py
    # http://localhost:8000
    # 1. clic en "Revisar y firmar"        -> abre el modal
    # 2. clic OTRA VEZ en el mismo punto   -> el modal SIGUE abierto
    # 3. doble clic sobre el botón         -> el modal SIGUE abierto
    # 4. clic en el fondo, lejos del modal -> se cierra (eso está bien)
    # 5. el botón "Cerrar" del modal       -> se cierra

Verificado así el 14/10/2026: 9/9 casos en Chrome, 0 errores de JS.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "asistente_juridico.html"

# La versión con la falla. Si vuelve a aparecer, el modal se cierra solo otra vez.
CIERRE_INGENUO = 'if(e.target===scrim) closeModal();'


def fuente():
    return HTML.read_text(encoding="utf-8")


def bloque_de_cierre_por_fondo():
    """El handler que decide si un clic en el fondo cierra el modal."""
    f = fuente()
    i = f.index('scrim.addEventListener("click"')
    return f[i:i + 900]


def cuerpo_de_open_modal():
    f = fuente()
    i = f.index("function openModal(")
    return f[i:i + 500]


# ============================================================
#  La falla no puede volver
# ============================================================

def test_no_vuelve_el_cierre_ingenuo():
    """El `if(e.target===scrim) closeModal()` pelado ES la falla."""
    assert CIERRE_INGENUO not in fuente().replace(" ", ""), (
        "Volvió el cierre de fondo sin guardas: el modal se va a cerrar solo "
        "cuando alguien vuelva a apretar el botón que lo abrió."
    )


# ============================================================
#  Las cuatro condiciones del clic deliberado
# ============================================================

def test_exige_que_el_clic_empiece_en_el_fondo():
    """Arrastrar desde adentro del modal y soltar afuera no cierra."""
    assert "clicEmpezoEnFondo" in bloque_de_cierre_por_fondo()


def test_ignora_dobles_y_triples_clics():
    b = bloque_de_cierre_por_fondo()
    assert "e.detail > 1" in b, (
        "Sin esto, un doble clic sobre el botón abre el modal y lo cierra "
        "en la misma ráfaga."
    )


def test_exige_que_el_puntero_se_haya_movido():
    """La señal que distingue 'quiero cerrar' de 'apreté de nuevo lo mismo'."""
    assert "punteroSeMovio" in bloque_de_cierre_por_fondo()
    assert "PX_MOVIMIENTO" in fuente(), "Falta el umbral de movimiento en píxeles."


def test_exige_un_instante_desde_que_abrio():
    assert "performance.now() - modalAbiertoEn" in bloque_de_cierre_por_fondo()
    assert "MS_ANTES_DE_CERRAR" in fuente()


# ============================================================
#  Que el arreglo no haya roto el cerrar de verdad
# ============================================================

def test_open_modal_registra_donde_estaba_el_puntero():
    """Si openModal no guarda el punto, la condición 3 no puede evaluarse."""
    c = cuerpo_de_open_modal()
    assert "puntoAlAbrir" in c
    assert "punteroSeMovio = false" in c


def test_el_boton_cerrar_sigue_cerrando_sin_condiciones():
    """Cerrar/Cancelar no pueden depender de mover el mouse: si no, el modal
    se vuelve una trampa."""
    f = fuente()
    assert 'onclick="closeModal()"' in f, "Desapareció el cerrar explícito."
    i = f.index("function closeModal(")
    cuerpo = f[i:f.index("}", i)]
    assert "punteroSeMovio" not in cuerpo and "e.detail" not in cuerpo


def test_hay_una_sola_via_de_cierre_por_fondo():
    """Un segundo listener de fondo evadiría todas las guardas."""
    assert fuente().count('scrim.addEventListener("click"') == 1
