import json
from datetime import date
from decimal import Decimal

import pytest

from omac import config, sistema
from omac.app import Api
from omac.notas.leitor import Nota
from omac.atendimentos import exportar as exp
from omac.atendimentos import ficha as fc
from omac.dados import esquema
from omac.lembretes import contas as lb
from tests.fabrica import criar_pasta_exemplo

NOV = date(2026, 11, 13)


def _atendimento(**campos):
    return fc.completar({"id": "x", "contato_id": "c", "data": "2026-11-03", **campos})


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
    ({"nome": "Ana", "data": ""}, "data"),
    ({"nome": "Ana", "data": "2026-02-30"}, "não existe"),
    ({"nome": "Ana", "data": "2026-11-03", "valor": "abc"}, "valor"),
    ({"nome": "Ana", "data": "2026-11-03", "forma": "cheque"}, "forma"),
    ({"nome": "Ana", "data": "2026-11-03", "forma": "credito", "parcelas": 13}, "1 a 12"),
    ({"nome": "Ana", "data": "2026-11-03", "nota": "talvez"}, "nota"),
])
def test_validacao(dados, erro):
    with pytest.raises(fc.AtendimentoInvalido, match=erro):
        fc.adicionar([], "c", dados, NOV)


def test_parcelas_so_valem_no_credito():
    a = fc.adicionar([], "c", {"data": "2026-11-03", "forma": "pix_pf", "parcelas": 5}, NOV)
    assert a["parcelas"] == 1
    a = fc.adicionar([], "c", {"data": "2026-11-03", "forma": "credito", "parcelas": "4"}, NOV)
    assert a["parcelas"] == 4


def test_alterar_mantem_a_data_do_pagamento():
    lista = []
    a = fc.adicionar(lista, "c", {"data": "2026-11-03", "pago": True}, date(2026, 11, 4))
    fc.alterar(lista, a["id"], "d", {"data": "2026-11-03", "pago": True}, NOV)
    assert a["pago_em"] == "2026-11-04" and a["contato_id"] == "d"
    fc.alterar(lista, a["id"], "d", {"data": "2026-11-03", "pago": False}, NOV)
    assert a["pago_em"] == ""


def test_alterar_com_erro_nao_muda_nada():
    lista = []
    a = fc.adicionar(lista, "c", {"data": "2026-11-03", "valor": "100"}, NOV)
    with pytest.raises(fc.AtendimentoInvalido):
        fc.alterar(lista, a["id"], "d", {"data": "2026-11-03", "valor": "xyz"}, NOV)
    assert a["contato_id"] == "c" and a["valor_centavos"] == 10000


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
    assert fc.nota_do_atendimento(_atendimento(), "Ana Souza", notas) == 11
    assert fc.nota_do_atendimento(_atendimento(data="2026-09-10"), "Ana Souza", notas) is None


@pytest.mark.parametrize("marcada, achada, situacao", [
    ("", 12, fc.NOTA_OK), ("", None, fc.FALTA), ("ok", None, fc.NOTA_OK),
    ("nao_precisa", None, fc.NOTA_NAO_PRECISA), ("nao_precisa", 12, fc.NOTA_OK),
])
def test_tres_situacoes_da_nota(marcada, achada, situacao):
    assert fc.situacao_da_nota(_atendimento(nota=marcada), achada) == situacao


# --- Lista ---------------------------------------------------------------------------


def test_meses_e_ordem():
    lista = [_atendimento(id="1", data="2026-11-10"), _atendimento(id="2", data="2026-11-02"),
             _atendimento(id="3", data="2026-10-05")]
    assert [a["id"] for a in fc.do_mes(lista, 2026, 11)] == ["2", "1"]
    assert fc.meses(lista) == [(2026, 10, 1), (2026, 11, 2)]


def test_totais():
    lista = [
        {"valor_centavos": 10000, "situacao": fc.PAGO, "nota_situacao": fc.NOTA_OK},
        {"valor_centavos": 5000, "situacao": fc.AGUARDANDO, "nota_situacao": fc.FALTA},
        {"valor_centavos": None, "situacao": fc.AGUARDANDO, "nota_situacao": fc.FALTA},
        {"valor_centavos": 2000, "situacao": fc.NAO_PAGO, "nota_situacao": fc.NOTA_OK},
        {"valor_centavos": 900, "situacao": fc.PAGO, "nota_situacao": fc.NOTA_NAO_PRECISA},
    ]
    assert fc.totais(lista) == {"recebido_centavos": 10900, "a_receber_centavos": 5000,
                                "nao_pago_centavos": 2000, "nao_pagos": 1, "sem_nota": 2}


# --- API -------------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "abrir_link", lambda u: None)
    return Api()


def test_api_salva_e_lista_o_mes_do_atendimento(api):
    r = api.atendimentos_salvar({"nome": "Ana Exemplo", "data": "2026-10-20", "valor": "150", "forma": "credito",
                               "parcelas": 3, "tratamento": "Limpeza", "pago": True})
    assert "erro" not in r, r
    assert (r["ano"], r["mes"]) == (2026, 10)
    [a] = r["atendimentos"]
    assert a["situacao"] == fc.PAGO and a["forma_texto"] == "Crédito 3x" and a["valor_centavos"] == 15000
    assert r["totais"]["recebido_centavos"] == 15000
    assert r["meses"] == [(2026, 10, 1)]
    assert "Ana Exemplo" in r["nomes"]
    assert r["notas_lidas"] is False

    # Gravado em JSON só com o id do contato; o nome fica em contatos.json.
    salvo = json.loads((config.pasta_dados() / esquema.ATENDIMENTOS).read_text(encoding="utf-8"))
    contatos = json.loads((config.pasta_dados() / esquema.CONTATOS).read_text(encoding="utf-8"))
    assert "nome" not in salvo["atendimentos"][0] and salvo["versao"] == 1
    assert salvo["atendimentos"][0]["contato_id"] == contatos["contatos"][0]["id"]
    assert contatos["contatos"][0]["nome"] == "Ana Exemplo"


def test_api_nome_ja_existente_usa_o_mesmo_contato(api):
    api.atendimentos_salvar({"nome": "Ana Exemplo", "data": "2026-10-20"})
    api.atendimentos_salvar({"nome": "ANA  exemplo", "data": "2026-10-21"})
    assert [c["nome"] for c in api.contatos_listar()["contatos"]] == ["Ana Exemplo"]


def test_api_atendimento_com_erro_nao_cria_contato(api):
    assert "erro" in api.atendimentos_salvar({"nome": "Ana", "data": "2026-02-30"})
    assert api.contatos_listar()["contatos"] == []


def test_api_erro_vira_mensagem(api):
    assert "erro" in api.atendimentos_salvar({"nome": "", "data": "2026-10-20"})


def test_api_marcar_apagar_e_desfazer(api):
    r = api.atendimentos_salvar({"nome": "Ana", "data": "2026-11-03", "valor": "100"})
    aid = r["atendimentos"][0]["id"]
    r = api.atendimentos_marcar_pago(aid, True, 2026, 11)
    assert r["atendimentos"][0]["pago_em"] == date.today().isoformat()
    r = api.atendimentos_apagar(aid, 2026, 11)
    assert r["atendimentos"] == [] and r["apagado"]["id"] == aid and r["apagado_nome"] == "Ana"
    r = api.atendimentos_restaurar(r["apagado"], 2026, 11)
    assert r["atendimentos"][0]["id"] == aid and r["atendimentos"][0]["pago_em"]


def test_api_acha_a_nota_na_pasta(api, tmp_path):
    pasta = criar_pasta_exemplo(tmp_path / "NFS-e 2026")
    api._cfg["pasta_notas"] = str(pasta)
    nota = api.notas_do_mes(2026, 10)["notas"][0]
    ano, mes = int(nota["competencia"][:4]), int(nota["competencia"][5:7])
    r = api.atendimentos_salvar({"nome": nota["paciente"].title(), "data": nota["competencia"]})
    assert (r["ano"], r["mes"]) == (ano, mes) and r["notas_lidas"]
    a = next(x for x in r["atendimentos"] if x["nome"] == nota["paciente"].title())
    assert a["nota_situacao"] == "ok" and a["nota_numero"] == nota["numero"]
    # Sem nota achada, dá para marcar à mão
    r = api.atendimentos_salvar({"nome": "Nome Que Nao Existe", "data": nota["competencia"], "nota": "ok"})
    b = next(x for x in r["atendimentos"] if x["nome"] == "Nome Que Nao Existe")
    assert b["nota_situacao"] == "ok" and b["nota_numero"] is None
    r = api.atendimentos_salvar({"nome": "Outro Nome", "data": nota["competencia"], "nota": "nao_precisa"})
    assert r["totais"]["sem_nota"] == 0


def test_api_sugere_pacientes_de_orto_com_o_valor(api):
    api.contatos_salvar({"nome": "Pedro Exemplo", "orto": True, "valor": "220"})
    api.contatos_salvar({"nome": "Bia Exemplo", "orto": True, "situacao": "finalizado"})
    r = api.atendimentos_listar(2026, 11)
    assert {"Pedro Exemplo", "Bia Exemplo"} <= set(r["nomes"]) and r["orto"] == {"Pedro Exemplo": 22000}
    assert r["sem_nota_por_padrao"] == ["dinheiro", "pix_pf"]


def test_exportar_planilha(tmp_path):
    from openpyxl import load_workbook

    lista = [
        {**_atendimento(tratamento="Limpeza", valor_centavos=15000, forma="credito", parcelas=3),
         "nome": "Ana", "situacao": fc.PAGO, "nota_situacao": fc.NOTA_OK},
        {**_atendimento(valor_centavos=None), "nome": "Bia", "situacao": fc.NAO_PAGO, "nota_situacao": fc.FALTA},
        {**_atendimento(forma="dinheiro"), "nome": "Caio", "situacao": fc.PAGO, "nota_situacao": fc.NOTA_NAO_PRECISA},
    ]
    destino = exp.exportar(lista, tmp_path / "ficha", 2026, 11)
    ws = load_workbook(destino).active
    assert [c.value for c in ws[1]] == exp.COLUNAS
    assert [c.value for c in ws[2]][4:] == ["Crédito", "3x", "Sim", "ok"]
    assert [c.value for c in ws[3]][3:] == [None, None, None, "Não", None]
    assert ws[4][7].value == "não precisa"
    assert ws.cell(5, 4).value == "=SUM(D2:D4)"


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
    caminho = config.pasta_dados() / esquema.LEMBRETES
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps({"versao": 1, "contas": [{"nome": "Luz", "dia": 20}]}), encoding="utf-8")
    r = api.lembretes_contas()
    [conta] = r["contas"]
    assert conta["criada_em"] == date.today().isoformat() and conta["mes_passado"] == ""
    assert json.loads(caminho.read_text(encoding="utf-8"))["contas"][0]["criada_em"] == date.today().isoformat()


def test_api_marcar_conta_paga(api):
    api.lembretes_salvar_conta({"nome": "Luz", "dia": 20})
    mes = date.today().isoformat()[:7]
    r = api.lembretes_marcar_paga("luz", mes, True)
    assert r["contas"][0]["este_mes"] == lb.PAGA
    r = api.lembretes_marcar_paga("Luz", mes, False)
    assert r["contas"][0]["este_mes"] == lb.EM_ABERTO
    assert "erro" in api.lembretes_marcar_paga("Água", mes, True)


def test_api_texto_do_lembrete_sem_as_pagas(api):
    api._cfg.update(assistente_nome="João")
    api.lembretes_definir_destinatario("Dra. Exemplo")
    r = api.lembretes_texto([{"nome": "Luz", "situacao": "vence hoje (20/11)"}])
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
