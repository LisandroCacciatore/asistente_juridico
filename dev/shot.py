# -*- coding: utf-8 -*-
"""Captura un screenshot full-page de un HTML local (verificación visual)."""
import sys, pathlib
from playwright.sync_api import sync_playwright

html = sys.argv[1]
url = html if html.startswith("http") else pathlib.Path(html).resolve().as_uri()
out = sys.argv[2] if len(sys.argv) > 2 else "shot.png"

with sync_playwright() as p:
    try:
        b = p.chromium.launch(channel="chrome")
    except Exception:
        b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
    pg.goto(url)
    pg.wait_for_timeout(6000)          # fuentes + rail() + datos del servidor
    pg.screenshot(path=out, full_page=True)
    b.close()
print(f"OK -> {out}")
