# -*- coding: utf-8 -*-
"""Escritura atómica y log con operador/identidad explícitos.

La consola local y el portal son dos procesos distintos. `estado.py` tiene
que sobrevivir a que los dos escriban a la vez y a que uno muera a mitad de
una escritura.
"""
import json
import multiprocessing
import os
import sys

import pytest
from filelock import FileLock, SoftFileLock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import estado  # noqa: E402


def _tomar_lock(ruta_lock, listo, liberar):
    from filelock import FileLock

    with FileLock(ruta_lock):
        listo.set()
        liberar.wait(5)


@pytest.fixture(autouse=True)
def _archivos_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ARCHIVO", str(tmp_path / "estado.json"))
    monkeypatch.setattr(estado, "ARCHIVO_LOG", str(tmp_path / "log_acciones.jsonl"))
    yield tmp_path


def test_guardar_no_deja_temporales(_archivos_temporales):
    estado.guardar({"cedulas": [{"id": "c1"}], "pendientes": []})

    with open(estado.ARCHIVO, encoding="utf-8") as f:
        assert json.load(f)["cedulas"][0]["id"] == "c1"
    assert list(_archivos_temporales.glob("*.tmp")) == []


def test_si_falla_la_serializacion_no_pisa_el_original(_archivos_temporales, monkeypatch):
    original = {"cedulas": [{"id": "c1"}], "pendientes": []}
    estado.guardar(original)

    def falla(*args, **kwargs):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(estado.json, "dump", falla)
    with pytest.raises(RuntimeError):
        estado.guardar({"cedulas": [], "pendientes": []})

    with open(estado.ARCHIVO, encoding="utf-8") as f:
        assert json.load(f) == original
    assert list(_archivos_temporales.glob("*.tmp")) == []


def test_reintenta_replace_si_windows_da_permission_error(_archivos_temporales, monkeypatch):
    original = {"cedulas": [{"id": "c1"}], "pendientes": []}
    nuevo = {"cedulas": [{"id": "c2"}], "pendientes": []}
    estado.guardar(original)

    llamadas = {"n": 0}
    replace_real = estado.os.replace

    def replace_con_dos_fallos(origen, destino):
        llamadas["n"] += 1
        if llamadas["n"] < 3:
            raise PermissionError("archivo abierto por otro programa")
        return replace_real(origen, destino)

    monkeypatch.setattr(estado, "_ESPERA_REPLACE", 0)
    monkeypatch.setattr(estado.os, "replace", replace_con_dos_fallos)

    estado.guardar(nuevo)

    assert llamadas["n"] == 3
    with open(estado.ARCHIVO, encoding="utf-8") as f:
        assert json.load(f) == nuevo


def test_replace_falla_con_mensaje_claro_si_sigue_bloqueado(_archivos_temporales, monkeypatch):
    estado.guardar({"cedulas": [], "pendientes": []})

    def siempre_bloqueado(origen, destino):
        raise PermissionError("archivo abierto por otro programa")

    monkeypatch.setattr(estado, "_ESPERA_REPLACE", 0)
    monkeypatch.setattr(estado.os, "replace", siempre_bloqueado)

    with pytest.raises(estado.ErrorEscrituraEstado, match="intentos"):
        estado.guardar({"cedulas": [{"id": "c2"}], "pendientes": []})

    with open(estado.ARCHIVO, encoding="utf-8") as f:
        assert json.load(f) == {"cedulas": [], "pendientes": []}


def test_usa_filelock_no_softfilelock():
    assert estado.FileLock is FileLock
    assert estado.FileLock is not SoftFileLock


def test_timeout_del_lock_es_legible(_archivos_temporales, monkeypatch):
    ctx = multiprocessing.get_context("spawn")
    listo = ctx.Event()
    liberar = ctx.Event()
    proceso = ctx.Process(
        target=_tomar_lock,
        args=(f"{estado.ARCHIVO}.lock", listo, liberar),
    )
    proceso.start()
    try:
        assert listo.wait(10)
        monkeypatch.setattr(estado, "BLOQUEO_TIMEOUT", 0.2)
        with pytest.raises(estado.EstadoBloqueado, match="lock"):
            estado.guardar({"cedulas": [], "pendientes": []})
    finally:
        liberar.set()
        proceso.join(10)
        if proceso.is_alive():
            proceso.terminate()
            proceso.join(5)
    assert proceso.exitcode == 0


def test_registrar_log_acepta_operador_e_identidad_explicitos(_archivos_temporales):
    entrada = estado.registrar_log(
        "pdf_subido",
        "c1",
        detalle="sha256=abc",
        operador="Jr",
        identidad="Santiago",
        usuario="win-jr",
        maquina="PC-JR",
    )

    assert entrada["operador"] == "Jr"
    assert entrada["identidad"] == "Santiago"
    assert entrada["usuario"] == "win-jr"
    assert entrada["maquina"] == "PC-JR"

    log = estado.leer_log()
    assert log[0]["operador"] == "Jr"
    assert log[0]["identidad"] == "Santiago"
    assert log[0]["detalle"] == "sha256=abc"
