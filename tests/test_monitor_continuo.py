# -*- coding: utf-8 -*-
"""Modo continuo del monitor: horario, puerta del login y Chromes huérfanos.

Cubre lo que en la spec quedó como "una jornada completa sin supervisión":
que la decisión de horario se pueda probar, que un ciclo sin nadie
adelante no cuelgue la jornada, y que quede una señal si un Chrome no se
cierra entre ciclos.

Lo único que necesita navegador es el test del archivo de bloqueo, y se
verifica contra un Chromium de verdad: si esa señal no funcionara en
Windows, la detección de Chromes huérfanos no serviría de nada.
"""
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import monitor_playwright as mp  # noqa: E402


# ============================================================
#  Horario (era un if adentro del __main__: no se podía probar)
# ============================================================

LUNES = datetime(2026, 9, 14, 10, 0)      # 14/09/2026 fue lunes
SABADO = datetime(2026, 9, 19, 10, 0)
DOMINGO = datetime(2026, 9, 20, 10, 0)
DIAS = [0, 1, 2, 3, 4]


@pytest.mark.parametrize("momento, esperado", [
    (datetime(2026, 9, 14, 7, 59), False),      # un minuto antes de abrir
    (datetime(2026, 9, 14, 8, 0), True),        # justo al abrir
    (datetime(2026, 9, 14, 12, 30), True),
    (datetime(2026, 9, 14, 18, 0), True),       # justo al cerrar
    (datetime(2026, 9, 14, 18, 1), False),      # un minuto después
    (datetime(2026, 9, 14, 3, 0), False),       # madrugada
])
def test_en_horario_dentro_y_fuera(momento, esperado):
    assert mp.en_horario(momento, "08:00", "18:00", DIAS) is esperado


def test_en_horario_fin_de_semana_no_trabaja():
    assert mp.en_horario(SABADO, "08:00", "18:00", DIAS) is False
    assert mp.en_horario(DOMINGO, "08:00", "18:00", DIAS) is False


def test_en_horario_respeta_los_dias_configurados():
    """Si alguna máquina trabaja sábado, se configura y listo."""
    assert mp.en_horario(SABADO, "08:00", "18:00", [5, 6]) is True
    assert mp.en_horario(LUNES, "08:00", "18:00", [5, 6]) is False


def test_en_horario_acepta_otro_horario():
    assert mp.en_horario(datetime(2026, 9, 14, 21, 0), "20:00", "23:00", DIAS) is True
    assert mp.en_horario(datetime(2026, 9, 14, 21, 0), "08:00", "18:00", DIAS) is False


# ============================================================
#  La puerta del login, con tope
# ============================================================

def test_pausa_sin_tope_espera_a_la_persona(monkeypatch):
    """Cortesía: una corrida a mano no cambia (sigue esperando ENTER)."""
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert mp.pausa("hacé algo", segundos=None) is True


def test_pausa_con_tope_sigue_si_contestan(capsys):
    assert mp.pausa("hacé algo", segundos=5, leer=lambda prompt: "") is True
    assert "ACCIÓN TUYA" in capsys.readouterr().out


def test_pausa_con_tope_se_rinde_si_nadie_contesta(capsys):
    """Es lo que evita que la jornada entera quede esperando un ENTER."""
    def nunca(prompt):
        time.sleep(3)
        return ""

    arranque = time.monotonic()
    resultado = mp.pausa("hacé algo", segundos=0.3, leer=nunca)
    demora = time.monotonic() - arranque

    assert resultado is False
    assert demora < 2, "tiene que rendirse al toque, no esperar al que nunca contesta"
    assert "nadie contestó a tiempo" in capsys.readouterr().out


def test_pausa_con_tope_avisa_si_el_lector_falla():
    def roto(prompt):
        raise EOFError("sin consola")

    assert mp.pausa("hacé algo", segundos=2, leer=roto) is False


# ============================================================
#  Chrome huérfano: se mira el PROCESO, no un archivo
# ============================================================
# La primera versión de esto buscaba un archivo de bloqueo (SingletonLock)
# dentro del perfil. Se probó contra el Chromium real y NO EXISTE: en la
# raíz del perfil no queda ningún archivo de bloqueo mientras el
# navegador corre. Lo que sí existe es el proceso, con el perfil en su
# línea de comando. Eso es lo que estos tests fijan.

def test_no_reporta_nada_cuando_no_hay_ningun_chrome_con_ese_perfil(tmp_path):
    """Un perfil que no está usando nadie: lista vacía, sin falsa alarma."""
    pids = mp.procesos_con_el_perfil(str(tmp_path / "perfil_que_nadie_usa"))
    assert pids == []


def test_verificar_perfil_liberado_cuando_no_quedo_nada(monkeypatch, capsys):
    monkeypatch.setattr(mp, "procesos_con_el_perfil", lambda perfil: [])
    assert mp.verificar_perfil_liberado("cualquiera") is True
    assert "Sin Chromes colgados" in capsys.readouterr().out


def test_avisa_cuando_quedo_un_chrome_vivo(monkeypatch, capsys):
    monkeypatch.setattr(mp, "procesos_con_el_perfil", lambda perfil: [4242, 4243])
    assert mp.verificar_perfil_liberado("cualquiera") is False
    salida = capsys.readouterr().out
    assert "2 proceso(s)" in salida and "4242" in salida and "huérfano" in salida


def test_no_concluye_nada_si_no_pudo_averiguarlo(monkeypatch, capsys):
    """Si no se puede averiguar, no se inventa un resultado."""
    monkeypatch.setattr(mp, "procesos_con_el_perfil", lambda perfil: None)
    assert mp.verificar_perfil_liberado("cualquiera") is None
    assert "no pude verificar" in capsys.readouterr().out


def test_perfil_en_uso_traduce_los_tres_casos(monkeypatch):
    monkeypatch.setattr(mp, "procesos_con_el_perfil", lambda perfil: [])
    assert mp.perfil_en_uso("x") is False
    monkeypatch.setattr(mp, "procesos_con_el_perfil", lambda perfil: [7])
    assert mp.perfil_en_uso("x") is True
    monkeypatch.setattr(mp, "procesos_con_el_perfil", lambda perfil: None)
    assert mp.perfil_en_uso("x") is None


def test_chromium_de_verdad_aparece_y_desaparece(tmp_path):
    """El supuesto del que depende la detección, verificado de verdad.

    Se abre un Chromium con un perfil propio y se pregunta por él: tiene
    que aparecer mientras corre y no quedar ninguno después de cerrar.
    Eso es exactamente lo que el monitor reporta al final de cada ciclo,
    así que si esto no se sostiene, el reporte no sirve.
    """
    sync_api = pytest.importorskip("playwright.sync_api")
    perfil = tmp_path / "perfil_de_prueba"

    with sync_api.sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(perfil), headless=True)
        except Exception as e:
            pytest.skip(f"Chromium no disponible en este Python: {str(e)[:120]}")

        try:
            pids = mp.procesos_con_el_perfil(str(perfil))
            assert pids, "con el navegador abierto, su proceso tiene que aparecer"
        finally:
            ctx.close()

    # El cierre no es instantáneo: se le da un margen corto.
    for _ in range(10):
        if not mp.procesos_con_el_perfil(str(perfil)):
            break
        time.sleep(0.5)
    assert mp.procesos_con_el_perfil(str(perfil)) == [], \
        "al cerrar el navegador no tiene que quedar ningún proceso con ese perfil"
