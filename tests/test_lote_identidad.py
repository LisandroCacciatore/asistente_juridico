# -*- coding: utf-8 -*-
"""La identidad del lote de firma (spec, Fase 10a).

Un lote es UNA sola sesión de FirmAr: el mismo acto repetido, no actos
distintos. Por eso lleva UNA identidad.

Hasta el 24/09/2026 el servidor la ignoraba: `ItemLote.identidad` existía en el
modelo pero se descartaba al armar la lista de items, y `trabajo()` llamaba a
`identidad_para_el_acto()` sin argumento. Resultado: el lote entero se firmaba
siempre con la identidad de la jornada, y no había forma de decir "esto se firma
con la sesión de un compañero" — que es una de las cosas que D18 permite.

Lo que se prueba acá:

  - que la identidad que manda el panel sea la que firma. Lo que la vuelve real
    es el PERFIL de Chrome que se abre (D24), así que se verifica ahí: cada
    persona entra a FirmAr con su propia sesión.
  - que sin identidad siga valiendo la de la jornada (D19): no se rompe nada.
  - que un nombre que no está en la lista NO sirva como identidad: si no se
    valida, cualquiera firma como cualquiera.
  - que un lote con cédulas de personas distintas se frene con el motivo (D25),
    y que no se abra ninguna ventana de firma.

No se abre ningún navegador: `firmar_lote` se reemplaza por un doble que anota
con qué perfil lo llamaron. Ningún test toca el estado.json ni el sesion.json
del repo: se redirigen a una carpeta temporal.
"""
import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import estado      # noqa: E402
import sesion      # noqa: E402
import servidor    # noqa: E402


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    monkeypatch.setattr(sesion, "ARCHIVO", str(tmp_path / "sesion.json"))
    yield tmp_path


@pytest.fixture
def cliente():
    return TestClient(servidor.app)


@pytest.fixture
def doble(monkeypatch):
    """Reemplaza firmar_lote y guarda con qué perfil la llamaron."""
    visto = {}

    def falso(items, **kw):
        visto["items"] = items
        visto["perfil"] = kw.get("perfil")
        visto["identidad_de_la_pausa"] = None
        return [{"id_cedula": it["id_cedula"], "ok": True} for it in items]

    monkeypatch.setattr(servidor, "firmar_lote", falso)
    return visto


def _cedula(id_cedula, identidad_cadena=""):
    estado.registrar_cedula({
        "id": id_cedula,
        "caratula": "PRUEBA C/ ART EJEMPLO S/ ACCIDENTE LABORAL",
        "cuij": "21-00000001-0",
        "ruta_pdf": "C:/tmp/cedula.pdf",
        "estado": "generada",
    })
    if identidad_cadena:
        estado.fijar_cadena(id_cedula, identidad_cadena)


def _esperar(cliente, job_id, limite=5.0):
    fin = time.time() + limite
    while time.time() < fin:
        st = cliente.get(f"/api/estado/{job_id}").json()
        if st["status"] in ("listo", "error"):
            return st
        time.sleep(0.02)
    raise AssertionError("el trabajo del lote no terminó a tiempo")


def _lote(cliente, identidad=None, ids=("c1",)):
    cuerpo = {"items": [{"id_cedula": i, "ruta_pdf": "C:/tmp/cedula.pdf"} for i in ids]}
    if identidad is not None:
        cuerpo["identidad"] = identidad
    r = cliente.post("/api/firmar_lote", json=cuerpo)
    return _esperar(cliente, r.json()["job_id"])


# ============================================================
#  La identidad elegida es la que firma
# ============================================================

def test_la_identidad_del_lote_es_la_que_manda_el_panel(cliente, doble):
    """Firmar con la sesión de un compañero: es la excepción que D18 permite."""
    _cedula("c1")
    st = _lote(cliente, identidad="Jr")
    assert st["status"] == "listo", st
    assert doble["perfil"] == sesion.perfil_de("Jr")


def test_la_identidad_del_lote_le_gana_a_la_de_la_jornada(cliente, doble):
    """Jr está operando y firma con la sesión de Santiago. Es a propósito."""
    sesion.declarar("Jr")
    _cedula("c1")
    st = _lote(cliente, identidad="Santiago")
    assert st["status"] == "listo", st
    assert doble["perfil"] == sesion.perfil_de("Santiago")
    assert doble["perfil"] != sesion.perfil_de("Jr")


def test_sin_identidad_vale_la_de_la_jornada(cliente, doble):
    """Lo de siempre: no mandar identidad no puede cambiar el comportamiento."""
    sesion.declarar("Jr")
    _cedula("c1")
    st = _lote(cliente)
    assert st["status"] == "listo", st
    assert doble["perfil"] == sesion.perfil_de("Jr")


def test_un_nombre_que_no_esta_en_la_lista_no_sirve_de_identidad(cliente, doble):
    """Si no se valida, cualquiera firma el log con cualquier nombre."""
    sesion.declarar("Jr")
    _cedula("c1")
    st = _lote(cliente, identidad="Inventado")
    assert st["status"] == "listo", st
    assert doble["perfil"] == sesion.perfil_de("Jr")


# ============================================================
#  La cadena no se cruza, y el lote ni arranca
# ============================================================

def test_un_lote_con_cedulas_de_personas_distintas_se_frena(cliente, doble):
    """Del SISFE que salió cada una, es el mismo que tiene que firmar (D25)."""
    _cedula("c1", identidad_cadena="Santiago")
    _cedula("c2", identidad_cadena="Jr")

    st = _lote(cliente, ids=("c1", "c2"))

    assert st["status"] == "error"
    assert "Santiago" in st["error"] and "Jr" in st["error"]
    assert not doble, "no se tiene que haber abierto ninguna ventana de firma"


def test_la_cedula_con_cadena_le_gana_a_la_identidad_pedida(cliente, doble):
    """Pedir otra identidad para una cédula que ya es de alguien: se frena."""
    _cedula("c1", identidad_cadena="Jr")
    st = _lote(cliente, identidad="Santiago")
    assert st["status"] == "error"
    assert "Jr" in st["error"]
    assert not doble


def test_un_lote_entero_de_la_misma_persona_firma_con_esa(cliente, doble):
    """El caso normal de la cadena: dos cédulas de Jr, se firman con Jr."""
    _cedula("c1", identidad_cadena="Jr")
    _cedula("c2", identidad_cadena="Jr")
    st = _lote(cliente, ids=("c1", "c2"))
    assert st["status"] == "listo", st
    assert doble["perfil"] == sesion.perfil_de("Jr")
    assert len(doble["items"]) == 2


def test_sin_identidad_ni_jornada_no_inventa_una_identidad(cliente, doble):
    """Sin nadie declarado y sin pedir nada, la identidad es "" — no un nombre
    cualquiera. El perfil cae al de siempre, que es lo que D24 manda cuando la
    persona no está en la lista."""
    _cedula("c1")
    st = _lote(cliente)
    assert st["status"] == "listo", st
    assert sesion.identidad_para_el_acto() == ""
    assert doble["perfil"] == sesion.perfil_de("")
