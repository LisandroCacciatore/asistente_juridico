# -*- coding: utf-8 -*-
# ============================================================
#  GENERAR_CEDULA.PY — Generador de cédulas Nivel 1 (sin IA)
# ------------------------------------------------------------
#  Toma datos ya estructurados (de un JSON o del formulario del
#  dashboard), arma el PDF con TUS módulos existentes y lo registra
#  en estado.json. NO usa Claude ni ninguna IA.
#
#  Clasificación del tipo de cédula:
#    - "auto"        -> la deducen tus reglas (cedulas.py)
#    - "estandar"    -> cédula estándar
#    - "aud51"       -> audiencia Art. 51 CPL
#    - "bus_federal" -> Bus Federal (Ley 22.172)
#    - "traslado"    -> primer decreto / traslado de demanda
#
#  USO:
#     python generar_cedula.py entrada.json
# ============================================================

import os
import re
import sys
import json

from cedulas_pdf import guardar_cedula_pdf
from expediente_utils import datos_del_juzgado
from config import CARPETA_CEDULAS_TEMP
import cedulas          # reglas de clasificación (sin IA)
import estado           # registro estado.json


# --- Etiquetas de cada tipo para el dashboard --------------------
_TIPOS = {
    "estandar":    {"tipo": "estandar",  "label": "Cédula estándar",           "ic": "📄"},
    "aud51":       {"tipo": "aud",       "label": "Audiencia Art. 51 CPL",     "ic": "🛡"},
    "bus_federal": {"tipo": "bus",       "label": "Bus Federal — Ley 22.172",  "ic": "🔒"},
    "traslado":    {"tipo": "traslado",  "label": "Traslado de demanda",       "ic": "⚖"},
    "peritos":     {"tipo": "peritos",   "label": "Perito (arts. 78 y 79)",   "ic": "🔬"},
}


def clasificar_por_reglas(texto_decreto, novedad=""):
    """Deduce el tipo de cédula con TUS reglas (sin IA). Devuelve la clave de _TIPOS."""
    if cedulas.es_bus_federal(texto_decreto, novedad):
        return "bus_federal"
    if cedulas.es_designacion_perito(texto_decreto):
        return "peritos"
    if cedulas.es_decreto_audiencia_51(texto_decreto):
        return "aud51"
    if cedulas.es_primer_decreto(texto_decreto):
        return "traslado"
    return "estandar"


def _id_cedula(caratula, cuij, n):
    """id corto y único: apellido + últimos dígitos del CUIJ + índice."""
    m = re.match(r'^\s*([A-Za-zÁÉÍÓÚÑáéíóúñ]+)', caratula or "")
    ape = (m.group(1).lower() if m else "cedula")
    cola = re.sub(r'\D', '', cuij or "")[-6:]
    return f"{ape}_{cola}_{n}" if n > 1 else f"{ape}_{cola}"


def generar(entrada, salida_dir=None):
    """
    entrada: dict con los datos de la cédula (ver ejemplo en __main__).
    salida_dir: carpeta de salida. Si es None, usa tu estructura de carpetas
                (encontrar_carpeta_expediente). Útil pasarla en pruebas.
    Devuelve la lista de entradas registradas en estado.json.
    """
    caratula = entrada.get("caratula", "")
    cuij = entrada.get("cuij", "")
    ciudad = entrada.get("ciudad", "Rosario")
    fecha_decreto = entrada.get("fecha_decreto", "")
    texto_decreto = entrada.get("texto_decreto", "")
    novedad = entrada.get("novedad", "")

    # 1) Juez / secretario / nominación: del "Radicado en:" o provistos a mano
    if entrada.get("radicado"):
        nom, juez, sec, cargo_j, cargo_s = datos_del_juzgado(entrada["radicado"])
    else:
        nom = entrada.get("nominacion", "")
        juez = entrada.get("juez", "")
        sec = entrada.get("secretario", "")
        cargo_j = entrada.get("cargo_juez", "JUEZ")
        cargo_s = entrada.get("cargo_secretario", "SECRETARIO")
    juzgado_txt = entrada.get("juzgado") or (f"Laboral {nom}ª Nom. — {ciudad}" if nom else ciudad)

    # 2) Tipo de cédula: manual o por reglas
    tipo = entrada.get("tipo", "auto")
    if tipo == "auto":
        tipo = clasificar_por_reglas(texto_decreto, novedad)
    if tipo not in _TIPOS:
        tipo = "estandar"
    meta = _TIPOS[tipo]
    es_aud51 = (tipo == "aud51")
    es_bus = (tipo == "bus_federal")
    es_peritos = (tipo == "peritos")

    # 3) Destinatarios: provistos a mano (Nivel 1). Si no hay, uno en blanco.
    destinatarios = entrada.get("destinatarios") or [{"nombre": "", "domicilio": ""}]

    # 4) Carpeta de salida: genérica y temporal, por CUIJ. No busca la
    #    carpeta del cliente — el PDF es transitorio (se borra al
    #    presentarse en Meta Jurídico; ver estado.marcar_presentada).
    cuij_limpio = re.sub(r'[^\w-]', '', cuij or "sin-cuij")
    carpeta = salida_dir or os.path.join(CARPETA_CEDULAS_TEMP, cuij_limpio)
    os.makedirs(carpeta, exist_ok=True)

    registradas = []
    for i, dest in enumerate(destinatarios, start=1):
        datos = {
            "juez": juez, "secretario": sec, "nominacion": nom, "ciudad": ciudad,
            "cargo_juez": cargo_j, "cargo_secretario": cargo_s,
            "caratula": caratula, "cuij": cuij,
            "fecha_decreto": fecha_decreto, "texto_decreto": texto_decreto,
            "destinatario_nombre": dest.get("nombre", ""),
            "destinatario_domicilio": dest.get("domicilio", ""),
            # extras para audiencia 51
            "actor": entrada.get("actor", ""),
            "demandado": entrada.get("demandado", ""),
            "objeto": entrada.get("objeto", ""),
            "fecha_audiencia": entrada.get("fecha_audiencia", ""),
            "hora_audiencia": entrada.get("hora_audiencia", ""),
        }
        ruta_pdf = guardar_cedula_pdf(
            datos, carpeta, es_aud51=es_aud51, es_bus_federal=es_bus,
            es_peritos=es_peritos,
            fecha_archivo=fecha_decreto, novedad=novedad,
        )

        entry = {
            "id": _id_cedula(caratula, cuij, i),
            "caratula": caratula,
            "tipo": meta["tipo"], "tipoLabel": meta["label"], "ic": meta["ic"],
            "cuij": cuij, "juzgado": juzgado_txt,
            "juez": (f"Dr./Dra. {juez}" if juez else ""),
            "dest": [{"n": dest.get("nombre", ""), "d": dest.get("domicilio", "")}],
            "ruta_pdf": os.path.abspath(ruta_pdf),
            "ruta_firmada": None,
            "estado": "generada",
            # De quién es esta cédula (SPEC D25): de qué sesión del SISFE
            # salieron los decretos. Se graba acá y no se cambia; si no se
            # sabe, queda vacío y se fija en el primer acto del portal.
            "identidad_cadena": entrada.get("identidad_cadena", ""),
        }
        estado.registrar_cedula(entry)
        registradas.append(entry)
        print(f"  ✓ Cédula generada: {os.path.basename(ruta_pdf)}")

    print(f"  ✓ {len(registradas)} cédula(s) registrada(s) en estado.json")
    return registradas


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        with open(sys.argv[1], encoding="utf-8") as f:
            entrada = json.load(f)
        generar(entrada)
    else:
        print('  Uso: python generar_cedula.py entrada.json')
