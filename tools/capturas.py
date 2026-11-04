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
    # arquivo, view, configurações, extras ("pasta": "vazia" | "mes": n)
    ("notas-claro", "notas", {"tema": "claro", "visual": "bonito"}, {}),
    ("notas-escuro", "notas", {"tema": "escuro", "visual": "bonito"}, {}),
    ("notas-otimizado", "notas", {"tema": "claro", "visual": "otimizado"}, {}),
    ("notas-alto-contraste", "notas", {"tema": "claro", "alto_contraste": True}, {}),
    ("notas-texto-grande", "notas", {"tema": "claro", "escala_fonte": 1.5}, {}),
    ("notas-pasta-vazia", "notas", {"tema": "escuro", "visual": "bonito"}, {"pasta": "vazia"}),
    ("notas-mes-vazio", "notas", {"tema": "escuro", "visual": "bonito"}, {"mes": 3}),
    ("extrato-claro", "extrato", {"tema": "claro", "visual": "bonito"}, {}),
    ("extrato-escuro", "extrato", {"tema": "escuro", "visual": "bonito"}, {}),
    ("extrato-otimizado", "extrato", {"tema": "claro", "visual": "otimizado"}, {}),
    ("extrato-alto-contraste", "extrato", {"tema": "claro", "alto_contraste": True}, {}),
    ("extrato-regras", "extrato", {"tema": "escuro", "visual": "bonito"}, {"aba": "regras"}),
    ("config-claro", "config", {"tema": "claro", "visual": "bonito"}, {}),
    ("config-escuro", "config", {"tema": "escuro", "visual": "bonito"}, {}),
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
        pasta_vazia = Path(tmp) / "NFS-e 2027"
        pasta_vazia.mkdir()

        with sync_playwright() as pw:
            # Mostra as barras de rolagem, como no Windows (o modo headless esconde).
            navegador = pw.chromium.launch(ignore_default_args=["--hide-scrollbars"])
            for nome, view, cfg, extras in VARIANTES:
                api = Api()
                alvo = pasta_vazia if extras.get("pasta") == "vazia" else pasta
                api._cfg.update({"pasta_notas": str(alvo), "pasta_extratos": str(pasta / "Extratos"),
                                 "escala_fonte": 1.0,
                                 "alto_contraste": False, **cfg})

                def chamar(metodo, args, api=api):
                    return json.dumps(getattr(api, metodo)(*json.loads(args)))

                # Tamanho de uma janela comum num notebook/monitor pequeno
                pagina = navegador.new_page(viewport={"width": 1164, "height": 725})
                pagina.expose_function("_omac_chamar", chamar)
                pagina.add_init_script(PONTE)
                pagina.goto((RAIZ / "omac" / "ui" / "index.html").as_uri())
                pagina.wait_for_selector("#painel-notas:not([hidden])")
                if "mes" in extras:
                    pagina.select_option("#sel-mes", str(extras["mes"]))
                    pagina.wait_for_selector("#notas-vazio:not([hidden])")
                if view != "notas":
                    pagina.click(f'.menu-item[data-view="{view}"]')
                if view == "extrato":
                    pagina.wait_for_selector("#ext-corpo tr")
                if "aba" in extras:
                    pagina.click(f'[data-acao="ext-aba"][data-aba="{extras["aba"]}"]')
                pagina.wait_for_timeout(400)
                pagina.screenshot(path=str(saida / f"{nome}.png"))
                pagina.close()
                print("ok", nome)
            navegador.close()


if __name__ == "__main__":
    main()
