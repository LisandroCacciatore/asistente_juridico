"""Tests de dev/auditoria_skills.py.

El audit lee el Hermes real, pero estos tests son **herméticos**: arman una
casa de Hermes de mentira (sqlite + ledger) en un temp y verifican que el
cuadro no mienta. Lo que se blinda acá:

  - una llamada con varias copias (la compactación guarda una por vez)
    se cuenta UNA vez, y el nombre sale de la copia sin podar;
  - `skills_list` no se hace pasar por una skill (se le roban los nombres
    del listado si no se lo trata aparte);
  - el ledger se deduplica por id y se agrupa por skill/sesión;
  - las skills del repo se cruzan con lo que expone el panel (acciones.py),
    incluidos los procedimientos que son archivo suelto (.md);
  - una entrada del ledger sin `ts` no rompe el cuadro.
"""

import importlib.util
import json
import os
import pathlib
import sqlite3
import sys
import time

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
RUTA_SCRIPT = RAIZ / "dev" / "auditoria_skills.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("auditoria_skills", RUTA_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


aud = _cargar()


# ------------------------------------------------------------------- andamiaje

def _tc(cid, tool, args):
    """El tool_calls de una llamada, tal como lo guarda Hermes."""
    return json.dumps([{"id": cid, "type": "function",
                        "function": {"name": tool, "arguments": json.dumps(args)}}])


def _casa(tmp_path, con_ledger=True, con_uso=True):
    """Casa de Hermes de mentira: state.db + skills/ con ledger y registro."""
    casa = tmp_path / "hermes"
    (casa / "skills").mkdir(parents=True)

    db = sqlite3.connect(str(casa / "state.db"))
    db.execute("""create table sessions (id text, title text, started_at real,
                  last_activity_at real)""")
    db.execute("""create table messages (id integer primary key, session_id text,
                  role text, tool_name text, tool_calls text, tool_call_id text,
                  content text, timestamp real, active integer, compacted integer)""")
    db.execute("insert into sessions values ('s1','Juridico',100,900)")
    db.execute("insert into sessions values ('s2','Otro',100,500)")

    # orden de columnas del INSERT: id, session_id, role, tool_name, tool_calls,
    #                            tool_call_id, content, timestamp, active, compacted
    filas = [
        (1, 's1', 'tool', 'skill_view', None, 'call_A', '{"success": true, "name": "emil-design-eng"}', 300, 0, 1),
        (2, 's1', 'tool', 'skill_view', None, 'call_A', '[skill_view] name=emil-design-eng (28,609 chars) [SKILL_PRUNED]', 300, 0, 1),
        (3, 's1', 'tool', 'skill_view', None, 'call_A', '[skill_view] name=emil-design-eng (28,609 chars)', 300, 1, 0),
        (4, 's1', 'assistant', None, _tc('call_A', 'skill_view', {'name': 'emil-design-eng'}), None, 'ok', 300, 1, 0),
        (5, 's1', 'tool', 'skills_list', None, 'call_B', '{"success": true, "skills": [{"name": "octalysis-auditor"}, {"name": "himalaya"}]}', 310, 1, 0),
        (6, 's1', 'assistant', None, _tc('call_B', 'skills_list', {}), None, 'ok', 310, 1, 0),
        (7, 's2', 'tool', 'skill_view', None, 'call_C', '{"success": true, "name": "repo-audit"}', 400, 1, 0),
        (8, 's2', 'assistant', None, _tc('call_C', 'skill_view', {'name': 'repo-audit'}), None, 'ok', 400, 1, 0),
        # llamada que FALLO: el resultado no trae el nombre, la llamada si
        (9, 's1', 'tool', 'skill_view', None, 'call_D', '{"success": false, "error": "Skill not found."}', 320, 1, 0),
        (10, 's1', 'assistant', None, _tc('call_D', 'skill_view', {'name': 'skill-que-falla'}), None, 'ok', 320, 1, 0),
        # escritura de una skill (create)
        (11, 's1', 'tool', 'skill_manage', None, 'call_E', '{"success": true, "name": "telemetria"}', 330, 1, 0),
        (12, 's1', 'assistant', None, _tc('call_E', 'skill_manage', {'name': 'telemetria', 'action': 'create'}), None, 'ok', 330, 1, 0),
    ]
    db.executemany("insert into messages values (?,?,?,?,?,?,?,?,?,?)", filas)
    db.commit()
    db.close()

    if con_ledger:
        entradas = [
            {"id": "e1", "ts": "2026-09-16T20:00:00+00:00", "actor": "curator", "action": "create",
             "skill": "human-gated-automation", "evidence": {"session_id": "s1"}},
            {"id": "e2", "ts": "2026-09-17T02:00:00+00:00", "actor": "curator", "action": "write_file",
             "skill": "human-gated-automation", "evidence": {"session_id": "s1", "file_path": "references/x.md"}},
            {"id": "e2", "ts": "2026-09-17T02:00:00+00:00", "actor": "curator", "action": "write_file",
             "skill": "human-gated-automation", "evidence": {"session_id": "s1", "file_path": "references/x.md"}},
            {"id": "e3", "ts": "2026-09-15T10:00:00+00:00", "actor": "curator", "action": "patch",
             "skill": "repo-audit", "evidence": {"session_id": "s2"}},
            {"id": "e4", "actor": "curator", "action": "write_file", "skill": "sin-fecha",
             "evidence": {"session_id": "s1"}},
        ]
        (casa / "skills" / ".curator_ledger.jsonl").write_text(
            "\n".join(json.dumps(e) for e in entradas), encoding="utf-8")

    if con_uso:
        (casa / "skills" / ".usage.json").write_text(
            json.dumps({"a": {"use_count": 1}, "b": {"use_count": 2}}), encoding="utf-8")
    return casa


def _repo(tmp_path):
    """Repo de mentira: una skill en carpeta, una suelta y un dato."""
    repo = tmp_path / "repo"
    (repo / "skills" / "cliente-art-nuevo").mkdir(parents=True)
    (repo / "skills" / "cliente-art-nuevo" / "SKILL.md").write_text("# alta ART\n", encoding="utf-8")
    (repo / "skills" / "oficio-raeo.md").write_text("# RAEO\n", encoding="utf-8")
    (repo / "skills" / "juzgados_rosario.json").write_text("{}", encoding="utf-8")
    (repo / "acciones.py").write_text(
        '_SKILLS_SECRETARIO = {\n'
        '    "art":  ("cliente-art-nuevo", "Alta de un cliente nuevo de ART"),\n'
        '    "raeo": ("oficio-raeo", "Oficio al RAEO"),\n'
        '}\n', encoding="utf-8")
    return repo


# ------------------------------------------------------------------- CAPA A

def test_una_llamada_con_copias_se_cuenta_una_vez(tmp_path):
    casa = _casa(tmp_path)
    cons, meta = aud.leer_consultas(str(casa))
    emil = [c for c in cons if c["skill"] == "emil-design-eng"]
    assert len(emil) == 1, "las 3 copias de la misma llamada son UNA llamada"
    assert emil[0]["completo"] is True, "se queda con la copia sin podar"


def test_skills_list_no_se_hace_pasar_por_skill(tmp_path):
    casa = _casa(tmp_path)
    cons, _ = aud.leer_consultas(str(casa))
    nombres = {c["skill"] for c in cons}
    assert "(listado de skills)" in nombres
    assert "octalysis-auditor" not in nombres, "los nombres del listado no son consultas"
    assert "himalaya" not in nombres


def test_titulo_de_la_sesion_pegado_a_la_llamada(tmp_path):
    casa = _casa(tmp_path)
    cons, _ = aud.leer_consultas(str(casa))
    assert next(c for c in cons if c["skill"] == "emil-design-eng")["titulo"] == "Juridico"


def test_filtros_de_sesion_y_skill(tmp_path):
    casa = _casa(tmp_path)
    cons, _ = aud.leer_consultas(str(casa), sesion="s2")
    assert {c["skill"] for c in cons} == {"repo-audit"}
    cons, _ = aud.leer_consultas(str(casa), skill="repo-audit")
    assert {c["sesion"] for c in cons} == {"s2"}


def test_filtro_desde(tmp_path):
    casa = _casa(tmp_path)
    cons, _ = aud.leer_consultas(str(casa), desde=aud.fecha_de("16/09/2026"))
    assert all(c["ts"] >= aud.fecha_de("16/09/2026").timestamp() for c in cons)


def test_sin_base_no_explota(tmp_path):
    cons, meta = aud.leer_consultas(str(tmp_path / "no-existe"))
    assert cons == [] and meta == {}


def test_el_nombre_sale_de_la_llamada_aunque_el_resultado_falle(tmp_path):
    """Un skill_view fallido no trae 'name' en el resultado: la llamada si."""
    casa = _casa(tmp_path)
    cons, _ = aud.leer_consultas(str(casa))
    fallada = next(c for c in cons if c["ok"] is False)
    assert fallada["skill"] == "skill-que-falla"
    assert fallada["tool"] == "skill_view"


def test_escritura_trae_accion_y_resultado(tmp_path):
    casa = _casa(tmp_path)
    cons, _ = aud.leer_consultas(str(casa))
    esc = next(c for c in cons if c["tool"] == "skill_manage")
    assert esc["skill"] == "telemetria"
    assert esc["accion"] == "create" and esc["ok"] is True


def test_el_cuadro_cuenta_lecturas_escrituras_y_fallidas(tmp_path, capsys):
    print(aud.salida_texto(_cuadro(tmp_path)))
    out = capsys.readouterr().out
    assert "lecturas (skill_view)" in out and "escrituras (skill_manage)" in out
    assert "1 fallidas" in out


# ------------------------------------------------------------------- CAPA B

def test_ledger_deduplica_y_agrupa(tmp_path):
    casa = _casa(tmp_path)
    led, _ = aud.leer_ledger(str(casa))
    assert len(led) == 4, "la entrada e2 repetida cuenta una vez"
    hga = [r for r in led if r["skill"] == "human-gated-automation"]
    assert len(hga) == 2
    assert sum(1 for r in hga if r["action"] == "create") == 1


def test_ledger_por_sesion(tmp_path):
    casa = _casa(tmp_path)
    led, _ = aud.leer_ledger(str(casa), sesion="s2")
    assert [r["skill"] for r in led] == ["repo-audit"]


def test_entrada_sin_ts_no_rompe_el_rango(tmp_path):
    casa = _casa(tmp_path)
    led, _ = aud.leer_ledger(str(casa))
    sin_fecha = [r for r in led if r["skill"] == "sin-fecha"]
    assert aud.rango_ts(sin_fecha) == (None, None)
    pri, ult = aud.rango_ts([r for r in led if r["skill"] == "human-gated-automation"])
    assert pri and ult and pri <= ult


# ------------------------------------------------------------------- CAPA C

def test_skills_del_repo_y_panel(tmp_path):
    repo = _repo(tmp_path)
    skills, _ = aud.leer_skills_del_repo(str(repo))
    por_nombre = {s["nombre"]: s for s in skills}
    assert por_nombre["cliente-art-nuevo"]["panel"] == ("art", "Alta de un cliente nuevo de ART")
    assert por_nombre["oficio-raeo.md"]["panel"][0] == "raeo", "el .md tambien cruza con el panel"
    assert por_nombre["juzgados_rosario.json"]["panel"] is None
    assert por_nombre["juzgados_rosario.json"]["tipo"] == "dato"


def test_inventario_cuenta_skills(tmp_path):
    casa = _casa(tmp_path)
    (casa / "skills" / "sdd-verify").mkdir()
    (casa / "skills" / "sdd-verify" / "SKILL.md").write_text("# sdd\n", encoding="utf-8")
    inv = aud.inventario([str(casa)])
    assert inv["por_casa"][str(casa)]["skills"] == 1
    assert inv["por_casa"][str(casa)]["sdd"] == 1
    assert inv["registro_uso"] == 2


# ------------------------------------------------------------------- salidas

def _cuadro(tmp_path):
    casa = _casa(tmp_path)
    repo = _repo(tmp_path)
    cons, meta = aud.leer_consultas(str(casa))
    led, _ = aud.leer_ledger(str(casa))
    skills, _ = aud.leer_skills_del_repo(str(repo))
    return {
        "generado": "2026-09-17T14:00:00", "perfil": "default", "top": 15,
        "inventario": aud.inventario([str(casa)]), "consultas": cons, "ledger": led,
        "ledger_total": len(led), "sesiones": meta, "repo": skills,
        "repo_raiz": str(repo), "filtros": "",
    }


def test_salida_texto_tiene_las_tres_capas(tmp_path, capsys):
    print(aud.salida_texto(_cuadro(tmp_path)))
    out = capsys.readouterr().out
    for etiqueta in ("CAPA A - CONSULTADAS", "CAPA B - APRENDIDAS",
                     "CAPA C - SKILLS DEL PROYECTO", "POR SESION", "INVENTARIO"):
        assert etiqueta in out
    assert "emil-design-eng" in out and "human-gated-automation" in out
    assert "si: art" in out


def test_salida_md_es_tabla(tmp_path):
    md = aud.salida_md(_cuadro(tmp_path))
    assert md.startswith("## Auditoría de skills")
    assert "| `emil-design-eng` | 1 |" in md
    assert "| `cliente-art-nuevo` | procedimiento | art |" in md


def test_json_es_serializable(tmp_path):
    carga = json.dumps(_cuadro(tmp_path), default=str)
    assert "CAPA" not in carga and "human-gated-automation" in carga


# ------------------------------------------------------------------- utilidades

def test_fecha_de_acepta_dos_formatos():
    assert aud.fecha_de("16/09/2026").year == 2026
    assert aud.fecha_de("16/09").year == __import__("datetime").date.today().year
    try:
        aud.fecha_de("ayer")
    except SystemExit:
        pass
    else:
        raise AssertionError("una fecha invalida tiene que cortar")


def test_nombre_de_skill_de_las_dos_formas():
    assert aud.nombre_de_skill('{"success": true, "name": "repo-audit"}') == "repo-audit"
    assert aud.nombre_de_skill("[skill_view] name=repo-audit (4,000 chars)") == "repo-audit"
    assert aud.nombre_de_skill("") == "(sin nombre)"
