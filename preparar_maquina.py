#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREPARAR_MAQUINA.PY — deja esta máquina lista para la primera corrida.

Qué hace:

1. Crea `config.py` a partir de `config.example.py` (config.py NO está en el
   repo a propósito: tiene los datos de cada máquina).
2. Le pone la matrícula de SISFE que le pases.
3. Avisa si falta instalar algo.

Los 44 juzgados de Rosario NO hay que copiarlos: se leen solos de
skills/juzgados_rosario.json (ver expediente_utils._juzgados).

Uso:
    python preparar_maquina.py --matricula LV029
"""
import argparse
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DESTINO = os.path.join(BASE, "config.py")
PLANTILLA = os.path.join(BASE, "config.example.py")


def _falta(modulo):
    try:
        __import__(modulo)
        return False
    except ImportError:
        return True


def main():
    ap = argparse.ArgumentParser(description="Prepara la máquina para la primera corrida.")
    ap.add_argument("--matricula", required=True,
                    help="Matrícula de SISFE (ej. LV029)")
    ap.add_argument("--force", action="store_true",
                    help="Pisa el config.py que ya exista (por defecto no lo toca)")
    args = ap.parse_args()

    if os.path.exists(DESTINO) and not args.force:
        print("config.py ya existe — no lo toco. (Usá --force si querés regenerarlo.)")
    else:
        shutil.copyfile(PLANTILLA, DESTINO)
        with open(DESTINO, encoding="utf-8") as f:
            texto = f.read()
        texto, cambios = re.subn(r'^SISFE_USUARIO\s*=\s*"[^"]*"',
                                 f'SISFE_USUARIO = "{args.matricula}"',
                                 texto, count=1, flags=re.M)
        with open(DESTINO, "w", encoding="utf-8") as f:
            f.write(texto)
        estado = "creado" if cambios else "creado (¡ojo! no encontré SISFE_USUARIO, revisalo a mano)"
        print(f"config.py {estado} — matrícula: {args.matricula}")

    print()
    pendientes = [m for m in ("fastapi", "uvicorn", "playwright", "pypdf", "reportlab", "docx", "PIL") if _falta(m)]
    if pendientes:
        print("Falta instalar:")
        print("    python -m pip install -r requirements.txt")
        print("    python -m playwright install chromium")
    else:
        print("Dependencias de Python: OK")

    if _falta("hermes") and shutil.which("hermes") is None:
        print("Ojo: 'hermes' no está en el PATH — las 4 acciones del secretario no van a correr.")
        print("     (el resto del sistema sí funciona sin Hermes)")

    print()
    print("Listo. Para arrancar:")
    print("    python servidor.py      y abrir http://localhost:8000")
    print("    python monitor_playwright.py --una-vez     (revisar SISFE una vez)")
    print("    python monitor_playwright.py --limite-ciclos 3   (modo continuo acotado)")
    print()
    print("Después de firmar una cédula, subirla al SISFE:")
    print('    python sisfe_notificar.py "ruta\\a\\cedula_FIRMADO.pdf" "21-04253894-6"')
    print("    (deja todo cargado y espera TU clic en NOTIFICAR)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
