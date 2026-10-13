# -*- coding: utf-8 -*-
"""El PDF de una cédula, servido por el servidor para verlo en el panel.

Antes el modal «Revisar cédula» mostraba los DATOS y decía «vista previa del
PDF»: el navegador no puede abrir una ruta del disco, así que no había forma
de ver el archivo de verdad. Desde el 24/09/2026 el panel lo pide a
`GET /api/cedula/<id>/pdf`.

Lo que se prueba acá, y por qué:
  - que sirva el archivo correcto (el firmado manda; el original si no hay)
  - que avise en vez de romper cuando el PDF ya no está (son transitorios:
    se borran al cerrar la cédula)
  - que el navegador NO pueda pedir un archivo que no sea de una cédula
    del registro (la ruta sale de estado.json, nunca del pedido)

Se usa el TestClient de FastAPI: pasa por el ruteo y el FileResponse reales.
Ningún test toca el estado.json del repo: se redirige a una carpeta temporal.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import estado  # noqa: E402
import servidor  # noqa: E402

PDF_ORIGINAL = b"%PDF-1.4\n% cedula generada, sin firmar\n"
PDF_FIRMADO = b"%PDF-1.4\n% cedula FIRMADA con FirmAr\n"


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    yield tmp_path


@pytest.fixture
def cliente():
    return TestClient(servidor.app)


def _cedula(tmp_path, con_original=True, con_firmado=False, sufijo=""):
    """Registra una cédula y devuelve (id, ruta_original, ruta_firmada)."""
    original = tmp_path / f"cedula{sufijo}.pdf"
    firmada = tmp_path / f"cedula{sufijo}_FIRMADO.pdf"
    if con_original:
        original.write_bytes(PDF_ORIGINAL)
    if con_firmado:
        firmada.write_bytes(PDF_FIRMADO)

    id_cedula = f"prueba{sufijo}"
    estado.registrar_cedula({
        "id": id_cedula,
        "caratula": "PRUEBA C/ ART EJEMPLO S/ ACCIDENTE LABORAL",
        "cuij": "21-00000001-0",
        "ruta_pdf": str(original) if con_original else None,
        "ruta_firmada": str(firmada) if con_firmado else None,
        "estado": "firmada" if con_firmado else "generada",
    })
    return id_cedula, original, firmada


# ============================================================
#  Sirve el archivo correcto
# ============================================================

def test_con_firmado_sirve_el_firmado(cliente, tmp_path):
    """`auto` (lo que pide el panel) prefiere la firmada: es la que se sube."""
    id_cedula, _, _ = _cedula(tmp_path, con_firmado=True)

    r = cliente.get(f"/api/cedula/{id_cedula}/pdf")

    assert r.status_code == 200
    assert r.content == PDF_FIRMADO


def test_sin_firmado_sirve_el_generado(cliente, tmp_path):
    """Todavía no se firmó: el panel igual puede mostrar lo que se va a firmar."""
    id_cedula, _, _ = _cedula(tmp_path)

    r = cliente.get(f"/api/cedula/{id_cedula}/pdf")

    assert r.status_code == 200
    assert r.content == PDF_ORIGINAL


def test_se_puede_pedir_el_original_a_proposito(cliente, tmp_path):
    """Con `cual=original` se ve el borrador aunque ya esté firmada."""
    id_cedula, _, _ = _cedula(tmp_path, con_firmado=True)

    r = cliente.get(f"/api/cedula/{id_cedula}/pdf?cual=original")

    assert r.status_code == 200
    assert r.content == PDF_ORIGINAL


def test_se_sirve_para_verlo_no_para_bajarlo(cliente, tmp_path):
    """`inline`: tiene que abrirse en el visor, no disparar una descarga."""
    id_cedula, _, _ = _cedula(tmp_path)

    r = cliente.get(f"/api/cedula/{id_cedula}/pdf")

    assert r.headers["content-type"].startswith("application/pdf")
    assert r.headers["content-disposition"].lower().startswith("inline")


# ============================================================
#  Cuando no hay nada que mostrar, avisa (no rompe)
# ============================================================

def test_cedula_que_no_esta_en_el_registro_da_404(cliente, tmp_path):
    r = cliente.get("/api/cedula/no-existe-esta-cedula/pdf")

    assert r.status_code == 404
    assert "registro" in r.json()["error"]


def test_si_el_pdf_se_borro_lo_dice(cliente, tmp_path):
    """Los PDF son transitorios: al cerrar la cédula se borran del disco.
    El panel tiene que poder explicar eso en vez de tirar un error crudo."""
    id_cedula, original, _ = _cedula(tmp_path)
    original.unlink()                       # simula la limpieza al notificar

    r = cliente.get(f"/api/cedula/{id_cedula}/pdf")

    assert r.status_code == 404
    assert "disco" in r.json()["error"]


def test_una_cedula_sin_rutas_anotadas_da_404(cliente, tmp_path):
    id_cedula, _, _ = _cedula(tmp_path, con_original=False)

    r = cliente.get(f"/api/cedula/{id_cedula}/pdf")

    assert r.status_code == 404


# ============================================================
#  El navegador no elige el archivo (esto es lo importante)
# ============================================================

def test_no_se_puede_pedir_un_archivo_de_afuera(cliente, tmp_path):
    """La ruta del archivo sale del registro, nunca del pedido.

    Si alguien arma un id con `../` o con una ruta absoluta, lo único que
    puede pasar es que el registro no encuentre esa cédula: nunca que el
    servidor devuelva un archivo que no sea de una cédula del estudio.
    """
    secreto = tmp_path / "config.py"
    secreto.write_text("SISFE_USUARIO = 'matricula real'\n", encoding="utf-8")

    for intento in ("../../config.py", "..%2F..%2Fconfig.py", str(secreto)):
        r = cliente.get(f"/api/cedula/{intento}/pdf")
        assert r.status_code == 404, intento
        assert b"SISFE_USUARIO" not in r.content


def test_el_pedido_no_puede_elegir_la_ruta_del_archivo(cliente, tmp_path):
    """Aunque el id exista, `cual` solo acepta tres valores conocidos: no hay
    campo por el que meter una ruta."""
    id_cedula, _, _ = _cedula(tmp_path, con_firmado=True)

    # un `cual` inventado cae en el comportamiento de `auto`
    r = cliente.get(f"/api/cedula/{id_cedula}/pdf?cual=/etc/passwd")

    assert r.status_code == 200
    assert r.content == PDF_FIRMADO
