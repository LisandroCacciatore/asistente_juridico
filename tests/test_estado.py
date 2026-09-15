# -*- coding: utf-8 -*-
"""
TEST_ESTADO.PY

Pruebas sobre estado.py — sin Playwright, sin portal, sin red. Usa una
carpeta temporal para estado.json/log_acciones.jsonl en cada test, así
nunca toca datos reales del repo ni de ninguna máquina.

Uso:  python -m pytest tests/test_estado.py -v
"""
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import estado


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    """Redirige ARCHIVO y ARCHIVO_LOG a una carpeta temporal por test,
    para que ningún test toque estado.json/log_acciones.jsonl reales."""
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    yield tmp_path


# ============================================================
#  Ciclo de vida básico: registrar → firmar → presentar
# ============================================================

def test_cargar_sin_archivo_devuelve_estructura_vacia():
    data = estado.cargar()
    assert data == {"cedulas": [], "pendientes": []}


def test_registrar_cedula_agrega_fecha_generada():
    estado.registrar_cedula({"id": "c1", "caratula": "CASO A", "cuij": "21-1",
                              "estado": "generada"})
    ced = estado.obtener_cedula("c1")
    assert ced is not None
    assert ced["fecha_generada"]  # se completó sola


def test_registrar_cedula_misma_id_reemplaza_no_duplica():
    estado.registrar_cedula({"id": "c1", "caratula": "V1", "estado": "generada"})
    estado.registrar_cedula({"id": "c1", "caratula": "V2", "estado": "generada"})
    data = estado.cargar()
    assert len(data["cedulas"]) == 1
    assert data["cedulas"][0]["caratula"] == "V2"


def test_marcar_firmada_completa_fecha_y_ruta():
    estado.registrar_cedula({"id": "c1", "caratula": "CASO A", "estado": "generada"})
    estado.marcar_firmada("c1", "/tmp/x_FIRMADO.pdf")
    ced = estado.obtener_cedula("c1")
    assert ced["estado"] == "firmada"
    assert ced["ruta_firmada"] == "/tmp/x_FIRMADO.pdf"
    assert ced["fecha_firmada"]


# ============================================================
#  marcar_presentada: borra SUS archivos, no toca los de otra cédula
# ============================================================

def test_marcar_presentada_borra_pdf_original_y_firmado(tmp_path):
    pdf = tmp_path / "cedula.pdf"
    pdf_firmado = tmp_path / "cedula_FIRMADO.pdf"
    pdf.write_bytes(b"%PDF original")
    pdf_firmado.write_bytes(b"%PDF firmado")

    estado.registrar_cedula({
        "id": "c1", "caratula": "CASO A", "cuij": "21-1",
        "ruta_pdf": str(pdf), "ruta_firmada": str(pdf_firmado),
        "estado": "firmada",
    })
    estado.marcar_presentada("c1")

    assert not pdf.exists()
    assert not pdf_firmado.exists()
    assert estado.obtener_cedula("c1")["estado"] == "presentada"


def test_marcar_presentada_no_toca_los_archivos_de_otra_cedula(tmp_path):
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(b"%PDF a")
    pdf_b.write_bytes(b"%PDF b")

    estado.registrar_cedula({"id": "a", "caratula": "A", "ruta_pdf": str(pdf_a),
                              "ruta_firmada": None, "estado": "firmada"})
    estado.registrar_cedula({"id": "b", "caratula": "B", "ruta_pdf": str(pdf_b),
                              "ruta_firmada": None, "estado": "firmada"})

    estado.marcar_presentada("a")

    assert not pdf_a.exists()      # la presentada, se borró
    assert pdf_b.exists()          # la otra, intacta
    assert estado.obtener_cedula("b")["estado"] == "firmada"  # sin cambios


def test_marcar_presentada_no_rompe_si_el_archivo_ya_no_existe():
    # ruta_pdf apunta a un archivo que nunca existió: no debe lanzar excepción
    estado.registrar_cedula({"id": "c1", "caratula": "CASO A",
                              "ruta_pdf": "/no/existe/nunca.pdf",
                              "ruta_firmada": None, "estado": "firmada"})
    estado.marcar_presentada("c1")  # no debe tirar excepción
    assert estado.obtener_cedula("c1")["estado"] == "presentada"


# ============================================================
#  Pendientes de clasificar
# ============================================================

def test_agregar_y_eliminar_pendiente():
    estado.agregar_pendiente({"id": "p1", "caratula": "CASO X", "cuij": "21-9",
                               "tipo_sugerido": "estandar"})
    assert estado.obtener_pendiente("p1") is not None
    estado.eliminar_pendiente("p1")
    assert estado.obtener_pendiente("p1") is None


def test_eliminar_pendiente_de_una_no_afecta_a_otra():
    estado.agregar_pendiente({"id": "p1", "caratula": "X"})
    estado.agregar_pendiente({"id": "p2", "caratula": "Y"})
    estado.eliminar_pendiente("p1")
    assert estado.obtener_pendiente("p1") is None
    assert estado.obtener_pendiente("p2") is not None


# ============================================================
#  marcar_atencion ("Solicita Revisión" y similares)
# ============================================================

def test_marcar_atencion_guarda_motivo_con_etiqueta():
    estado.registrar_cedula({"id": "c1", "caratula": "CASO A", "estado": "firmada"})
    estado.marcar_atencion("c1", "No se encontró el expediente en Meta Jurídico")
    ced = estado.obtener_cedula("c1")
    assert ced["estado"] == "atencion"
    assert ced["reason"] == "Solicita Revisión: No se encontró el expediente en Meta Jurídico"


# ============================================================
#  Log de acciones: nunca se pisa, orden más reciente primero
# ============================================================

def test_registrar_log_no_pisa_entradas_anteriores():
    estado.registrar_log("generada", "c1")
    estado.registrar_log("firmada", "c1")
    estado.registrar_log("presentada", "c1")
    log = estado.leer_log()
    assert len(log) == 3


def test_leer_log_mas_reciente_primero():
    estado.registrar_log("generada", "c1")
    estado.registrar_log("firmada", "c1")
    log = estado.leer_log()
    assert log[0]["accion"] == "firmada"
    assert log[1]["accion"] == "generada"


def test_marcar_presentada_deja_rastro_del_borrado_en_el_log(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF")
    estado.registrar_cedula({"id": "c1", "caratula": "CASO A",
                              "ruta_pdf": str(pdf), "ruta_firmada": None,
                              "estado": "firmada"})
    estado.marcar_presentada("c1")
    acciones = [e["accion"] for e in estado.leer_log()]
    assert "eliminado_pdf" in acciones
    assert "presentada" in acciones


# ============================================================
#  Concurrencia: el RLock de _mutar no debe perder actualizaciones
# ============================================================

def test_agregar_pendientes_en_paralelo_no_pierde_ninguno():
    # 20 hilos agregando cada uno un pendiente distinto al mismo tiempo.
    # Sin el lock que cubre cargar->modificar->guardar, esto pierde
    # entradas (dos hilos leen el mismo estado viejo y uno pisa al otro).
    hilos = []
    for i in range(20):
        t = threading.Thread(target=estado.agregar_pendiente,
                              args=({"id": f"p{i}", "caratula": f"CASO {i}"},))
        hilos.append(t)
    for t in hilos:
        t.start()
    for t in hilos:
        t.join()

    data = estado.cargar()
    ids = {p["id"] for p in data["pendientes"]}
    assert ids == {f"p{i}" for i in range(20)}
