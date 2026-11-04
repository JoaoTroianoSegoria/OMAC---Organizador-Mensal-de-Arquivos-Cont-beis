"""Tira as capturas de tela do README com dados de exemplo (nenhum dado real).

Abre a interface no Chromium (mesmo motor do WebView2 do Windows) ligada à
API Python de verdade, lendo uma pasta de notas gerada por tests/fabrica.py.

    pip install playwright && python -m playwright install chromium
    python tools/capturas.py [pasta_de_saida]
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

PONTE = """
window.pywebview = { api: new Proxy({}, { get: (_, nome) =>
  (...args) => window._omac_chamar(nome, JSON.stringify(args)).then(JSON.parse) }) };
"""

VARIANTES = [
    # arquivo, view, configurações
    ("notas-claro", "notas", {"tema": "claro", "visual": "bonito"}),
    ("notas-escuro", "notas", {"tema": "escuro", "visual": "bonito"}),
    ("notas-otimizado", "notas", {"tema": "claro", "visual": "otimizado"}),
    ("notas-alto-contraste", "notas", {"tema": "claro", "alto_contraste": True}),
    ("notas-texto-grande", "notas", {"tema": "claro", "escala_fonte": 1.5}),
    ("config-claro", "config", {"tema": "claro", "visual": "bonito"}),
    ("config-escuro", "config", {"tema": "escuro", "visual": "bonito"}),
]


def main() -> None:
    from playwright.sync_api import sync_playwright

    saida = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "docs" / "capturas")
    saida.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_CONFIG_HOME"] = tmp  # não mexe na configuração de quem roda
        from omac.app import Api
        from tests.fabrica import criar_pasta_exemplo

        pasta = criar_pasta_exemplo(Path(tmp) / "NFS-e 2026")

        with sync_playwright() as pw:
            navegador = pw.chromium.launch()
            for nome, view, cfg in VARIANTES:
                api = Api()
                api._cfg.update({"pasta_notas": str(pasta), "escala_fonte": 1.0,
                                 "alto_contraste": False, **cfg})

                def chamar(metodo, args, api=api):
                    return json.dumps(getattr(api, metodo)(*json.loads(args)))

                pagina = navegador.new_page(viewport={"width": 1280, "height": 820})
                pagina.expose_function("_omac_chamar", chamar)
                pagina.add_init_script(PONTE)
                pagina.goto((RAIZ / "omac" / "ui" / "index.html").as_uri())
                pagina.wait_for_selector("#tabela-corpo tr")
                if view != "notas":
                    pagina.click(f'.menu-item[data-view="{view}"]')
                pagina.wait_for_timeout(400)
                pagina.screenshot(path=str(saida / f"{nome}.png"))
                pagina.close()
                print("ok", nome)
            navegador.close()


if __name__ == "__main__":
    main()
