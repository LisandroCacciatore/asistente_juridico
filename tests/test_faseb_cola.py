# -*- coding: utf-8 -*-
"""Épica 3 de la Fase B: la cola sobrevive a un reinicio.

Cada escenario de la especifica es un test acá.
"""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import faseb_cola  # noqa: E402
from faseb_cola import Cola  # noqa: E402


@pytest.fixture
def cola(tmp_path):
    return Cola(str(tmp_path / "cola.json"))


def test_ciclo_normal(cola):
    t = cola.crear("firmar_lote", "c-1", "jr")
    assert t["estado"] == "pedido"
    cola.encolar(t["id"])
    assert cola.obtener(t["id"])["estado"] == "en_cola"
    cola.siguiente()
    assert cola.obtener(t["id"])["estado"] == "corriendo"
    cola.pasar(t["id"], "esperando_humano")
    cola.pasar(t["id"], "listo")
    assert cola.obtener(t["id"])["estado"] == "listo"


def test_cada_cambio_queda_en_disco(cola, tmp_path):
    t = cola.crear("firmar_lote", "c-1", "jr")
    cola.encolar(t["id"])
    # una instancia nueva lee el mismo archivo
    otra = Cola(str(tmp_path / "cola.json"))
    assert otra.obtener(t["id"])["estado"] == "en_cola"


def test_reinicio_con_trabajo_en_cola_sigue_en_cola(cola, tmp_path):
    t = cola.crear("firmar_lote", "c-1", "jr")
    cola.encolar(t["id"])
    otra = Cola(str(tmp_path / "cola.json"))
    dudosos = otra.recuperar()
    assert dudosos == [], "un trabajo en cola no se toca"
    assert otra.obtener(t["id"])["estado"] == "en_cola"
    assert otra.siguiente()["id"] == t["id"], "y se ejecuta"


@pytest.mark.parametrize("estado", ["corriendo", "esperando_humano"])
def test_reinicio_con_trabajo_corriendo_pasa_a_dudoso(cola, tmp_path, estado):
    t = cola.crear("presentar", "c-1", "jr")
    cola.encolar(t["id"])
    cola.siguiente()
    if estado == "esperando_humano":
        cola.pasar(t["id"], "esperando_humano")

    otra = Cola(str(tmp_path / "cola.json"))
    dudosos = otra.recuperar()
    assert len(dudosos) == 1
    assert dudosos[0]["estado"] == "dudoso"
    assert "SISFE" in dudosos[0]["motivo"]
    assert otra.obtener(t["id"])["estado"] == "dudoso"


def test_dudoso_no_se_encola_solo(cola):
    t = cola.crear("presentar", "c-1", "jr")
    cola.encolar(t["id"])
    cola.siguiente()
    cola.pasar(t["id"], "dudoso")
    assert cola.siguiente() is None, "nadie lo retoma sin una persona"
    with pytest.raises(faseb_cola.TransicionInvalida):
        cola.pasar(t["id"], "en_cola")


def test_tiempo_limite(cola):
    t = cola.crear("firmar_lote", "c-1", "jr")
    cola.encolar(t["id"])
    cola.siguiente()
    vencidos = cola.vencidos(ahora=t["creado"] + cola.ttl + 1)
    assert len(vencidos) == 1
    assert vencidos[0]["estado"] == "error"
    assert "tiempo límite" in vencidos[0]["motivo"]


def test_transicion_invalida(cola):
    t = cola.crear("firmar_lote", "c-1", "jr")
    with pytest.raises(faseb_cola.TransicionInvalida):
        cola.pasar(t["id"], "listo")  # de pedido no se va a listo


def test_no_existe_el_trabajo(cola):
    with pytest.raises(KeyError):
        cola.pasar("no-existe", "en_cola")


def test_listar_por_estado(cola):
    a = cola.crear("firmar_lote", "c-1", "jr")
    b = cola.crear("presentar", "c-2", "jr")
    cola.encolar(a["id"])
    assert [t["id"] for t in cola.listar("en_cola")] == [a["id"]]
    assert len(cola.listar()) == 2


def test_dos_workers_no_toman_el_mismo_trabajo(tmp_path):
    """El lock de siguiente() evita que dos workers tomen el mismo trabajo."""
    import threading

    cola = faseb_cola.Cola(str(tmp_path / "cola.json"))
    for _ in range(6):
        cola.encolar(cola.crear("firmar")["id"])

    tomados = []
    cerrojo = threading.Lock()

    def worker():
        while True:
            trabajo = cola.siguiente()
            if not trabajo:
                break
            with cerrojo:
                tomados.append(trabajo["id"])

    hilos = [threading.Thread(target=worker) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert len(tomados) == 6
    assert len(set(tomados)) == 6, "un trabajo se tomo dos veces"
