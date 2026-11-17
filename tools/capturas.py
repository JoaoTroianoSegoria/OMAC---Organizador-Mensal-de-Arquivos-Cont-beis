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
    ("inicio", "inicio", {"tema": "claro", "visual": "bonito"}, {}),
    ("inicio-escuro", "inicio", {"tema": "escuro", "visual": "bonito"}, {}),
    ("resumo", "resumo", {"tema": "claro", "visual": "bonito"}, {}),
    ("tratamentos-historico", "tratamentos", {"tema": "claro", "visual": "bonito"}, {"agenda": "historico"}),
    ("contatos", "contatos", {"tema": "claro", "visual": "bonito"}, {"ct": "lista"}),
    ("contatos-escuro", "contatos", {"tema": "escuro", "visual": "bonito"}, {"ct": "lista"}),
    ("contatos-janela", "contatos", {"tema": "claro", "visual": "bonito"}, {"ct": "janela"}),
    ("tratamentos-paciente", "tratamentos", {"tema": "escuro", "visual": "bonito"}, {"agenda": "paciente"}),
    ("config-backup", "config", {"tema": "claro", "visual": "bonito", "backup_automatico": True}, {"rolar": "#g-backup"}),
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
    ("tratamentos", "tratamentos", {"tema": "claro", "visual": "bonito"}, {"agenda": "lista"}),
    ("tratamentos-mensagem", "tratamentos", {"tema": "escuro", "visual": "bonito"}, {"agenda": "mensagem"}),
    ("atendimentos", "atendimentos", {"tema": "claro", "visual": "bonito"}, {"pag": "lista"}),
    ("atendimentos-atendimento", "atendimentos", {"tema": "escuro", "visual": "bonito"}, {"pag": "janela"}),
    ("notas-avisos-minimizados", "notas", {"tema": "claro", "visual": "bonito", "avisos_recolhidos": ["notas"]}, {}),
    ("config-whatsapp", "config", {"tema": "claro", "visual": "bonito"}, {"rolar": "#g-whats"}),
    ("config-claro", "config", {"tema": "claro", "visual": "bonito"}, {}),
    ("config-escuro", "config", {"tema": "escuro", "visual": "bonito"}, {}),
]


def _gravar(pasta: Path, nome: str, dados: dict) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _dados_da_1_5(pasta: Path) -> None:
    """Exemplos no formato da 1.5.0: a 1.6.0 passa tudo para o formato novo ao abrir."""
    from datetime import date, timedelta

    from omac.tratamentos.orto import meses_ate

    hoje = date.today()
    meses = meses_ate(hoje.year, hoje.month, 6)
    inicio = f"{meses[0][0]}-{meses[0][1]:02d}-01"
    pacientes = []
    for i, (nome, telefone, valor, agendado) in enumerate((
        ("ANA BEATRIZ MOREIRA", "5561900000001", 25000, True),
        ("CARLOS EDUARDO LIMA", "5561900000002", 25000, False),
        ("LUCAS COSTA RIBEIRO", "", 18000, False),
        ("MARIANA ALVES SOUZA", "5561900000004", 30000, True),
        ("PEDRO ALVES SOUZA", "", 22000, False),
        ("JOANA RIBEIRO LIMA", "5561900000006", 25000, False),
    )):
        de_alta = nome.startswith("JOANA")
        pacientes.append({
            "id": f"p{i}", "nome": nome, "telefone": telefone, "valor_centavos": valor,
            "agendado_em": hoje.isoformat() if agendado else "", "finalizado_em": "",
            "alta_inicio": "2026-10-01" if de_alta else "", "alta_fim": "2027-01-15" if de_alta else "",
            "responsaveis": {"pai": {"nome": "Carlos Souza", "telefone": ""},
                             "mae": {"nome": "Helena Alves", "telefone": "5561900000005"},
                             "envia_para": "mae"} if nome.startswith("PEDRO") else None,
            "atendidos": {} if de_alta else {f"{a}-{m:02d}": f"{a}-{m:02d}-10" for j, (a, m) in enumerate(meses)
                                             if (j + i) % 4 != 1 and j < 5},
            "altas": [], "criado_em": inicio,
        })
    _gravar(pasta, "agendamentos.json", {"pacientes": pacientes})

    mes = hoje.replace(day=1)
    anterior = mes - timedelta(days=3)
    atendimentos = []
    for i, (nome, tratamento, dia, valor, forma, parcelas, pago) in enumerate((
        ("Ana Beatriz Moreira", "Limpeza", mes, 18000, "pix_pf", 1, True),
        ("Pedro Alves Souza", "Manutenção", mes + timedelta(days=1), 22000, "credito", 3, True),
        ("Rafael Martins", "Botox", mes + timedelta(days=3), 90000, "credito", 6, False),
        ("Camila Ferreira", "Limpeza", mes + timedelta(days=4), 18000, "dinheiro", 1, True),
        ("Juliana Alves", "Clareamento", mes + timedelta(days=6), 65000, "pix_pj", 1, False),
        ("Bruno Carvalho", "Restauração", anterior, 25000, "debito", 1, False),
    )):
        atendimentos.append({"id": f"a{i}", "nome": nome, "tratamento": tratamento, "data": dia.isoformat(),
                             "valor_centavos": valor, "forma": forma, "parcelas": parcelas,
                             "pago_em": dia.isoformat() if pago else "", "nota_manual": nome.startswith("Ana")})
    _gravar(pasta, "pagamentos.json", {"atendimentos": atendimentos})

    anterior_mes = (hoje.replace(day=1) - timedelta(days=1)).isoformat()[:7]
    _gravar(pasta, "whatsapp.json", {
        "inicio": "2026-01-01", "ultima_abertura": hoje.isoformat(),
        "contatos": {
            "FERNANDA COSTA": {"nome": "FERNANDA COSTA", "telefone": "5561900000010"},
            "CAMILA FERREIRA": {"nome": "CAMILA FERREIRA", "telefone": "5561900000011"},
            # Parecido com "Rafael Martins" da ficha, e telefone diferente do cadastro da orto:
            # vão para "Conferir contatos".
            "RAFAEL MARTINS COSTA": {"nome": "RAFAEL MARTINS COSTA", "telefone": "5561900000012"},
            "CARLOS EDUARDO LIMA": {"nome": "CARLOS EDUARDO LIMA", "telefone": "5561900000099"},
        },
        "enviadas": {},
        "contas": [
            {"nome": "Aluguel", "dia": 10, "criada_em": "2026-01-01", "pagas": {hoje.isoformat()[:7]: hoje.isoformat(),
                                                                               anterior_mes: anterior_mes + "-09"}},
            {"nome": "Internet", "dia": 22, "criada_em": "2026-01-01", "pagas": {}},
            {"nome": "Laboratório", "dia": 28, "criada_em": "2026-01-01", "pagas": {anterior_mes: anterior_mes + "-27"}},
        ],
    })
    _gravar(pasta, "config.json", {"lembrete_nome": "Dra. Exemplo", "lembrete_telefone": "5561900000000"})


def _preparar_whatsapp(api, caso: str | None) -> None:
    from datetime import date, timedelta

    hoje = date.today()
    with api._contas() as d:
        if caso == "lembretes":
            d["contas"] = [{"nome": "Aluguel", "dia": hoje.day},
                           {"nome": "Condomínio", "dia": (hoje + timedelta(days=1)).day}]
            d["ultima_abertura"] = ""
        else:
            d["ultima_abertura"] = hoje.isoformat()  # sem a janela de lembretes por cima


def main() -> None:
    from playwright.sync_api import sync_playwright

    saida = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "docs" / "capturas")
    saida.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_CONFIG_HOME"] = tmp  # não mexe na configuração de quem roda
        from omac.app import Api
        from tests.fabrica import criar_pasta_exemplo

        _dados_da_1_5(Path(tmp) / "omac")
        pasta = criar_pasta_exemplo(Path(tmp) / "NFS-e 2026")
        pendrive = Path(tmp) / "Pendrive"
        pendrive.mkdir()
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
                                 "assistente_nome": "Exemplo", "abrir_em": "notas",
                                 "backup_pasta": str(pendrive), **cfg})
                api._cfg["chave_pix"] = "chave@exemplo.com"
                _preparar_whatsapp(api, extras.get("whats"))
                if not api._cfg["backup_ultimo"]:
                    api.backup_agora()

                def chamar(metodo, args, api=api):
                    return json.dumps(getattr(api, metodo)(*json.loads(args)))

                # Tamanho de uma janela comum num notebook/monitor pequeno
                pagina = navegador.new_page(viewport={"width": 1164, "height": 725})
                pagina.expose_function("_omac_chamar", chamar)
                pagina.add_init_script(PONTE)
                pagina.goto((RAIZ / "omac" / "ui" / "index.html").as_uri())
                pagina.wait_for_selector("#painel-notas:not([hidden])")
                # As notas e extratos de exemplo são de outubro/2026, seja qual for o dia de hoje.
                pagina.evaluate("mudarMes(2026, 10)")
                pagina.wait_for_timeout(300)
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
                if view in ("inicio", "resumo"):
                    pagina.wait_for_selector(".ini-cartao" if view == "inicio" else "#rs-corpo tr")
                if "ct" in extras:
                    pagina.wait_for_selector("#ct-corpo tr")
                    if extras["ct"] == "janela":
                        pagina.click('#ct-corpo tr:has(td:first-child:text-is("PEDRO ALVES SOUZA")) [data-acao="ct-editar"]')
                        pagina.wait_for_selector("#ct-contato[open]")
                if "agenda" in extras:
                    pagina.wait_for_selector("#ag-ativos-corpo tr")
                    if extras["agenda"] == "paciente":
                        pagina.click('#ag-ativos-corpo tr:has-text("PEDRO") [data-acao="ag-editar"]')
                        pagina.wait_for_selector("#ct-contato[open]")
                    if extras["agenda"] == "historico":
                        pagina.click('[data-acao="ag-aba"][data-aba="historico"]')
                        pagina.wait_for_selector("#ag-hist-corpo tr")
                    if extras["agenda"] == "mensagem":
                        pagina.click('#ag-ativos-corpo tr:has-text("PEDRO") [data-acao="ag-mensagem"]')
                        pagina.click('[data-acao="ag-tipo"][data-tipo="cobrar"]')
                if "pag" in extras:
                    pagina.wait_for_selector("#pg-corpo tr")
                    if extras["pag"] == "janela":
                        pagina.click('#pg-corpo tr:nth-child(3) [data-acao="pg-editar"]')
                        pagina.wait_for_selector("#pg-atendimento[open]")
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
