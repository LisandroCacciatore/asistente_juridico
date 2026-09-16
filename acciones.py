# -*- coding: utf-8 -*-
# ============================================================
#  ACCIONES.PY — Motor del panel "Acciones del secretario"
# ------------------------------------------------------------
#  Cada acción del dashboard entra por acá. Hay dos motores:
#
#    local       → un script del repo, determinista y sin IA.
#                  (cédula desde texto, apertura de cuenta judicial)
#
#    secretario  → hace falta INTERPRETAR un texto (un decreto, una
#                  demanda, un informe de saldos), así que lo resuelve
#                  Hermes cargando la skill del estudio. Corre en un
#                  proceso aparte, acotado en turnos y en tiempo.
#
#  Regla que no se rompe: el secretario PREPARA. No firma, no presenta
#  y no envía: los mails quedan como borradores y los actos
#  irreversibles son del abogado.
# ============================================================

import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE, "skills")


class AccionError(Exception):
    """Falla prevista de una acción: el mensaje se muestra tal cual."""


def _correr(cmd, timeout=900, cwd=BASE, env_extra=None):
    """Corre un proceso y mata TODO el árbol si se pasa de tiempo.

    En Windows los nietos (node, Chrome de Playwright) sobreviven si se
    mata solo el proceso padre: hay que matar el árbol con taskkill /T /F,
    o el job queda colgado para siempre.
    """
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)

    p = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                           capture_output=True)
        else:
            p.kill()
        p.communicate()
        raise AccionError(
            f"Se pasó de {timeout // 60} minutos y lo corté. "
            "Revisá la ventana de Chrome y volvé a intentar."
        )
    return p.returncode, (out or "").strip()


# ============================================================
#  Motor local
# ============================================================

def _demandado_de_caratula(caratula):
    """Saca la parte demandada del «X c/ Y s/ Z» de la carátula."""
    m = re.search(r"\bc\s*/\s*(.+?)\s+s\s*/", caratula or "", re.I)
    return m.group(1).strip() if m else ""


def _destinatarios_de_datos(datos, caratula):
    """A quién va la cédula, según lo que se tildó en el panel (D8).

    Si el panel mandó la lista, se respeta tal cual (es la decisión del
    abogado). Si no vino nada —una corrida por consola, la skill vieja—
    se mantiene el comportamiento de siempre: la parte demandada.
    """
    elegidos = datos.get("destinatarios")
    if isinstance(elegidos, list):
        limpios = []
        for d in elegidos:
            if isinstance(d, dict):
                nombre = (d.get("nombre") or "").strip()
                domicilio = (d.get("domicilio") or "").strip()
            else:
                nombre, domicilio = str(d).strip(), ""
            if nombre:
                limpios.append({"nombre": nombre, "domicilio": domicilio})
        if limpios:
            return limpios
    return [{"nombre": _demandado_de_caratula(caratula), "domicilio": "Domicilio constituido"}]


def detectar_destinatarios(datos, pausar=None):
    """Lee el decreto pegado y dice a quién habría que notificar.

    Es el paso previo que pide D8: mostrar la lista para que el abogado
    confirme ANTES de que exista un PDF. No genera nada, no registra
    nada y no toca ningún portal — es sólo lectura del texto.

    Devuelve también lo que se interpretó (carátula, CUIJ, fuero,
    ciudad) para que la confirmación sea sobre datos concretos y no
    sobre un "confiá en mí".
    """
    from cedula_desde_texto import (
        es_sentencia, extraer_caratula, extraer_cuij, extraer_juzgado,
        extraer_ciudad, extraer_fuero, extraer_destinatarios, extraer_peritos,
    )
    from cedulas import es_designacion_perito

    texto = (datos.get("texto") or "").strip()
    if len(texto) < 40:
        raise AccionError("Pegá el decreto completo: encabezado, fecha y parte resolutiva.")

    caratula = extraer_caratula(texto)

    # Domicilio común por defecto: el que el repo venía imprimiendo. Cada
    # fila lo puede pisar desde el panel, y vacío = no se imprime.
    dom = (datos.get("domicilio") or "Domicilio constituido").strip()

    # La cédula de peritos va AL PERITO (así lo dice el acta del sorteo), no a
    # las partes de la carátula: si se ofrecieran las partes, el abogado
    # generaría una cédula a nombre de quien no corresponde.
    if es_designacion_perito(texto):
        peritos = [dict(p, rol="Perito designado (acta del sorteo)", origen="acta",
                        domicilio=p.get("domicilio") or dom)
                   for p in extraer_peritos(texto)]
        return {
            "ok": True,
            "caratula": caratula,
            "cuij": extraer_cuij(texto),
            "juzgado": extraer_juzgado(texto),
            "fuero": extraer_fuero(texto) or "LABORAL",
            "ciudad": extraer_ciudad(texto) or "ROSARIO",
            "es_sentencia": es_sentencia(texto),
            "tipo": "peritos",
            "destinatarios": peritos,
            "aviso": "" if peritos else (
                "Es una designación de perito, pero no pude separar los nombres del "
                "acta. Escribilos a mano abajo."
            ),
        }

    detectados = extraer_destinatarios(texto, caratula) if caratula else []
    for d in detectados:
        d["domicilio"] = dom

    return {
        "ok": True,
        "caratula": caratula,
        "cuij": extraer_cuij(texto),
        "juzgado": extraer_juzgado(texto),
        "fuero": extraer_fuero(texto) or "LABORAL",
        "ciudad": extraer_ciudad(texto) or "ROSARIO",
        "es_sentencia": es_sentencia(texto),
        "destinatarios": detectados,
        "aviso": "" if caratula else (
            "No pude leer la carátula del encabezado. Sin carátula la cédula sale sin "
            "el «autos caratulados»: revisá el texto o escribí la carátula a mano."
        ),
    }


def cedula(datos, pausar=None):
    """Cédula a partir del texto pegado. Motor del repo, sin IA."""
    from cedula_desde_texto import (
        es_sentencia, recortar_sentencia, extraer_caratula,
        extraer_cuij, extraer_fecha_decreto, extraer_juzgado,
        extraer_ciudad, extraer_fuero,
    )
    import generar_cedula

    texto = (datos.get("texto") or "").strip()
    if len(texto) < 40:
        raise AccionError("Pegá el decreto completo: encabezado, fecha y parte resolutiva.")

    es_sent = es_sentencia(texto)
    recortado = recortar_sentencia(texto) if es_sent else texto

    caratula = extraer_caratula(texto) or extraer_caratula(recortado)
    if not caratula:
        raise AccionError(
            "No pude leer la carátula. Pegá el encabezado del decreto, "
            "donde dice «APELLIDO c/ PARTE s/ OBJETO»."
        )
    cuij = extraer_cuij(texto)
    fecha = extraer_fecha_decreto(texto)
    juzgado = extraer_juzgado(texto)
    destinatarios = _destinatarios_de_datos(datos, caratula)

    entrada = {
        "caratula": caratula,
        "cuij": cuij,
        "fecha_decreto": fecha,
        "texto_decreto": recortado,
        "juzgado": juzgado,
        "tipo": "auto",                     # lo deducen las reglas del repo
        "destinatarios": destinatarios,
    }

    # Ciudad y fuero solo si se detectaron: si se pasaran vacíos, la plantilla
    # los tomaría como dato válido e imprimiría un hueco en vez de su default.
    ciudad = extraer_ciudad(texto)
    if ciudad:
        entrada["ciudad"] = ciudad
    fuero = extraer_fuero(texto)
    if fuero:
        entrada["fuero"] = fuero
    registradas = generar_cedula.generar(entrada)
    if not registradas:
        raise AccionError("El generador no devolvió ninguna cédula.")

    primera = registradas[0]
    cuantas = len(registradas)
    etiqueta = primera.get("tipoLabel", "Cédula")
    mensaje = (
        f"{etiqueta} generada — revisala en «Listas para firmar»" if cuantas == 1
        else f"{cuantas} cédulas generadas — revisalas en «Listas para firmar»"
    )
    return {
        "ok": True,
        "mensaje": mensaje,
        "generadas": [r.get("id") for r in registradas],
        "caratula": caratula,
        "cuij": cuij,
        "destinatario": destinatarios[0]["nombre"],
        "destinatarios": [d["nombre"] for d in destinatarios],
        "recortada": es_sent,
        "archivos": [r.get("ruta_pdf") for r in registradas],
    }


def cuenta(datos, pausar=None):
    """Apertura de cuenta judicial en el Banco Municipal (Playwright)."""
    cuij = (datos.get("cuij") or "").strip()
    if not re.fullmatch(r"21-\d{8}-\d", cuij):
        raise AccionError("El CUIJ va con el formato 21-00000001-0.")

    script = os.path.join(
        SKILLS_DIR, "apertura-cuenta-judicial-banco-municipal",
        "scripts", "apertura_cuenta_judicial.py",
    )
    if not os.path.isfile(script):
        raise AccionError("No encuentro el script de apertura de cuenta en el repo.")

    salida = os.path.join(tempfile.gettempdir(), "aj_cuenta_" + cuij.replace("-", "_"))
    os.makedirs(salida, exist_ok=True)
    cmd = [sys.executable, script, "--cuij", cuij, "--out", salida]
    if (datos.get("caratula") or "").strip():
        cmd += ["--caratula", datos["caratula"].strip()]

    if pausar:
        pausar("Se va a abrir el SISFE con tu perfil de Chrome.\n"
               "Si te pide iniciar sesión, hacelo en la ventana y apretá «Ya está, continuar».")

    rc, out = _correr(cmd, timeout=900)
    if rc != 0:
        raise AccionError(f"El script terminó con error (código {rc}).\n{out[-600:]}")

    archivos = []
    if os.path.isdir(salida):
        archivos = sorted(f for f in os.listdir(salida)
                          if f.lower().endswith((".pdf", ".png")))
    return {
        "ok": True,
        "mensaje": "Capturas tomadas y PDF armado — listo para el mail al Banco",
        "salida": salida,
        "archivos": archivos,
        "detalle": out[-400:],
    }


# ============================================================
#  Motor "secretario": Hermes con la skill del estudio
# ============================================================
#  Las skills viven en skills/ como texto: es el procedimiento que
#  escribió el estudio. En vez de depender de que Hermes las tenga
#  instaladas, el procedimiento viaja DENTRO del pedido (--query-file,
#  que no interpreta nada de shell). Así la única fuente de verdad
#  sigue siendo skills/ del repo.
_SKILLS_SECRETARIO = {
    "art":           ("cliente-art-nuevo",              "Alta de un cliente nuevo de ART"),
    "boletas":       ("oficio-incumplimiento-boletas",  "Oficios por incumplimiento de boletas"),
    "raeo":          ("oficio-raeo",                    "Oficio al RAEO"),
    "transferencia": ("transferencia-de-capital",       "Transferencia de capital"),
}


def _texto_skill(nombre):
    """Lee el procedimiento de una skill del repo (archivo suelto o carpeta)."""
    candidatos = [
        os.path.join(SKILLS_DIR, nombre, "SKILL.md"),
        os.path.join(SKILLS_DIR, nombre + ".md"),
    ]
    for ruta in candidatos:
        if os.path.isfile(ruta):
            with open(ruta, encoding="utf-8") as f:
                return f.read()
    raise AccionError(f"No encuentro el procedimiento de la skill «{nombre}» en skills/.")


_PROMPT = """Sos el secretario del estudio del Dr. Santiago Segovia. Estás corriendo en la carpeta
del repo asistente_juridico, en la misma máquina donde está el estudio.

SEGUÍ AL PIE DE LA LETRA EL SIGUIENTE PROCEDIMIENTO:
============================================================
{procedimiento}
============================================================

Datos que aportó el abogado ({titulo}):
---8<---
{texto}
---8<---

Reglas que no podés romper, aunque el procedimiento diga otra cosa:
- Escribí TODOS los archivos de salida en: {carpeta}
- NO envíes ningún mail. Si el procedimiento pide dejar un mail, creá un BORRADOR en Gmail
  y nada más: el envío es un acto del abogado.
- No firmes, no presentes y no abras portales: esos actos son del abogado.
- Usá las plantillas y los scripts que ya están en el repo; no inventes formatos nuevos.

Cuando termines, respondé en 3 líneas como máximo:
1) qué archivos generaste (con la ruta completa),
2) qué datos faltaron o quedaron dudosos,
3) qué tiene que hacer el abogado a mano.
"""


def secretario(accion, datos, pausar=None):
    """Corre Hermes en un proceso aparte con el procedimiento de la skill."""
    skill, titulo = _SKILLS_SECRETARIO[accion]
    texto = (datos.get("texto") or "").strip()
    if len(texto) < 30:
        raise AccionError("Pegá el texto completo: el secretario necesita leerlo para armar los documentos.")

    carpeta = os.path.join(tempfile.gettempdir(), f"aj_{accion}")
    os.makedirs(carpeta, exist_ok=True)

    if pausar:
        pausar("El secretario está armando los documentos.\nPuede tardar un par de minutos.")

    prompt = _PROMPT.format(
        procedimiento=_texto_skill(skill), titulo=titulo, texto=texto, carpeta=carpeta,
    )
    ruta_prompt = os.path.join(carpeta, "pedido.txt")
    with open(ruta_prompt, "w", encoding="utf-8") as f:
        f.write(prompt)

    exe = shutil.which("hermes") or "hermes"
    cmd = [
        exe, "chat",
        "--query-file", ruta_prompt,   # el texto no se interpreta: va tal cual
        "-Q",                          # solo la respuesta final
        "--in", BASE,
        "--max-turns", "30",           # acotado: no es una sesión abierta
        "--run-budget", "600",
    ]
    rc, out = _correr(cmd, timeout=700, cwd=BASE)
    if rc != 0:
        raise AccionError(
            "El secretario no pudo terminar el trabajo.\n" + (out[-700:] or f"código {rc}")
        )

    archivos = []
    for nombre in sorted(os.listdir(carpeta)):
        if nombre.lower().endswith((".pdf", ".docx", ".doc", ".json", ".txt")) and nombre != "pedido.txt":
            archivos.append(nombre)
    return {
        "ok": True,
        "mensaje": f"{titulo}: el secretario dejó {len(archivos) or 'los'} archivo(s) listos",
        "salida": carpeta,
        "archivos": archivos,
        "detalle": out[-600:],
    }


# ============================================================
#  Dispatcher
# ============================================================

def ejecutar(accion, datos, pausar=None):
    """Corre una acción del panel y devuelve su resultado."""
    if accion == "destinatarios":
        return detectar_destinatarios(datos, pausar)
    if accion == "cedula":
        return cedula(datos, pausar)
    if accion == "cuenta":
        return cuenta(datos, pausar)
    if accion in _SKILLS_SECRETARIO:
        return secretario(accion, datos, pausar)
    raise AccionError(f"Acción desconocida: {accion}")


if __name__ == "__main__":
    import json

    if len(sys.argv) < 3:
        print("Uso: python acciones.py <cedula|cuenta|art|boletas|raeo|transferencia> datos.json")
        raise SystemExit(1)
    with open(sys.argv[2], encoding="utf-8") as f:
        print(json.dumps(ejecutar(sys.argv[1], json.load(f)), ensure_ascii=False, indent=2))
