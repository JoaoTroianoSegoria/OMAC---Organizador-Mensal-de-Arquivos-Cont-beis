"""Gera assets/omac.ico e assets/omac.png a partir do mesmo dente do logo da interface.

    python tools/icone.py   (precisa do playwright, igual ao tools/capturas.py)
"""

from __future__ import annotations

import io
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

SVG = """<!doctype html><html><body style="margin:0;background:transparent">
<svg width="256" height="256" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2fc6b8"/><stop offset="1" stop-color="#1478b8"/>
    </linearGradient>
    <linearGradient id="brilho" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect x="8" y="8" width="240" height="240" rx="60" fill="url(#g)"/>
  <rect x="8" y="8" width="240" height="240" rx="60" fill="url(#brilho)"/>
  <g transform="translate(40 38) scale(7.4)" fill="none" stroke="#fff" stroke-width="1.9"
     stroke-linecap="round" stroke-linejoin="round">
    <path d="M7 3C4.5 3 3 5 3 7.5c0 2.5 1 4 1.6 6 .7 2.5 1 7.5 3 7.5 1.8 0 1.7-4.5 2.6-6 .4-.7 1.1-1 1.8-1s1.4.3 1.8 1c.9 1.5.8 6 2.6 6 2 0 2.3-5 3-7.5.6-2 1.6-3.5 1.6-6C21 5 19.5 3 17 3c-1.8 0-3 1-5 1S8.8 3 7 3z"/>
  </g>
</svg></body></html>"""


def main() -> None:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 256, "height": 256})
        pagina.set_content(SVG)
        png = pagina.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": 256, "height": 256})
        navegador.close()

    img = Image.open(io.BytesIO(png)).convert("RGBA")
    destino = RAIZ / "assets"
    destino.mkdir(exist_ok=True)
    img.save(destino / "omac.png")
    img.save(destino / "omac.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ícones salvos em", destino)


if __name__ == "__main__":
    main()
