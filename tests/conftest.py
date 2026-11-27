# -*- coding: utf-8 -*-
"""Configuración común de la suite.

El `TestClient` de FastAPI manda `Host: testserver`. En producción ese host no
existe y no debe existir en la lista de hosts permitidos: es un nombre de una
sola palabra que podría resolverse en una red local. Así que se inyecta sólo
durante las pruebas.
"""
import pytest


@pytest.fixture(autouse=True)
def _host_de_testclient(monkeypatch):
    try:
        import servidor
    except Exception:
        return  # los tests que no usan el asistente no lo necesitan
    monkeypatch.setattr(
        servidor,
        "HOSTS_PERMITIDOS",
        set(servidor.HOSTS_PERMITIDOS) | {"testserver"},
    )


@pytest.fixture(autouse=True)
def _sin_token_por_defecto(monkeypatch):
    """La suite corre sin token, como el dashboard. Los tests de la épica 1 lo
    activan con monkeypatch para probar el 401."""
    try:
        import servidor
    except Exception:
        return
    monkeypatch.setattr(servidor, "TOKEN_ASISTENTE", "", raising=False)
    monkeypatch.setattr(servidor, "TOKEN_PORTAL", "", raising=False)


@pytest.fixture(autouse=True)
def _cola_temporal(tmp_path_factory, monkeypatch):
    """La cola escribe en disco: en pruebas va a un archivo temporal."""
    try:
        import servidor
        import faseb_cola
    except Exception:
        return
    ruta = tmp_path_factory.mktemp("cola") / "cola.json"
    monkeypatch.setattr(servidor, "COLA", faseb_cola.Cola(str(ruta)))
