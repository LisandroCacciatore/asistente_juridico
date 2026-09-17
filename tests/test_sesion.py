# -*- coding: utf-8 -*-
"""Quién entra, y con qué identidad firma y notifica (Fase 10a).

Cubre las decisiones D18, D19 y D24 de SPEC_CIRCUITO_v0.2.md.

Las dos reglas que estos tests protegen:

  1. El sistema tiene que poder decir **quién operó** y **con qué identidad**
     se firmó o se notificó — que no son lo mismo cuando alguien trabaja con
     la sesión de otro (el caso Jr con Santiago).
  2. **No se acepta un nombre que no esté en la lista del estudio**: si no, el
     log se puede firmar con cualquier nombre y deja de servir como registro.

Ni la jornada ni el log reales se tocan: todo va a una carpeta temporal.
"""
import datetime
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config_portales  # noqa: E402
import estado  # noqa: E402
import sesion  # noqa: E402

GENTE = {
    "Santiago": {"matricula": "LV029", "perfil": "chrome_profile_portales"},
    "Jr":       {"matricula": "12345", "perfil": "chrome_profile_jr"},
    "Socio":    {"matricula": "",      "perfil": "chrome_profile_socio"},
}


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    """La jornada y el log reales no se tocan nunca desde los tests."""
    monkeypatch.setattr(sesion, "ARCHIVO", str(tmp_path / "sesion.json"))
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    monkeypatch.setattr(sesion, "personas", lambda: GENTE)
    yield tmp_path


# ============================================================
#  La lista de gente del estudio
# ============================================================

def test_los_operadores_salen_de_la_lista():
    assert sesion.operadores() == ["Santiago", "Jr", "Socio"]


def test_sin_lista_configurada_no_inventa_gente(monkeypatch):
    """Una máquina sin la lista cargada no se queda sin asistente: cae al
    usuario de Windows, que es el único dato que hay."""
    monkeypatch.setattr(sesion, "personas", lambda: {})
    assert sesion.operadores() == [sesion.usuario_windows()]


def test_el_nombre_se_acepta_sin_importar_mayusculas():
    assert sesion.nombre_valido("jr") == "Jr"
    assert sesion.nombre_valido("  SOCIO ") == "Socio"


@pytest.mark.parametrize("nombre", ["Invitado", "", None, "Santi", "1234"])
def test_un_nombre_que_no_esta_en_la_lista_se_rechaza(nombre):
    assert sesion.nombre_valido(nombre) == ""


def test_la_lista_real_de_config_tiene_a_las_tres_personas():
    """Sin el parche de los tests: así está en config.py."""
    import config
    assert {"Santiago", "Jr", "Socio"} <= set(config.PERSONAS)


# ============================================================
#  La jornada: declarar, vencer, cerrar
# ============================================================

def test_declarar_arranca_la_jornada():
    s = sesion.declarar("Jr")
    assert s["operador"] == "Jr"
    assert s["identidad"] == "Jr"          # por defecto, la suya
    assert s["maquina"] and s["usuario_windows"]
    assert s["inicio"]
    assert sesion.actual()["operador"] == "Jr"


def test_declarar_que_otro_opera_con_la_identidad_de_santiago():
    """El caso que motivó todo esto: Jr maneja, pero firma y notifica la
    identidad de Santiago. Las dos quedan asentadas."""
    sesion.declarar("Jr", identidad="Santiago")
    s = sesion.actual()
    assert s["operador"] == "Jr"
    assert s["identidad"] == "Santiago"


def test_declarar_un_desconocido_falla():
    with pytest.raises(ValueError) as e:
        sesion.declarar("Invitado")
    assert "Invitado" in str(e.value)
    assert sesion.actual() is None


def test_declarar_con_identidad_desconocida_falla():
    with pytest.raises(ValueError):
        sesion.declarar("Jr", identidad="Invitado")


def test_sin_declarar_no_hay_jornada():
    assert sesion.actual() is None
    assert sesion.estado_para_el_panel()["declarada"] is False


def test_cerrar_la_jornada():
    sesion.declarar("Jr")
    sesion.cerrar()
    assert sesion.actual() is None


def test_cambiar_de_persona_en_la_misma_jornada():
    sesion.declarar("Jr")
    sesion.declarar("Socio")
    assert sesion.actual()["operador"] == "Socio"


# --- El vencimiento (función pura: se prueba sin reloj real) ------

def test_vencida_sin_jornada():
    assert sesion.vencida(None) is True
    assert sesion.vencida({}) is True


def test_vencida_al_cambiar_el_dia():
    """Nadie declara quién es a las 9 y sigue valiendo a la mañana siguiente."""
    ayer = datetime.datetime(2026, 9, 15, 23, 30)
    hoy = datetime.datetime(2026, 9, 16, 9, 0)
    s = {"operador": "Jr", "inicio": ayer.isoformat(), "ultimo_uso": ayer.isoformat()}
    assert sesion.vencida(s, ahora=hoy) is True


def test_no_vence_dentro_del_mismo_dia():
    s = {"operador": "Jr", "inicio": "2026-09-16T09:00:00", "ultimo_uso": "2026-09-16T09:00:00"}
    assert sesion.vencida(s, ahora=datetime.datetime(2026, 9, 16, 17, 0)) is False


def test_vence_por_inactividad():
    """La máquina que quedó abierta sin nadie: pasado el límite, vuelve a
    preguntar aunque sea el mismo día. El límite por defecto son 12 horas."""
    ultimo = datetime.datetime(2026, 9, 16, 8, 0)
    s = {"operador": "Jr", "inicio": ultimo.isoformat(), "ultimo_uso": ultimo.isoformat()}
    assert sesion.vencida(s, ahora=datetime.datetime(2026, 9, 16, 10, 0),
                          horas_inactividad=12) is False      # 2 horas: sigue
    assert sesion.vencida(s, ahora=datetime.datetime(2026, 9, 16, 20, 1),
                          horas_inactividad=12) is True       # 12 h 1 min: venció
    assert sesion.vencida(s, ahora=datetime.datetime(2026, 9, 16, 21, 0)) is True


def test_la_jornada_vencida_no_devuelve_nada(monkeypatch):
    """`actual()` aplica el vencimiento: si venció, es como si no hubiera.

    Con el reloj fijo: si dependiera de la hora real, este test pasaría o
    fallaría según a qué hora se corran los tests.
    """
    fijo = datetime.datetime(2026, 9, 16, 10, 0)
    monkeypatch.setattr(sesion, "_ahora", lambda: fijo)
    sesion.declarar("Jr")
    assert sesion.actual()["operador"] == "Jr"

    treinta_horas = fijo + datetime.timedelta(hours=30)   # otro día y sin uso
    monkeypatch.setattr(sesion, "_ahora", lambda: treinta_horas)
    assert sesion.actual() is None


def test_tocar_marca_actividad(monkeypatch):
    """El panel se refresca solo cada 60 s: mientras está abierto, la jornada
    sigue viva (y si nadie lo mira 12 horas, vence)."""
    fijo = datetime.datetime(2026, 9, 16, 10, 0)
    monkeypatch.setattr(sesion, "_ahora", lambda: fijo)
    sesion.declarar("Jr")
    assert sesion._leer()["ultimo_uso"] == fijo.isoformat(timespec="seconds")

    dos_horas = fijo + datetime.timedelta(hours=2)
    monkeypatch.setattr(sesion, "_ahora", lambda: dos_horas)
    assert sesion.actual(tocar=True)["operador"] == "Jr"
    assert sesion._leer()["ultimo_uso"] == dos_horas.isoformat(timespec="seconds")


# ============================================================
#  Lo que ve el panel
# ============================================================

def test_estado_para_el_panel():
    sesion.declarar("Santiago")
    e = sesion.estado_para_el_panel()
    assert e["declarada"] is True
    assert e["operador"] == "Santiago"
    assert e["identidad"] == "Santiago"
    assert set(e["opciones"]) == {"Santiago", "Jr", "Socio"}
    assert e["usuario_windows"] and e["maquina"]


def test_detalle_de_la_identidad_con_y_sin_matricula():
    assert sesion.detalle_identidad("Santiago") == "Santiago — matrícula LV029"
    assert sesion.detalle_identidad("Jr") == "Jr — matrícula 12345"
    assert sesion.detalle_identidad("Socio") == "Socio (sin matrícula cargada)"
    assert "sin declarar" in sesion.detalle_identidad("")


# ============================================================
#  Un perfil de Chrome por persona (D24)
# ============================================================

def test_cada_persona_tiene_su_perfil():
    assert sesion.perfil_de("Jr").endswith("chrome_profile_jr")
    assert sesion.perfil_de("Socio").endswith("chrome_profile_socio")
    assert sesion.perfil_de("Santiago").endswith("chrome_profile_portales")


def test_una_persona_sin_perfil_propio_usa_el_de_siempre():
    """Que falte el dato no puede dejar el asistente sin navegador."""
    assert sesion.perfil_de("Nadie") == config_portales.PERFIL_CHROME
    assert sesion.perfil_de(None) == config_portales.PERFIL_CHROME


# ============================================================
#  La confirmación antes del portal (D19)
# ============================================================

def test_la_confirmacion_dice_quien_opera_y_con_que_identidad():
    sesion.declarar("Jr", identidad="Santiago")
    avisos = []
    pausar = sesion.pausar_con_identidad(avisos.append, "Santiago")
    pausar("Ingresá tu PIN y hacé clic en FIRMAR.")

    assert "identidad de Santiago" in avisos[0]
    assert "matrícula LV029" in avisos[0]
    assert "Operador registrado: Jr" in avisos[0]
    assert "Ingresá tu PIN" in avisos[0]     # el mensaje original sigue ahí


def test_la_confirmacion_no_se_repite_en_cada_paso():
    """En la firma en lote hay una pausa por documento: repetir el aviso
    cinco veces es ruido."""
    sesion.declarar("Jr")
    avisos = []
    pausar = sesion.pausar_con_identidad(avisos.append)
    pausar("Documento 1 de 5")
    pausar("Documento 2 de 5")

    assert "identidad" in avisos[0]
    assert avisos[1] == "Documento 2 de 5"


def test_la_confirmacion_sin_jornada_no_inventa_una_identidad():
    """Sin nadie declarado no se pone el nombre de la máquina como si fuera
    una identidad: eso haría creer que sí se sabe quién está firmando."""
    avisos = []
    sesion.pausar_con_identidad(avisos.append)("Ingresá tu PIN.")
    assert "No hay una identidad declarada" in avisos[0]
    assert "Operador registrado" in avisos[0]      # cae al usuario de Windows
    assert "Ingresá tu PIN" in avisos[0]


def test_la_confirmacion_avisa_si_la_maquina_no_tiene_la_lista(monkeypatch):
    """Máquina de un solo usuario, sin PERSONAS cargado: la identidad es la
    del usuario de Windows, y se dice tal cual en vez de callarse."""
    monkeypatch.setattr(sesion, "personas", lambda: {})
    avisos = []
    sesion.pausar_con_identidad(avisos.append)("Ingresá tu PIN.")
    assert "no tiene la lista de personas cargada" in avisos[0]


# ============================================================
#  Con qué identidad se ejecuta cada acto
# ============================================================

def test_el_acto_usa_la_identidad_de_la_jornada():
    sesion.declarar("Jr")
    assert sesion.identidad_para_el_acto() == "Jr"


def test_el_acto_puede_forzar_la_identidad_de_otro():
    sesion.declarar("Jr")
    assert sesion.identidad_para_el_acto("Santiago") == "Santiago"
    assert sesion.identidad_para_el_acto("Invitado") == "Jr"   # no cuela


def test_sin_jornada_el_acto_no_tiene_identidad():
    assert sesion.identidad_para_el_acto() == ""


# ============================================================
#  El log: las dos identidades en cada línea (D18)
# ============================================================

def test_el_log_sella_operador_e_identidad():
    sesion.declarar("Jr")
    estado.registrar_log("generada", "una_cedula", "CARATULA", "21-00000001-0")
    e = estado.leer_log()[0]
    assert e["operador"] == "Jr"
    assert e["identidad"] == "Jr"
    assert e["usuario"] and e["maquina"]       # el control cruzado sigue


def test_el_log_muestra_la_excepcion_cuando_alguien_usa_otra_identidad():
    """Si operó Jr pero firmó Santiago, el log tiene que dejar de leerse
    como si hubiera sido todo de la misma persona."""
    sesion.declarar("Jr", identidad="Santiago")
    estado.registrar_log("firmada", "una_cedula")
    e = estado.leer_log()[0]
    assert e["operador"] == "Jr"
    assert e["identidad"] == "Santiago"


def test_el_log_sin_jornada_cae_al_usuario_de_windows():
    """Queda el dato de la máquina: el campo nunca va vacío."""
    estado.registrar_log("generada", "una_cedula")
    e = estado.leer_log()[0]
    assert e["operador"] == sesion.usuario_windows()
    assert e["identidad"] == sesion.usuario_windows()


def test_la_accion_puede_declarar_la_identidad_a_mano():
    sesion.declarar("Jr")
    estado.registrar_log("firmada", "una_cedula", identidad="Santiago")
    assert estado.leer_log()[0]["identidad"] == "Santiago"


def test_las_lineas_viejas_del_log_se_siguen_leyendo(tmp_path):
    """Las del log anterior a D18 no tienen los campos: se completan al leer,
    así ningún consumidor tiene que acordarse de que pueden faltar."""
    import json
    ruta = tmp_path / "viejo.jsonl"
    ruta.write_text(json.dumps({"fecha_hora": "2026-09-16T10:00:00", "accion": "generada",
                                "id": "x", "caratula": "", "cuij": "", "detalle": "",
                                "usuario": "Torso", "maquina": "PC"}) + "\n", encoding="utf-8")
    import estado as est
    original = est.ARCHIVO_LOG
    est.ARCHIVO_LOG = str(ruta)
    try:
        e = est.leer_log()[0]
        assert e["operador"] == "Torso"     # el usuario de la máquina
        assert e["identidad"] == ""
    finally:
        est.ARCHIVO_LOG = original
