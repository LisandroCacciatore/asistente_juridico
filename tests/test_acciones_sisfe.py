# -*- coding: utf-8 -*-
"""La acción de subir al SISFE, del lado del motor de acciones.

Cubre la Fase 6 del SPEC_CIRCUITO_v0.2.md: que los datos salgan de la
cédula y no del panel, que un fallo del portal no marque nada, y que la
cédula NO desaparezca de la pantalla cuando queda cargada.

Todo con un `sisfe_notificar.subir` de mentira: acá no se toca el portal.
El estado real (estado.json / log_acciones.jsonl) tampoco: se redirige a
una carpeta temporal en cada test.
"""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import acciones  # noqa: E402
import estado  # noqa: E402
import sesion  # noqa: E402
import sisfe_notificar  # noqa: E402

CUIJ = "21-04253894-6"
CARATULA = "RIVAS JESUS IGNACIO C/ ASOCIART ART SA S/ ENFERMEDAD LABORAL"


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    """Ningún test toca el estado.json/log/sesión reales del repo."""
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    monkeypatch.setattr(sesion, "ARCHIVO", str(tmp_path / "sesion.json"))
    yield tmp_path


def _cedula_firmada(tmp_path, con_firmado=True, con_cuij=True):
    """Una cédula como la deja el paso de firma."""
    ruta_pdf = tmp_path / "cedula.pdf"
    ruta_pdf.write_bytes(b"%PDF-1.4\n")
    firmada = tmp_path / "cedula_FIRMADO.pdf"
    if con_firmado:
        firmada.write_bytes(b"%PDF-1.4\n% firmada\n")

    estado.registrar_cedula({
        "id": "rivas_000001", "caratula": CARATULA,
        "cuij": CUIJ if con_cuij else "",
        "ruta_pdf": str(ruta_pdf),
        "ruta_firmada": str(firmada) if con_firmado else None,
        "estado": "firmada",
    })
    return "rivas_000001", str(firmada)


def _subida_falsa(monkeypatch, resultado):
    """Reemplaza la subida real y anota con qué la llamaron."""
    llamadas = {}

    def falso(ruta_pdf, cuij, caratula=None, descripcion=None,
              usar_chrome=True, pausar=None, elegir=None, perfil=None):
        llamadas.update(ruta_pdf=ruta_pdf, cuij=cuij, caratula=caratula,
                        pausar=pausar, perfil=perfil)
        return resultado

    monkeypatch.setattr(sisfe_notificar, "subir", falso)
    return llamadas


def _resultado_ok(**extra):
    r = {
        "ok": True, "cuij": CUIJ, "caratula_portal": CARATULA,
        "id_sisfe": "10067855763", "descripcion": "16/09/2026",
        "adjuntado": True,
        "partes": [
            {"fila": 0, "caracter": "AUXILIAR DE JUSTICIA",
             "parte": "CAJA DE SEG.SOCIAL DE ABOGADOS Y PROCURA", "codigo": "CS01", "correo": ""},
            {"fila": 3, "caracter": "REPRESENTANTE",
             "parte": "PEREYRA, FABIAN CARLOS", "codigo": "XXI100",
             "correo": "FCPEREYRA@GMAIL.COM"},
        ],
        "tildadas": [0, 3], "avisos": [], "notificado": False,
    }
    r.update(extra)
    return r


# ============================================================
#  De dónde salen los datos
# ============================================================

def test_el_pdf_y_el_cuij_salen_de_la_cedula(monkeypatch, tmp_path):
    """El panel manda el id y nada más: el resto no se puede escribir mal."""
    id_cedula, firmada = _cedula_firmada(tmp_path)
    llamadas = _subida_falsa(monkeypatch, _resultado_ok())

    r = acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    assert llamadas["ruta_pdf"] == firmada            # el FIRMADO, no el original
    assert llamadas["cuij"] == CUIJ
    assert llamadas["caratula"] == CARATULA
    assert r["ok"] is True
    assert r["id_sisfe"] == "10067855763"
    assert r["tildadas"] == 2
    assert r["notificado"] is False                   # el clic es del abogado


def test_la_pausa_del_portal_confirma_con_que_identidad_se_actua(monkeypatch, tmp_path):
    """Antes de abrir el SISFE, la pausa dice con qué identidad se va a actuar
    (SPEC D19): no se vuelve a preguntar quién sos, se confirma en pantalla."""
    id_cedula, _ = _cedula_firmada(tmp_path)
    sesion.declarar("Jr", identidad="Santiago")
    llamadas = _subida_falsa(monkeypatch, _resultado_ok())
    mensajes = []

    acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula}, pausar=mensajes.append)

    assert llamadas["pausar"] is not None
    llamadas["pausar"]("Ingresá tu contraseña de SISFE.")   # así la llama el módulo
    assert "identidad de Santiago" in mensajes[0]
    assert "Operador registrado: Jr" in mensajes[0]


def test_a_la_subida_le_llega_el_perfil_de_la_identidad(monkeypatch, tmp_path):
    """Cada uno entra a los portales con su perfil (SPEC D24): la sesión del
    SISFE es personal, no de la máquina."""
    id_cedula, _ = _cedula_firmada(tmp_path)
    sesion.declarar("Jr")
    llamadas = _subida_falsa(monkeypatch, _resultado_ok())

    acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    assert llamadas["perfil"].endswith("chrome_profile_jr")


def test_la_identidad_del_acto_queda_en_el_log(monkeypatch, tmp_path):
    """El caso que motivó todo esto: operó Jr, se notificó con la identidad de
    Santiago. Las dos cosas tienen que poder leerse después."""
    id_cedula, _ = _cedula_firmada(tmp_path)
    sesion.declarar("Jr", identidad="Santiago")
    _subida_falsa(monkeypatch, _resultado_ok())

    r = acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    assert r["identidad"] == "Santiago"
    entrada = [l for l in estado.leer_log() if l["accion"] == "cargada_en_sisfe"][0]
    assert entrada["operador"] == "Jr"
    assert entrada["identidad"] == "Santiago"


def test_sin_pdf_firmado_no_arranca(monkeypatch, tmp_path):
    id_cedula, _ = _cedula_firmada(tmp_path, con_firmado=False)
    llamadas = _subida_falsa(monkeypatch, _resultado_ok())

    with pytest.raises(acciones.AccionError) as e:
        acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    assert "firmala primero" in str(e.value)
    assert "ruta_pdf" not in llamadas          # ni siquiera se intentó


def test_sin_cuij_no_arranca(monkeypatch, tmp_path):
    id_cedula, _ = _cedula_firmada(tmp_path, con_cuij=False)
    _subida_falsa(monkeypatch, _resultado_ok())

    with pytest.raises(acciones.AccionError) as e:
        acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    assert "CUIJ" in str(e.value)


def test_si_el_firmado_no_esta_en_el_disco_lo_dice_sin_pedir_ningun_paso(monkeypatch, tmp_path):
    """Un `ruta_firmada` que apunta a un archivo que ya no está.

    Se corta ANTES de la pausa: avisar "se va a abrir el SISFE" y hacer
    apretar «continuar» para después contar que el archivo no estaba es
    hacer perder el tiempo.
    """
    id_cedula, firmada = _cedula_firmada(tmp_path)
    os.remove(firmada)
    llamadas = _subida_falsa(monkeypatch, _resultado_ok())
    pausas = []

    with pytest.raises(acciones.AccionError) as e:
        acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula},
                          pausar=lambda m: pausas.append(m))

    assert "No encuentro el PDF firmado" in str(e.value)
    assert pausas == []                      # ningún paso humano pedido
    assert "ruta_pdf" not in llamadas        # y no se abrió ningún portal


# ============================================================
#  Un fallo del portal no marca nada
# ============================================================

def test_si_el_portal_no_quedo_listo_avisa_y_no_marca_nada(monkeypatch, tmp_path):
    id_cedula, _ = _cedula_firmada(tmp_path)
    _subida_falsa(monkeypatch, _resultado_ok(
        ok=False, id_sisfe="",
        avisos=["El expediente abierto es 21-99999999-9 y la cédula es de 21-04253894-6."],
    ))

    with pytest.raises(acciones.AccionError) as e:
        acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    assert "21-99999999-9" in str(e.value)
    cedula = estado.obtener_cedula(id_cedula)
    assert not cedula.get("sisfe_cargada")
    assert cedula["estado"] == "firmada"
    assert all(l["accion"] != "cargada_en_sisfe" for l in estado.leer_log())


# ============================================================
#  La cédula cargada sigue a la vista
# ============================================================

def test_cargarla_en_el_sisfe_no_la_saca_de_la_pantalla(monkeypatch, tmp_path):
    """El dashboard dibuja generada/firmada/presentada: si el paso le
    cambiara el estado, la cédula desaparecería de todas las secciones y
    el abogado no tendría dónde apretar «ya la notifiqué»."""
    id_cedula, _ = _cedula_firmada(tmp_path)
    _subida_falsa(monkeypatch, _resultado_ok())

    acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    cedula = estado.obtener_cedula(id_cedula)
    assert cedula["estado"] == "firmada"                 # sigue en «a presentar»
    assert cedula["sisfe_cargada"] is True
    assert cedula["sisfe_descripcion"] == "16/09/2026"


def test_el_paso_queda_en_el_log(monkeypatch, tmp_path):
    """Lo que sobrevive a los archivos es el log: ahí tiene que estar."""
    id_cedula, _ = _cedula_firmada(tmp_path)
    _subida_falsa(monkeypatch, _resultado_ok())

    acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    entradas = [l for l in estado.leer_log() if l["accion"] == "cargada_en_sisfe"]
    assert len(entradas) == 1
    assert entradas[0]["id"] == id_cedula
    assert entradas[0]["cuij"] == CUIJ
    assert entradas[0]["usuario"] and entradas[0]["maquina"]


# ============================================================
#  El cierre: sólo lo dispara una persona
# ============================================================

def test_confirmar_la_notificacion_cierra_la_cedula_y_borra_los_pdf(monkeypatch, tmp_path):
    id_cedula, firmada = _cedula_firmada(tmp_path)
    _subida_falsa(monkeypatch, _resultado_ok())
    acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})

    r = acciones.ejecutar("marcar_notificada", {"id_cedula": id_cedula})

    assert r["ok"] is True
    cedula = estado.obtener_cedula(id_cedula)
    assert cedula["estado"] == "presentada"
    assert not os.path.isfile(firmada)          # el PDF ya cumplió su función
    acciones_del_log = [l["accion"] for l in estado.leer_log()]
    assert "notificada_en_sisfe" in acciones_del_log
    assert "presentada" in acciones_del_log


def test_confirmar_una_cedula_que_no_existe_avisa():
    with pytest.raises(acciones.AccionError) as e:
        acciones.ejecutar("marcar_notificada", {"id_cedula": "no_existe"})
    assert "No encuentro esa cédula" in str(e.value)


# ============================================================
#  El dispatcher
# ============================================================

def test_el_dispatcher_conoce_las_dos_acciones(monkeypatch, tmp_path):
    id_cedula, _ = _cedula_firmada(tmp_path)
    _subida_falsa(monkeypatch, _resultado_ok())
    assert acciones.ejecutar("notificar_sisfe", {"id_cedula": id_cedula})["ok"] is True
    assert acciones.ejecutar("marcar_notificada", {"id_cedula": id_cedula})["ok"] is True


def test_una_accion_desconocida_sigue_fallando():
    with pytest.raises(acciones.AccionError):
        acciones.ejecutar("no_existe", {})
