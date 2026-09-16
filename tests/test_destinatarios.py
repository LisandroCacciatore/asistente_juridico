# -*- coding: utf-8 -*-
"""Destinatarios: detectarlos, confirmarlos y generar una cédula por cada uno.

Cubre la fase 2 del SPEC_CIRCUITO_v0.2.md (decisión D8). No necesita
portal: es lectura de texto y generación de PDFs.

La regla que estos tests protegen: el sistema propone a quién notificar
—y lo muestra— pero nunca inventa un destinatario. Lo que no está en la
carátula ni en lo que el juez manda notificar, no aparece.
"""
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import acciones  # noqa: E402
import estado  # noqa: E402
import generar_cedula  # noqa: E402
from cedula_desde_texto import extraer_destinatarios, extraer_partes  # noqa: E402


DECRETO = """JUZGADO DE PRIMERA INSTANCIA DE DISTRITO EN LO LABORAL DE LA 3 NOMINACIÓN DE ROSARIO
ROSARIO, 02 de Marzo de 2026.-

Autos caratulados: "PÉREZ c/ SEGUROS EJEMPLO S.A. S/ COBRO DE PESOS" CUIJ 21-00000009-0

Rosario, 2 de Marzo de 2026.- Proveyendo el escrito: téngase presente.
Notifíquese a la Dra. Ana Pérez. Notifíquese a las partes. Cítese a los peritos.
"""


def _texto(ruta):
    with open(ruta, "rb") as f:
        return " ".join(" ".join((p.extract_text() or "").split())
                        for p in PdfReader(f).pages)


# --------------------------------------------------- partes de la carátula
def test_partes_de_una_caratula_estandar():
    p = extraer_partes("PÉREZ c/ SEGUROS EJEMPLO S.A. S/ COBRO DE PESOS")
    assert p["actor"] == "PÉREZ"
    assert p["demandado"] == "SEGUROS EJEMPLO S.A."
    assert p["objeto"] == "COBRO DE PESOS"


def test_partes_conservan_el_punto_de_la_sigla():
    """«S.A.» pierde el punto si se recorta como si fuera puntuación."""
    p = extraer_partes("GÓMEZ c/ ART EJEMPLO S.R.L. S/ ACCIDENTE")
    assert p["demandado"] == "ART EJEMPLO S.R.L."


def test_partes_sin_objeto():
    p = extraer_partes("LÓPEZ c/ EMPRESA EJEMPLO S.A.")
    assert p["actor"] == "LÓPEZ"
    assert p["demandado"] == "EMPRESA EJEMPLO S.A."
    assert p["objeto"] == ""


def test_partes_de_caratula_vacia_no_inventa():
    assert extraer_partes("") == {"actor": "", "demandado": "", "objeto": ""}
    assert extraer_partes(None)["demandado"] == ""


# ------------------------------------------------------- destinatarios
def test_demandado_primero_y_actor_segundo():
    """El primero es el que el repo venía usando solo: la parte demandada."""
    d = extraer_destinatarios(DECRETO)
    assert [x["nombre"] for x in d] == ["SEGUROS EJEMPLO S.A.", "PÉREZ", "Dra. Ana Pérez"]
    assert d[0]["rol"] == "Demandado/a (de la carátula)"
    assert d[1]["rol"] == "Actor/a (de la carátula)"


def test_suma_al_que_el_decreto_manda_notificar():
    d = {x["nombre"]: x for x in extraer_destinatarios(DECRETO)}
    assert "Dra. Ana Pérez" in d
    assert d["Dra. Ana Pérez"]["origen"] == "decreto"


def test_no_toma_frases_genericas_como_persona():
    """«las partes» y «los peritos» no son destinatarios."""
    nombres = [x["nombre"] for x in extraer_destinatarios(DECRETO)]
    assert not any("partes" in n.lower() for n in nombres)
    assert not any("perito" in n.lower() for n in nombres)


def test_no_repite_al_que_ya_esta():
    texto = DECRETO + "\nNotifíquese a PÉREZ."
    nombres = [x["nombre"] for x in extraer_destinatarios(texto)]
    assert nombres.count("PÉREZ") == 1


def test_sin_caratula_no_devuelve_nada():
    """Sin carátula legible no hay destinatarios: mejor vacío que inventado."""
    assert extraer_destinatarios("Rosario, 2 de marzo. Notifíquese.") == []


# ------------------------------------------- paso previo del panel (D8)
def test_detectar_devuelve_lo_que_interpret_y_la_lista():
    r = acciones.detectar_destinatarios({"texto": DECRETO})
    assert r["ok"] is True
    assert r["caratula"] == "PÉREZ c/ SEGUROS EJEMPLO S.A. S/ COBRO DE PESOS"
    assert r["cuij"] == "21-00000009-0"
    assert r["fuero"] == "LABORAL"
    assert r["ciudad"] == "ROSARIO"
    assert r["aviso"] == ""
    assert len(r["destinatarios"]) == 3


def test_detectar_avisa_cuando_no_hay_caratula():
    r = acciones.detectar_destinatarios({"texto": "x" * 60})
    assert r["caratula"] == ""
    assert r["destinatarios"] == []
    assert "carátula" in r["aviso"]


def test_detectar_no_genera_ni_registra_nada(tmp_path, monkeypatch):
    """Es sólo lectura: no debe quedar ninguna cédula en estado.json."""
    tocado = []
    monkeypatch.setattr(estado, "registrar_cedula", lambda e: tocado.append(e))
    monkeypatch.setattr(generar_cedula, "CARPETA_CEDULAS_TEMP", str(tmp_path))
    acciones.detectar_destinatarios({"texto": DECRETO})
    assert tocado == []
    assert list(tmp_path.iterdir()) == []


def test_detectar_con_texto_corto_avisa_que_falta():
    with pytest.raises(acciones.AccionError):
        acciones.detectar_destinatarios({"texto": "muy corto"})


# ------------------------------------------------- lo que elige el panel
def test_respeta_la_lista_que_mando_el_panel():
    """Si el abogado destildó, no se genera lo destildado."""
    dests = acciones._destinatarios_de_datos(
        {"destinatarios": [{"nombre": "SEGUROS EJEMPLO S.A.", "domicilio": ""}]},
        "PÉREZ c/ SEGUROS EJEMPLO S.A. S/ COBRO",
    )
    assert dests == [{"nombre": "SEGUROS EJEMPLO S.A.", "domicilio": ""}]


def test_sin_lista_mantiene_el_comportamiento_de_siempre():
    """Una corrida por consola (sin panel) notifica al demandado, como antes."""
    dests = acciones._destinatarios_de_datos({}, "PÉREZ c/ SEGUROS EJEMPLO S.A. S/ COBRO")
    assert dests == [{"nombre": "SEGUROS EJEMPLO S.A.", "domicilio": "Domicilio constituido"}]


def test_ignora_las_filas_sin_nombre():
    dests = acciones._destinatarios_de_datos(
        {"destinatarios": [{"nombre": "  "}, {"nombre": "PÉREZ", "domicilio": "Mitre 100"}]},
        "PÉREZ c/ X S/ Y",
    )
    assert dests == [{"nombre": "PÉREZ", "domicilio": "Mitre 100"}]


# ------------------------------------------------------------- de punta a punta
def test_genera_una_cedula_por_destinatario(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "registrar_cedula", lambda e: None)
    monkeypatch.setattr(generar_cedula, "CARPETA_CEDULAS_TEMP", str(tmp_path))

    r = acciones.cedula({
        "texto": DECRETO,
        "destinatarios": [
            {"nombre": "SEGUROS EJEMPLO S.A.", "domicilio": ""},
            {"nombre": "PÉREZ", "domicilio": "Mitre 100 - Rosario"},
        ],
    })

    assert r["ok"] is True
    assert len(r["archivos"]) == 2
    assert r["destinatarios"] == ["SEGUROS EJEMPLO S.A.", "PÉREZ"]
    assert "2 cédulas" in r["mensaje"]

    textos = [_texto(a) for a in r["archivos"]]
    # La carátula del cuerpo nombra a la demandada en las DOS cédulas, así que
    # para saber a quién va cada una hay que mirar el encabezado (antes de
    # "Hago saber"), que es donde va el nombre y el domicilio del notificado.
    cabeceras = [t.split("Hago saber")[0] for t in textos]
    juridica = next(c for c in cabeceras if "SEGUROS EJEMPLO S.A." in c)
    fisica = next(c for c in cabeceras if "Mitre 100" in c)

    assert "PÉREZ" not in juridica
    assert "Domicilio" not in juridica          # persona jurídica: no se imprime
    assert "Domicilio" in fisica                # persona física: sí


def test_un_solo_destinatario_da_una_sola_cedula(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "registrar_cedula", lambda e: None)
    monkeypatch.setattr(generar_cedula, "CARPETA_CEDULAS_TEMP", str(tmp_path))

    r = acciones.cedula({
        "texto": DECRETO,
        "destinatarios": [{"nombre": "SEGUROS EJEMPLO S.A.", "domicilio": ""}],
    })
    assert len(r["archivos"]) == 1
    assert "generada" in r["mensaje"]
