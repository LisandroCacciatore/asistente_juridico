# -*- coding: utf-8 -*-
"""
EXPONER_SKILLS_HERMES.PY

Deja las skills del estudio (skills/ del repo) al alcance de un Hermes
que corra en esta carpeta, para poder invocarlas con `hermes chat -s <skill>`.

Hermes carga las skills locales de un proyecto desde ./.hermes/skills/
(una carpeta por skill, con su SKILL.md). Este script las genera a partir
de skills/ — que sigue siendo la única fuente de verdad: no se edita nada
a mano acá.

  Uso:  python dev/exponer_skills_hermes.py
"""
import os
import re
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEN = os.path.join(BASE, "skills")
DESTINO = os.path.join(BASE, ".hermes", "skills")


def _nombre_skill(ruta_md):
    """Saca el `name:` del frontmatter (es el nombre real de la skill)."""
    try:
        with open(ruta_md, encoding="utf-8") as f:
            cabecera = f.read(1200)
    except OSError:
        return None
    m = re.search(r'^name:\s*"?([\w\-]+)"?\s*$', cabecera, re.M)
    return m.group(1) if m else None


def recolectar():
    """Devuelve [(nombre, origen)] de cada skill del repo."""
    encontradas = []
    for entrada in sorted(os.listdir(ORIGEN)):
        ruta = os.path.join(ORIGEN, entrada)
        if os.path.isdir(ruta):
            md = os.path.join(ruta, "SKILL.md")
            if os.path.isfile(md):
                nombre = _nombre_skill(md) or entrada
                encontradas.append((nombre, ruta))
        elif entrada.endswith(".md"):
            nombre = _nombre_skill(ruta)
            if nombre:
                encontradas.append((nombre, ruta))
    return encontradas


def main():
    if not os.path.isdir(ORIGEN):
        print(f"No encuentro {ORIGEN}")
        return 1

    os.makedirs(DESTINO, exist_ok=True)
    skills = recolectar()
    for nombre, origen in skills:
        destino = os.path.join(DESTINO, nombre)
        if os.path.isdir(destino):
            shutil.rmtree(destino)
        os.makedirs(destino, exist_ok=True)
        if os.path.isdir(origen):
            # skill con references/scripts/assets: se copia entera
            for item in os.listdir(origen):
                src = os.path.join(origen, item)
                dst = os.path.join(destino, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        else:
            # skill de un solo archivo: pasa a ser su SKILL.md
            shutil.copy2(origen, os.path.join(destino, "SKILL.md"))
        print(f"  ✓ {nombre}")

    print(f"\n{len(skills)} skills expuestas en {DESTINO}")

    # Hermes exige confiar en el proyecto para cargar sus skills locales.
    try:
        r = subprocess.run(["hermes", "skills", "trust"], cwd=BASE,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
        salida = (r.stdout or r.stderr or "").strip()
        print("\nhermes skills trust ->", "OK" if r.returncode == 0 else f"código {r.returncode}")
        if salida:
            print(salida[-600:])
    except FileNotFoundError:
        print("\n⚠ No encontré el comando `hermes` en el PATH.")
        return 1
    except subprocess.TimeoutExpired:
        print("\n⚠ `hermes skills trust` tardó demasiado (¿pidió confirmación?).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
