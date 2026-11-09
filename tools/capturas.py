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
    ("whatsapp-enviar", "whatsapp", {"tema": "escuro", "visual": "bonito"}, {"whats": "enviar"}),
    ("whatsapp-envio", "whatsapp", {"tema": "claro", "visual": "bonito"}, {"whats": "janela"}),
    ("whatsapp-contas", "whatsapp", {"tema": "claro", "visual": "bonito"}, {"whats": "contas"}),
    ("whatsapp-lembretes", "notas", {"tema": "escuro", "visual": "bonito"}, {"whats": "lembretes"}),
    ("whatsapp-envio-otimizado", "whatsapp", {"tema": "escuro", "visual": "otimizado"}, {"whats": "janela"}),
    ("whatsapp-lembretes-contraste", "notas", {"tema": "claro", "alto_contraste": True}, {"whats": "lembretes"}),
    ("agendamentos", "agendamentos", {"tema": "claro", "visual": "bonito"}, {"agenda": "lista"}),
    ("agendamentos-mensagem", "agendamentos", {"tema": "escuro", "visual": "bonito"}, {"agenda": "mensagem"}),
    ("notas-avisos-minimizados", "notas", {"tema": "claro", "visual": "bonito", "avisos_recolhidos": ["notas"]}, {}),
    ("config-whatsapp", "config", {"tema": "claro", "visual": "bonito"}, {"rolar": "#g-whats"}),
    ("config-claro", "config", {"tema": "claro", "visual": "bonito"}, {}),
    ("config-escuro", "config", {"tema": "escuro", "visual": "bonito"}, {}),
]


def _preparar_whatsapp(api, caso: str | None) -> None:
    from datetime import date, timedelta

    hoje = date.today()
    with api._dados() as d:
        d["inicio"] = "2026-01-01"
        d["contas"] = [{"nome": "Aluguel", "dia": 10}, {"nome": "Internet", "dia": 22}]
        if caso == "lembretes":
            d["contas"] = [{"nome": "Aluguel", "dia": hoje.day},
                           {"nome": "Condomínio", "dia": (hoje + timedelta(days=1)).day}]
            d["ultima_abertura"] = ""
        else:
            d["ultima_abertura"] = hoje.isoformat()  # sem a janela de lembretes por cima


def _preparar_agendamentos(api) -> None:
    from datetime import date

    from omac.agendamentos.pacientes import adicionar as adicionar_paciente

    with api._agenda() as d:
        if d["pacientes"]:
            return
        adicionar_paciente(d["pacientes"], {
            "nome": "JOANA RIBEIRO LIMA", "valor": "250,00", "situacao": "alta",
            "alta_inicio": "2026-10-01", "alta_fim": "2027-01-15",
        })
        filho = adicionar_paciente(d["pacientes"], {
            "nome": "PEDRO ALVES SOUZA", "valor": "220,00",
            "responsaveis": {"pai": {"nome": "Carlos Souza", "telefone": ""},
                             "mae": {"nome": "Helena Alves", "telefone": "61900000005"}, "envia_para": "mae"},
        })
        filho["agendado_em"] = ""
        for nome, telefone, valor, agendado in (
            ("ANA BEATRIZ MOREIRA", "61900000001", "250,00", True),
            ("CARLOS EDUARDO LIMA", "61900000002", "250,00", False),
            ("LUCAS COSTA RIBEIRO", "", "180,00", False),
            ("MARIANA ALVES SOUZA", "61900000004", "300,00", True),
        ):
            p = adicionar_paciente(d["pacientes"], {"nome": nome, "telefone": telefone, "valor": valor})
            p["agendado_em"] = date.today().isoformat() if agendado else ""


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
                                 "alto_contraste": False, "lembrete_fechamento_dia": 0,
                                 "assistente_nome": "Exemplo", "lembrete_nome": "Dra. Exemplo",
                                 "lembrete_telefone": "61900000000", **cfg})
                api._cfg["chave_pix"] = "chave@exemplo.com"
                _preparar_whatsapp(api, extras.get("whats"))
                _preparar_agendamentos(api)

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
                if "whats" in extras and view == "whatsapp":
                    pagina.wait_for_selector("#whats-corpo tr")
                    if extras["whats"] == "contas":
                        pagina.click('[data-acao="whats-aba"][data-aba="contas"]')
                    if extras["whats"] == "janela":
                        pagina.click('#whats-corpo [data-acao="whats-enviar"]')
                        pagina.wait_for_selector("#envio[open]")
                if "agenda" in extras:
                    pagina.wait_for_selector("#ag-ativos-corpo tr")
                    if extras["agenda"] == "mensagem":
                        pagina.click('#ag-ativos-corpo [data-acao="ag-mensagem"]')
                        pagina.click('[data-acao="ag-tipo"][data-tipo="cobrar"]')
                if extras.get("whats") == "lembretes":
                    pagina.wait_for_selector("#lembretes[open]")
                if "rolar" in extras:
                    pagina.locator(extras["rolar"]).scroll_into_view_if_needed()
                if "aba" in extras:
                    pagina.click(f'[data-acao="ext-aba"][data-aba="{extras["aba"]}"]')
                pagina.wait_for_timeout(400)
                pagina.screenshot(path=str(saida / f"{nome}.png"))
                pagina.close()
                print("ok", nome)
            navegador.close()


if __name__ == "__main__":
    main()
