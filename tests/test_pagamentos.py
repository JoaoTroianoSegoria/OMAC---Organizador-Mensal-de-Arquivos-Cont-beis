import json
from datetime import date
from decimal import Decimal

import pytest

from omac import config, sistema
from omac.app import Api
from omac.notas.leitor import Nota
from omac.pagamentos import exportar as exp
from omac.pagamentos import ficha as fc
from omac.whatsapp import lembretes as lb
from tests.fabrica import criar_pasta_exemplo

NOV = date(2026, 11, 13)


def _atendimento(**campos):
    return fc.completar({"id": "x", "nome": "Ana Exemplo", "data": "2026-11-03", **campos})


# --- Situação do pagamento ------------------------------------------------------------


def test_pago_aguardando_e_nao_pago_saem_das_datas():
    assert fc.situacao(_atendimento(pago_em="2026-11-05"), NOV) == fc.PAGO
    assert fc.situacao(_atendimento(), NOV) == fc.AGUARDANDO
    # Virou o mês sem marcar: "não". Ninguém precisa abrir o app no dia 1.
    assert fc.situacao(_atendimento(), date(2026, 12, 1)) == fc.NAO_PAGO
    assert fc.situacao(_atendimento(data="2026-10-30"), NOV) == fc.NAO_PAGO
    # Pagou depois: basta marcar.
    a = _atendimento(data="2026-10-30")
    fc.marcar_pago(a, True, NOV)
    assert fc.situacao(a, NOV) == fc.PAGO


def test_forma_por_extenso():
    assert fc.forma_por_extenso(_atendimento(forma="pix_pj")) == "Pix PJ"
    assert fc.forma_por_extenso(_atendimento(forma="credito", parcelas=3)) == "Crédito 3x"
    assert fc.forma_por_extenso(_atendimento(forma="credito", parcelas=1)) == "Crédito à vista"
    assert fc.forma_por_extenso(_atendimento()) == ""


@pytest.mark.parametrize("dados, erro", [
    ({"nome": " ", "data": "2026-11-03"}, "nome"),
    ({"nome": "Ana", "data": ""}, "data"),
    ({"nome": "Ana", "data": "2026-02-30"}, "não existe"),
    ({"nome": "Ana", "data": "2026-11-03", "valor": "abc"}, "valor"),
    ({"nome": "Ana", "data": "2026-11-03", "forma": "cheque"}, "forma"),
    ({"nome": "Ana", "data": "2026-11-03", "forma": "credito", "parcelas": 13}, "1 a 12"),
])
def test_validacao(dados, erro):
    with pytest.raises(fc.AtendimentoInvalido, match=erro):
        fc.adicionar([], dados, NOV)


def test_parcelas_so_valem_no_credito():
    a = fc.adicionar([], {"nome": "Ana", "data": "2026-11-03", "forma": "pix_pf", "parcelas": 5}, NOV)
    assert a["parcelas"] == 1
    a = fc.adicionar([], {"nome": "Ana", "data": "2026-11-03", "forma": "credito", "parcelas": "4"}, NOV)
    assert a["parcelas"] == 4


def test_alterar_mantem_a_data_do_pagamento():
    lista = []
    a = fc.adicionar(lista, {"nome": "Ana", "data": "2026-11-03", "pago": True}, date(2026, 11, 4))
    fc.alterar(lista, a["id"], {"nome": "Ana Souza", "data": "2026-11-03", "pago": True}, NOV)
    assert a["pago_em"] == "2026-11-04" and a["nome"] == "Ana Souza"
    fc.alterar(lista, a["id"], {"nome": "Ana Souza", "data": "2026-11-03", "pago": False}, NOV)
    assert a["pago_em"] == ""


def test_alterar_com_erro_nao_muda_nada():
    lista = []
    a = fc.adicionar(lista, {"nome": "Ana", "data": "2026-11-03", "valor": "100"}, NOV)
    with pytest.raises(fc.AtendimentoInvalido):
        fc.alterar(lista, a["id"], {"nome": "Outra", "data": "2026-11-03", "valor": "xyz"}, NOV)
    assert a["nome"] == "Ana" and a["valor_centavos"] == 10000


# --- Nota emitida ----------------------------------------------------------------------


@pytest.mark.parametrize("ficha, nota, igual", [
    ("Ana Souza", "ANA SOUZA", True),
    ("Ana Souza", "ANA MARIA SOUZA", True),  # sobrenome a mais na nota
    ("Ana Maria Souza", "Ana Souza", True),
    ("João Otávio", "JOAO OTAVIO", True),  # sem acento no arquivo
    ("Ana", "ANA SOUZA", False),  # uma palavra só não basta
    ("Ana", "ANA", True),
    ("Ana Souza", "MARIA SOUZA", False),
    ("Ana Souza", "", False),
])
def test_mesmo_paciente(ficha, nota, igual):
    assert fc.mesmo_paciente(ficha, nota) is igual


def _nota(numero, paciente, competencia):
    return Nota(numero, paciente, Decimal("100"), competencia, competencia, f"{numero}.pdf")


def test_nota_precisa_ser_do_mes_do_atendimento():
    notas = [_nota(10, "ANA SOUZA", date(2026, 10, 30)), _nota(11, "ANA SOUZA", date(2026, 11, 5))]
    assert fc.nota_do_atendimento(_atendimento(nome="Ana Souza"), notas) == 11
    assert fc.nota_do_atendimento(_atendimento(nome="Ana Souza", data="2026-09-10"), notas) is None


# --- Lista ---------------------------------------------------------------------------


def test_meses_e_ordem():
    lista = [_atendimento(id="1", data="2026-11-10", nome="Bia"), _atendimento(id="2", data="2026-11-02"),
             _atendimento(id="3", data="2026-10-05"), _atendimento(id="4", data="2026-11-10", nome="Ana")]
    assert [a["id"] for a in fc.do_mes(lista, 2026, 11)] == ["2", "4", "1"]
    assert fc.meses(lista) == [(2026, 10, 1), (2026, 11, 3)]


def test_nomes_juntam_ficha_e_ortodontia_sem_repetir():
    ficha = [_atendimento(nome="ana souza", data="2026-10-01"), _atendimento(nome="Ana Souza", data="2026-11-01")]
    orto = [{"nome": "Pedro Exemplo"}, {"nome": "ANA SOUZA"}]
    assert fc.nomes_salvos(ficha, orto) == ["Ana Souza", "Pedro Exemplo"]


def test_totais():
    lista = [
        {"valor_centavos": 10000, "situacao": fc.PAGO, "nota": True},
        {"valor_centavos": 5000, "situacao": fc.AGUARDANDO, "nota": False},
        {"valor_centavos": None, "situacao": fc.AGUARDANDO, "nota": False},
        {"valor_centavos": 2000, "situacao": fc.NAO_PAGO, "nota": True},
    ]
    assert fc.totais(lista) == {"recebido_centavos": 10000, "a_receber_centavos": 5000,
                                "nao_pago_centavos": 2000, "nao_pagos": 1, "sem_nota": 2}


# --- API -------------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "abrir_link", lambda u: None)
    return Api()


def test_api_salva_e_lista_o_mes_do_atendimento(api):
    r = api.pagamentos_salvar({"nome": "Ana Exemplo", "data": "2026-10-20", "valor": "150", "forma": "credito",
                               "parcelas": 3, "tratamento": "Limpeza", "pago": True})
    assert "erro" not in r, r
    assert (r["ano"], r["mes"]) == (2026, 10)
    [a] = r["atendimentos"]
    assert a["situacao"] == fc.PAGO and a["forma_texto"] == "Crédito 3x" and a["valor_centavos"] == 15000
    assert r["totais"]["recebido_centavos"] == 15000
    assert r["meses"] == [(2026, 10, 1)]
    assert "Ana Exemplo" in r["nomes"]
    assert r["notas_lidas"] is False

    # Gravado em JSON, separado do resto
    salvo = json.loads(config.caminho_pagamentos().read_text(encoding="utf-8"))
    assert salvo["atendimentos"][0]["nome"] == "Ana Exemplo"


def test_api_erro_vira_mensagem(api):
    assert "erro" in api.pagamentos_salvar({"nome": "", "data": "2026-10-20"})


def test_api_marcar_apagar_e_desfazer(api):
    r = api.pagamentos_salvar({"nome": "Ana", "data": "2026-11-03", "valor": "100"})
    aid = r["atendimentos"][0]["id"]
    r = api.pagamentos_marcar_pago(aid, True, 2026, 11)
    assert r["atendimentos"][0]["pago_em"] == date.today().isoformat()
    r = api.pagamentos_apagar(aid, 2026, 11)
    assert r["atendimentos"] == [] and r["apagado"]["id"] == aid
    r = api.pagamentos_restaurar(r["apagado"], 2026, 11)
    assert r["atendimentos"][0]["id"] == aid and r["atendimentos"][0]["pago_em"]


def test_api_acha_a_nota_na_pasta(api, tmp_path):
    pasta = criar_pasta_exemplo(tmp_path / "NFS-e 2026")
    api._cfg["pasta_notas"] = str(pasta)
    nota = api.notas_do_mes(2026, 10)["notas"][0]
    ano, mes = int(nota["competencia"][:4]), int(nota["competencia"][5:7])
    r = api.pagamentos_salvar({"nome": nota["paciente"].title(), "data": nota["competencia"]})
    assert (r["ano"], r["mes"]) == (ano, mes) and r["notas_lidas"]
    a = next(x for x in r["atendimentos"] if x["nome"] == nota["paciente"].title())
    assert a["nota"] and a["nota_numero"] == nota["numero"]
    # Sem nota achada, dá para marcar à mão
    r = api.pagamentos_salvar({"nome": "Nome Que Nao Existe", "data": nota["competencia"], "nota_manual": True})
    b = next(x for x in r["atendimentos"] if x["nome"] == "Nome Que Nao Existe")
    assert b["nota"] and b["nota_numero"] is None


def test_api_sugere_pacientes_de_orto_com_o_valor(api):
    api.agendamentos_salvar({"nome": "Pedro Exemplo", "valor": "220"})
    r = api.pagamentos_listar(2026, 11)
    assert "Pedro Exemplo" in r["nomes"] and r["orto"]["Pedro Exemplo"] == 22000


def test_exportar_planilha(tmp_path):
    from openpyxl import load_workbook

    lista = [
        {**_atendimento(tratamento="Limpeza", valor_centavos=15000, forma="credito", parcelas=3),
         "situacao": fc.PAGO, "nota": True},
        {**_atendimento(nome="Bia", valor_centavos=None), "situacao": fc.NAO_PAGO, "nota": False},
    ]
    destino = exp.exportar(lista, tmp_path / "ficha", 2026, 11)
    ws = load_workbook(destino).active
    assert [c.value for c in ws[1]] == exp.COLUNAS
    assert [c.value for c in ws[2]][4:] == ["Crédito", "3x", "Sim", "ok"]
    assert [c.value for c in ws[3]][3:] == [None, None, None, "Não", None]
    assert ws.cell(4, 4).value == "=SUM(D2:D3)"


def test_tratamentos_nas_configuracoes():
    assert config.normalizar({})["tratamentos"] == ["Limpeza", "Manutenção", "Botox"]
    assert config.normalizar({"tratamentos": [" Clareamento ", "clareamento", "", "Botox"]})["tratamentos"] == \
        ["Clareamento", "Botox"]
    assert config.normalizar({"tratamentos": []})["tratamentos"] == []
    assert config.normalizar({"tratamentos": "x"})["tratamentos"] == ["Limpeza", "Manutenção", "Botox"]


# --- Contas pagas ------------------------------------------------------------------------


def test_conta_paga_para_de_avisar_naquele_mes():
    [conta] = lb.adicionar_conta([], {"nome": "Aluguel", "dia": 14}, hoje=date(2026, 10, 1))
    assert len(lb.contas_a_avisar([conta], NOV, date(2026, 11, 12))) == 1
    lb.marcar_paga(conta, "2026-11", True, NOV)
    assert lb.contas_a_avisar([conta], NOV, date(2026, 11, 12)) == []
    # No mês seguinte volta a avisar.
    assert len(lb.contas_a_avisar([conta], date(2026, 12, 13), date(2026, 12, 12))) == 1


def test_situacao_da_conta_no_mes():
    [conta] = lb.adicionar_conta([], {"nome": "Aluguel", "dia": 10}, hoje=date(2026, 10, 15))
    assert lb.situacao_no_mes(conta, 2026, 9, NOV) == ""  # antes de começar a acompanhar
    assert lb.situacao_no_mes(conta, 2026, 10, NOV) == lb.NAO_PAGA
    assert lb.situacao_no_mes(conta, 2026, 11, NOV) == lb.EM_ABERTO
    lb.marcar_paga(conta, "2026-10", True, NOV)
    assert lb.situacao_no_mes(conta, 2026, 10, NOV) == lb.PAGA
    lb.marcar_paga(conta, "2026-10", False, NOV)
    assert lb.situacao_no_mes(conta, 2026, 10, NOV) == lb.NAO_PAGA


def test_alterar_ou_desfazer_conta_nao_perde_o_que_foi_pago():
    contas = lb.adicionar_conta([], {"nome": "Água", "dia": 5}, hoje=date(2026, 10, 1))
    lb.marcar_paga(contas[0], "2026-10", True, NOV)
    contas = lb.adicionar_conta(contas, {"nome": "Água e esgoto", "dia": 6}, antiga={"nome": "Água"})
    assert contas[0]["pagas"] == {"2026-10": NOV.isoformat()} and contas[0]["criada_em"] == "2026-10-01"
    apagada = contas[0]
    contas = lb.adicionar_conta(lb.remover_conta(contas, apagada["nome"]), apagada)
    assert contas[0]["pagas"] == {"2026-10": NOV.isoformat()}


def test_api_contas_de_versao_anterior_ganham_a_data_uma_vez(api):
    caminho = config.caminho_whatsapp()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps({"contas": [{"nome": "Luz", "dia": 20}]}), encoding="utf-8")
    r = api.whatsapp_contas()
    [conta] = r["contas"]
    assert conta["criada_em"] == date.today().isoformat() and conta["mes_passado"] == ""
    assert json.loads(caminho.read_text(encoding="utf-8"))["contas"][0]["criada_em"] == date.today().isoformat()


def test_api_marcar_conta_paga(api):
    api.whatsapp_salvar_conta({"nome": "Luz", "dia": 20})
    mes = date.today().isoformat()[:7]
    r = api.whatsapp_marcar_paga("luz", mes, True)
    assert r["contas"][0]["este_mes"] == lb.PAGA
    r = api.whatsapp_marcar_paga("Luz", mes, False)
    assert r["contas"][0]["este_mes"] == lb.EM_ABERTO
    assert "erro" in api.whatsapp_marcar_paga("Água", mes, True)


def test_api_texto_do_lembrete_sem_as_pagas(api):
    api._cfg.update(assistente_nome="João", lembrete_nome="Dra. Exemplo")
    r = api.whatsapp_texto_lembrete([{"nome": "Luz", "situacao": "vence hoje (20/11)"}])
    assert "Luz: vence hoje" in r["mensagem"] and "Dra. Exemplo" in r["mensagem"]


# --- Estrutura ---------------------------------------------------------------------------


def test_modulos_nao_tem_metodos_com_o_mesmo_nome():
    """Cada módulo é uma classe da Api: dois métodos com o mesmo nome, um apaga o outro sem erro."""
    donos: dict[str, list[str]] = {}
    for cls in Api.__mro__[1:]:
        for nome in vars(cls):
            if not nome.startswith("__"):
                donos.setdefault(nome, []).append(cls.__name__)
    assert {n: c for n, c in donos.items() if len(c) > 1} == {}
