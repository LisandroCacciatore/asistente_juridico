#!/usr/bin/env python3
"""auditoria_skills.py - El cuadro del uso de skills de Hermes.

Responde tres preguntas distintas, que es lo que se mezcla cuando alguien
dice "que skills se usaron":

  CAPA A - CONSULTADAS : lo que el agente abrio para leer (skill_view).
                         Fuente: state.db, tabla messages.
  CAPA B - APRENDIDAS  : lo que el curator escribio DENTRO de las skills a
                         partir de las sesiones. Fuente: .curator_ledger.jsonl.
  CAPA C - DEL PROYECTO: los procedimientos del repo que Hermes ejecuta
                         headless (no viven en Hermes, viven en skills/ del repo).

Ojo con dos trampas del registro (verificado 17/09/2026):
  1. `messages` guarda UNA COPIA POR COMPACTACION del mismo mensaje. Contar
     filas infla todo. La clave estable de una llamada es `tool_call_id`.
     Por eso se agrupa por tool_call_id y no por fila.
  2. El contador global .usage.json NO mide consultas: se mueve junto con lo
     que escribe el curator (mismo numero de patches). Aca se usa solo para
     el inventario, nunca como prueba de uso.

Uso:
    python dev/auditoria_skills.py                    # el cuadro completo
    python dev/auditoria_skills.py --sesion ultima    # solo la ultima sesion
    python dev/auditoria_skills.py --skill repo-audit
    python dev/auditoria_skills.py --desde 16/09/2026
    python dev/auditoria_skills.py --json             # machine-readable
    python dev/auditoria_skills.py --md               # tabla markdown

Solo lee: abre las bases en modo read-only y nunca escribe en Hermes.
"""

import argparse
import collections
import datetime
import glob
import io
import json
import os
import re
import sqlite3
import sys

# ---------------------------------------------------------------- ubicaciones

def casas_hermes():
    """Hermes puede vivir en dos casas: el perfil instalado y ~/.hermes."""
    out = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        out.append(os.path.join(local, "hermes"))
    out.append(os.path.join(os.path.expanduser("~"), ".hermes"))
    return [c for c in out if os.path.isdir(c)]


def raiz_repo():
    """Si el script vive en <repo>/dev/, el repo es la carpeta de arriba."""
    aqui = os.path.dirname(os.path.abspath(__file__))
    padre = os.path.dirname(aqui)
    if os.path.isdir(os.path.join(padre, "skills")):
        return padre
    return os.path.dirname(padre) if os.path.basename(aqui) == "dev" else aqui


# ------------------------------------------------------------------ utilidades

def local(ts):
    try:
        return datetime.datetime.fromtimestamp(float(ts))
    except (TypeError, ValueError):
        return None


def fch(ts, fmt="%d/%m %H:%M"):
    d = local(ts)
    return d.strftime(fmt) if d else "-"


def _epoch(iso):
    """Un ts ISO del ledger -> epoch. Si no se entiende, None (no rompe el cuadro)."""
    if not iso:
        return None
    try:
        return datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def rango_ts(registros):
    """(primero, ultimo) de una lista del ledger, tolerando entradas sin ts."""
    ts = [t for t in (_epoch(r.get("ts")) for r in registros) if t]
    return (min(ts), max(ts)) if ts else (None, None)


def fecha_de(texto):
    """'16/09/2026' o '16/09' -> datetime (asume el anio actual)."""
    for f in ("%d/%m/%Y", "%d/%m/%y", "%d/%m"):
        try:
            d = datetime.datetime.strptime(texto, f)
            return d.replace(year=datetime.date.today().year) if f == "%d/%m" else d
        except ValueError:
            continue
    raise SystemExit("Fecha no entendida: %s (usá 16/09/2026 o 16/09)" % texto)


def abrir_sqlite(ruta):
    """Abre read-only: el audit no puede tocar la base viva de Hermes."""
    if not os.path.isfile(ruta):
        return None
    try:
        return sqlite3.connect("file:%s?mode=ro" % ruta.replace("\\", "/"), uri=True)
    except sqlite3.Error:
        return None


def utf8_out():
    """La consola de Windows viene en cp1252: forzar utf-8, sin romper si no se puede."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def nombre_de_skill(texto):
    """El nombre sale del JSON completo o del resumen ya podado."""
    if not texto:
        return "(sin nombre)"
    for pat in (r'"name"\s*:\s*"([^"]+)"', r'\[skill_[a-z_]+\]\s*name=([^\s(]+)', r'name=([^\s()]+)'):
        m = re.search(pat, texto)
        if m:
            return m.group(1)
    return "(sin nombre)"


# ------------------------------------------------------------------- CAPA A

def leer_consultas(home, sesion=None, desde=None, skill=None):
    """skill_view / skill_manage / skills_list: una fila por LLAMADA distinta."""
    db = abrir_sqlite(os.path.join(home, "state.db"))
    if not db:
        return [], {}
    cur = db.cursor()

    # 1) La LLAMADA manda: el nombre y la accion salen de los argumentos. Un
    #    resultado fallido no trae el nombre (y un skill_view de nombre vacio
    #    tampoco), asi que leerlo del resultado deja llamadas sin identificar.
    llamadas = {}
    try:
        filas_call = list(cur.execute(
            "select session_id, tool_calls, timestamp from messages "
            "where tool_calls like '%\"skill_view\"%' or tool_calls like '%\"skill_manage\"%' "
            "or tool_calls like '%\"skills_list\"%'"))
    except sqlite3.Error:
        filas_call = []
    for sid, tc, ts in filas_call:
        try:
            items = json.loads(tc or "[]") or []
        except ValueError:
            continue
        for it in items:
            fn = it.get("function") or {}
            tool = fn.get("name") or ""
            if not tool.startswith("skill"):
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (ValueError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}
            cid = it.get("id") or it.get("call_id") or "%s|%s" % (sid, ts)
            reg = llamadas.setdefault(cid, {"sesion": sid, "tool": tool, "ts": ts,
                                            "skill": args.get("name") or "",
                                            "accion": args.get("action") or "",
                                            "ok": None, "completo": False})
            if ts and (not reg["ts"] or ts < reg["ts"]):
                reg["ts"] = ts

    # 2) El resultado completa: como termino (ok/fallo) y el nombre de respaldo.
    try:
        filas_res = list(cur.execute(
            "select session_id, tool_name, tool_call_id, timestamp, content "
            "from messages where tool_name like 'skill%' order by id"))
    except sqlite3.Error:
        filas_res = []
    for sid, tool, cid, ts, content in filas_res:
        clave = cid or "%s|%s|%s" % (sid, tool, ts)
        reg = llamadas.setdefault(clave, {"sesion": sid, "tool": tool, "ts": ts,
                                          "skill": "", "accion": "", "ok": None,
                                          "completo": False})
        if ts and (not reg["ts"] or ts < reg["ts"]):
            reg["ts"] = ts
        texto = content or ""
        # la copia mas entera (las podadas dicen "[skill_view] name=X (N chars)")
        if ('"success"' in texto or '"error"' in texto) and not reg["completo"]:
            reg["completo"] = True
            if not reg["skill"]:
                reg["skill"] = nombre_de_skill(texto)
        if '"success": true' in texto:
            reg["ok"] = True
        elif '"success": false' in texto and reg["ok"] is None:
            reg["ok"] = False

    for reg in llamadas.values():
        if reg["tool"] == "skills_list":
            reg["skill"] = "(listado de skills)"
        elif not reg["skill"]:
            reg["skill"] = "(sin nombre)"

    # titulos y actividad de las sesiones, para poder etiquetarlas
    meta = {}
    try:
        for sid, titulo, ini, act in cur.execute(
                "select id, title, started_at, last_activity_at from sessions"):
            meta[sid] = {"titulo": titulo or "", "inicio": ini, "actividad": act}
    except sqlite3.Error:
        pass

    out = []
    for reg in llamadas.values():
        if sesion and reg["sesion"] != sesion:
            continue
        if skill and reg["skill"] != skill:
            continue
        if desde and (not reg["ts"] or local(reg["ts"]) < desde):
            continue
        info = meta.get(reg["sesion"], {})
        reg["titulo"] = info.get("titulo") or ""
        reg["actividad"] = info.get("actividad")
        out.append(reg)
    out.sort(key=lambda r: r["ts"] or 0)
    return out, meta


def ultima_sesion(meta):
    if not meta:
        return None
    vivas = [(i.get("actividad") or 0, sid) for sid, i in meta.items()]
    return max(vivas)[1] if vivas else None


# ------------------------------------------------------------------- CAPA B

def leer_ledger(home, sesion=None, desde=None, skill=None):
    ruta = os.path.join(home, "skills", ".curator_ledger.jsonl")
    if not os.path.isfile(ruta):
        return [], ruta
    vistos, out = set(), []
    for linea in io.open(ruta, encoding="utf-8", errors="replace"):
        linea = linea.strip()
        if not linea:
            continue
        try:
            r = json.loads(linea)
        except ValueError:
            continue
        rid = r.get("id")
        if rid and rid in vistos:
            continue
        if rid:
            vistos.add(rid)
        r["_sesion"] = (r.get("evidence") or {}).get("session_id") or ""
        r["_archivo"] = (r.get("evidence") or {}).get("file_path") or ""
        if sesion and r["_sesion"] != sesion:
            continue
        if skill and r.get("skill") != skill:
            continue
        if desde:
            try:
                cuando = datetime.datetime.fromisoformat(str(r["ts"]).replace("Z", "+00:00")).astimezone()
            except (KeyError, ValueError):
                cuando = None
            if not cuando or cuando.replace(tzinfo=None) < desde:
                continue
        out.append(r)
    out.sort(key=lambda r: r.get("ts") or "")
    return out, ruta


# ------------------------------------------------------------------- CAPA C

def leer_skills_del_repo(repo):
    carpeta = os.path.join(repo, "skills")
    if not os.path.isdir(carpeta):
        return [], carpeta
    # que procedimientos expone el panel (acciones.py -> _SKILLS_SECRETARIO)
    expuestos = {}
    acciones = os.path.join(repo, "acciones.py")
    if os.path.isfile(acciones):
        txt = io.open(acciones, encoding="utf-8", errors="replace").read()
        bloque = re.search(r"_SKILLS_SECRETARIO\s*=\s*\{(.*?)\}", txt, re.S)
        if bloque:
            for clave, carpeta_skill, titulo in re.findall(
                    r'"([^"]+)"\s*:\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"', bloque.group(1)):
                expuestos[carpeta_skill] = (clave, titulo)

    out = []
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*"))):
        nombre = os.path.basename(ruta)
        if os.path.isdir(ruta):
            proc = os.path.join(ruta, "SKILL.md")
            if not os.path.isfile(proc):
                continue
            archivo, kb = proc, os.path.getsize(proc) / 1024.0
        elif ruta.endswith((".md", ".json")):
            archivo, kb = ruta, os.path.getsize(ruta) / 1024.0
        else:
            continue
        es_json = archivo.endswith(".json")
        # el panel referencia la skill por su nombre sin extension
        clave = nombre[:-3] if nombre.endswith(".md") else nombre
        out.append({
            "nombre": nombre,
            "archivo": os.path.relpath(archivo, repo).replace("\\", "/"),
            "kb": kb,
            "modificado": os.path.getmtime(archivo),
            "panel": expuestos.get(clave),
            "tipo": "dato" if es_json else "procedimiento",
        })
    return out, carpeta


# ------------------------------------------------------------------- inventario

def inventario(casas):
    inv = {"casas": casas, "por_casa": {}, "registro_uso": 0, "sdd": 0}
    for casa in casas:
        skills = os.path.join(casa, "skills")
        n, sdd = 0, 0
        if os.path.isdir(skills):
            for ruta in glob.glob(os.path.join(skills, "**", "SKILL.md"), recursive=True):
                n += 1
                if os.path.basename(os.path.dirname(ruta)).startswith("sdd-"):
                    sdd += 1
        reg = os.path.join(skills, ".usage.json")
        usados = 0
        if os.path.isfile(reg):
            try:
                usados = len(json.load(io.open(reg, encoding="utf-8")))
            except (ValueError, OSError):
                usados = 0
        inv["por_casa"][casa] = {"skills": n, "sdd": sdd, "registro_uso": usados}
        inv["registro_uso"] = max(inv["registro_uso"], usados)
        inv["sdd"] = max(inv["sdd"], sdd)
    return inv


# ------------------------------------------------------------------- salida

def salida_texto(cuadro):
    L = []
    utf8_out()
    inv, cons, led, rep, meta = cuadro["inventario"], cuadro["consultas"], cuadro["ledger"], cuadro["repo"], cuadro["sesiones"]
    L.append("=" * 78)
    L.append("AUDITORIA DE SKILLS - Hermes")
    L.append("  %s   |   perfil: %s" % (datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), cuadro["perfil"]))
    for casa in inv["casas"]:
        d = inv["por_casa"][casa]
        L.append("  casa: %-46s %3d skills (%d sdd)" % (casa, d["skills"], d["sdd"]))
    if cuadro["filtros"]:
        L.append("  filtros: %s" % cuadro["filtros"])
    L.append("=" * 78)

    L.append("")
    L.append("CAPA A - CONSULTADAS (skill_view)          fuente: state.db")
    if not cons:
        L.append("  (ninguna consulta con estos filtros)")
    else:
        L.append("  %d llamadas distintas   %d skills distintas   %d sesiones"
                 % (len(cons), len({c["skill"] for c in cons}), len({c["sesion"] for c in cons})))
        vistas = sum(1 for c in cons if c["tool"] == "skill_view")
        escrituras = sum(1 for c in cons if c["tool"] == "skill_manage")
        fallidas = sum(1 for c in cons if c["ok"] is False)
        L.append("  %d lecturas (skill_view)   %d escrituras (skill_manage)   %d fallidas"
                 % (vistas, escrituras, fallidas))
        L.append("  %-34s %4s %4s %4s %-13s %-13s %s"
                 % ("skill", "n", "lec", "esc", "primera", "ultima", "sesion"))
        agrup = collections.defaultdict(list)
        for c in cons:
            agrup[c["skill"]].append(c)
        for sk, cs in sorted(agrup.items(), key=lambda kv: max(x["ts"] or 0 for x in kv[1]), reverse=True):
            ses = sorted({x["sesion"] for x in cs})
            L.append("  %-34s %4d %4d %4d %-13s %-13s %s%s" % (
                sk, len(cs),
                sum(1 for x in cs if x["tool"] == "skill_view"),
                sum(1 for x in cs if x["tool"] == "skill_manage"),
                fch(min(x["ts"] or 0 for x in cs)), fch(max(x["ts"] or 0 for x in cs)),
                ses[0] if len(ses) == 1 else "%d sesiones" % len(ses),
                "  (" + (meta.get(ses[0], {}).get("titulo") or "")[:24] + ")" if len(ses) == 1 else ""))

    L.append("")
    L.append("CAPA B - APRENDIDAS (ledger del curator)   fuente: .curator_ledger.jsonl")
    if not led:
        L.append("  (sin entradas con estos filtros)")
    else:
        creadas = sum(1 for r in led if r.get("action") == "create")
        L.append("  %d entradas   %d skills tocadas   %d creadas de cero"
                 % (len(led), len({r.get("skill") for r in led}), creadas))
        L.append("  %-32s %5s %5s %-13s %-13s %s" % ("skill", "escr", "crea", "primera", "ultima", "sesion"))
        agrup = collections.defaultdict(list)
        for r in led:
            agrup[r.get("skill")].append(r)
        orden = sorted(agrup.items(), key=lambda kv: max(x.get("ts") or "" for x in kv[1]), reverse=True)
        for sk, rs in orden[:cuadro["top"]]:
            cre = sum(1 for x in rs if x.get("action") == "create")
            ses = sorted({x["_sesion"] for x in rs if x["_sesion"]})
            pri, ult = rango_ts(rs)
            L.append("  %-32s %5d %5d %-13s %-13s %s" % (
                sk, len(rs), cre, fch(pri), fch(ult),
                ses[0] if len(ses) == 1 else "%d sesiones" % len(ses)))
        if len(orden) > cuadro["top"]:
            L.append("  ... %d skills mas" % (len(orden) - cuadro["top"]))

    L.append("")
    L.append("POR SESION                               (filas != mensajes: hay copias)")
    por_ses = collections.defaultdict(lambda: {"c": 0, "e": 0})
    for c in cons:
        por_ses[c["sesion"]]["c"] += 1
    for r in led:
        if r["_sesion"]:
            por_ses[r["_sesion"]]["e"] += 1
    if not por_ses:
        L.append("  (nada)")
    else:
        L.append("  %-24s %-28s %6s %6s %6s" % ("sesion", "titulo", "consult", "escrit", "activa"))
        for sid, d in sorted(por_ses.items(), key=lambda kv: (meta.get(kv[0], {}).get("actividad") or 0), reverse=True)[:8]:
            L.append("  %-24s %-28s %6d %6d %6s" % (sid, (meta.get(sid, {}).get("titulo") or "")[:28],
                                                     d["c"], d["e"], fch(meta.get(sid, {}).get("actividad"))))

    L.append("")
    L.append("CAPA C - SKILLS DEL PROYECTO (las ejecuta Hermes)   repo: %s" % cuadro["repo_raiz"])
    if not rep:
        L.append("  (no encontre skills/ en ese repo)")
    else:
        L.append("  %-42s %-16s %8s %-13s %s" % ("procedimiento", "tipo", "kb", "modificado", "panel"))
        for s in rep:
            L.append("  %-42s %-16s %8.1f %-13s %s" % (
                s["nombre"][:42], s["tipo"], s["kb"], fch(s["modificado"]),
                ("si: %s" % s["panel"][0]) if s["panel"] else "-"))

    L.append("")
    L.append("INVENTARIO")
    L.append("  skills en el registro de uso ....... %d" % inv["registro_uso"])
    L.append("  familia SDD (Gentle AI) instalada .. %d  (2 de las casas pueden repetir)" % inv["sdd"])
    L.append("  ledger del curator ................. %d entradas totales" % cuadro["ledger_total"])
    L.append("")
    return "\n".join(L)


def salida_md(cuadro):
    L = ["## Auditoría de skills — %s" % datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), ""]
    L.append("| Capa | Qué es | Registro |")
    L.append("|---|---|---|")
    L.append("| A | Consultadas (`skill_view`) | `state.db` |")
    L.append("| B | Aprendidas (escribe el curator) | `.curator_ledger.jsonl` |")
    L.append("| C | Del proyecto (las ejecuta Hermes) | `skills/` del repo |")
    L.append("")
    for titulo, cons in (("A — Consultadas", cuadro["consultas"]),
                         ("B — Aprendidas", cuadro["ledger"])):
        L += ["### %s" % titulo, ""]
        agrup = collections.defaultdict(list)
        for c in cons:
            agrup[c.get("skill")].append(c)
        if not agrup:
            L += ["_(sin datos)_", ""]
            continue
        L += ["| skill | veces | primera | última |", "|---|---|---|---|"]
        for sk, cs in sorted(agrup.items(), key=lambda kv: len(kv[1]), reverse=True):
            if isinstance(cs[0].get("ts"), (int, float)):
                pri, ult = fch(min(x["ts"] for x in cs if x.get("ts"))), fch(max(x["ts"] for x in cs if x.get("ts")))
            else:
                prim, ultm = rango_ts(cs)
                pri, ult = fch(prim), fch(ultm)
            L.append("| `%s` | %d | %s | %s |" % (sk, len(cs), pri, ult))
        L.append("")
    rep = cuadro["repo"]
    if rep:
        L += ["### C — Skills del proyecto", "", "| procedimiento | tipo | panel |", "|---|---|---|"]
        for s in rep:
            L.append("| `%s` | %s | %s |" % (s["nombre"], s["tipo"], s["panel"][0] if s["panel"] else "—"))
        L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------- principal

def main():
    ap = argparse.ArgumentParser(description="Cuadro del uso de skills de Hermes (solo lectura).")
    ap.add_argument("--hermes", help="casa de Hermes (por defecto: las dos conocidas)")
    ap.add_argument("--repo", help="carpeta del repo del estudio (por defecto: la de este script)")
    ap.add_argument("--sesion", help="id de sesion, o 'ultima'")
    ap.add_argument("--skill", help="una skill sola")
    ap.add_argument("--desde", help="16/09/2026 o 16/09")
    ap.add_argument("--top", type=int, default=15, help="cuantas skills mostrar (def. 15)")
    ap.add_argument("--json", action="store_true", help="salida machine-readable")
    ap.add_argument("--md", action="store_true", help="salida en tabla markdown")
    args = ap.parse_args()

    casas = [args.hermes] if args.hermes else casas_hermes()
    principal = next((c for c in casas if os.path.isfile(os.path.join(c, "state.db"))), casas[0] if casas else "")
    desde = fecha_de(args.desde) if args.desde else None

    cons, meta = leer_consultas(principal, args.sesion, desde, args.skill)
    led, ruta_led = leer_ledger(principal, args.sesion, desde, args.skill)
    if args.sesion == "ultima":
        sid = ultima_sesion(meta)
        if sid:
            cons = [c for c in cons if c["sesion"] == sid]
            led = [r for r in led if r["_sesion"] == sid]

    repo = args.repo or raiz_repo()
    skills_repo, _ = leer_skills_del_repo(repo)
    total_led = len(leer_ledger(principal)[0])

    cuadro = {
        "generado": datetime.datetime.now().isoformat(timespec="seconds"),
        "perfil": os.environ.get("HERMES_PROFILE", "default"),
        "top": args.top,
        "inventario": inventario(casas),
        "consultas": cons,
        "ledger": led,
        "ledger_total": total_led,
        "sesiones": meta,
        "repo": skills_repo,
        "repo_raiz": repo,
        "filtros": ", ".join(x for x in [
            ("sesion=" + args.sesion) if args.sesion else "",
            ("skill=" + args.skill) if args.skill else "",
            ("desde=" + args.desde) if args.desde else ""] if x),
    }

    if args.json:
        utf8_out()
        print(json.dumps(cuadro, ensure_ascii=False, indent=2, default=str))
    elif args.md:
        print(salida_md(cuadro))
    else:
        print(salida_texto(cuadro))


if __name__ == "__main__":
    main()
