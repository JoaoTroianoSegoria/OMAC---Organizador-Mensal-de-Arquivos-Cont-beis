import json
from datetime import date
from decimal import Decimal

import pytest

from omac import config, sistema
from omac.agendamentos import pacientes as pc
from omac.app import Api
from omac.notas.leitor import Nota
from omac.resumo import ano as resumo
from tests.fabrica import criar_pasta_exemplo

NOV = date(2026, 11, 13)


def _paciente(**campos):
    return pc.completar({"id": "p", "nome": "Ana", "criado_em": "2026-08-10", **campos})


# --- Atendido e histórico ------------------------------------------------------------------


def test_situacao_no_mes():
    p = _paciente(atendidos={"2026-09": "2026-09-05", "2026-11": "2026-11-03"})
    assert pc.situacao_no_mes(p, 2026, 7, NOV) == pc.FORA  # antes do cadastro
    assert pc.situacao_no_mes(p, 2026, 8, NOV) == pc.NAO_VEIO
    assert pc.situacao_no_mes(p, 2026, 9, NOV) == pc.VEIO
    assert pc.situacao_no_mes(p, 2026, 10, NOV) == pc.NAO_VEIO
    assert pc.situacao_no_mes(p, 2026, 11, NOV) == pc.VEIO
    assert pc.situacao_no_mes(p, 2026, 12, NOV) == pc.FORA  # ainda não chegou
    assert pc.situacao_no_mes(_paciente(), 2026, 11, NOV) == pc.FALTA_VIR


def test_mes_marcado_antes_do_cadastro_estende_o_historico():
    p = _paciente(atendidos={"2026-06": "2026-11-13"})
    assert pc.situacao_no_mes(p, 2026, 6, NOV) == pc.VEIO
    assert pc.situacao_no_mes(p, 2026, 7, NOV) == pc.NAO_VEIO


def test_alta_atual_e_alta_que_acabou_aparecem_como_alta():
    p = _paciente(alta_inicio="2026-09-15", alta_fim="2026-12-01")
    assert pc.situacao_no_mes(p, 2026, 8, NOV) == pc.NAO_VEIO
    assert pc.situacao_no_mes(p, 2026, 9, NOV) == pc.DE_ALTA
    assert pc.situacao_no_mes(p, 2026, 11, NOV) == pc.DE_ALTA
    pc.voltar_ao_tratamento(p)
    assert p["altas"] == [{"inicio": "2026-09-15", "fim": "2026-12-01"}]
    assert pc.situacao_no_mes(p, 2026, 10, NOV) == pc.DE_ALTA
    # Quem veio no mês da alta aparece como "veio".
    pc.marcar_atendido(p, "2026-09", True, NOV)
    assert pc.situacao_no_mes(p, 2026, 9, NOV) == pc.VEIO


def test_mudar_de_alta_para_finalizado_guarda_a_alta():
    pacientes = []
    p = pc.adicionar(pacientes, {"nome": "Ana", "situacao": "alta", "alta_inicio": "2026-09-01",
                                 "alta_fim": "2026-10-01"}, date(2026, 8, 1))
    pc.alterar(pacientes, p["id"], {"nome": "Ana", "situacao": "finalizado"}, date(2026, 10, 20))
    assert p["altas"] == [{"inicio": "2026-09-01", "fim": "2026-10-01"}]
    assert pc.situacao_no_mes(p, 2026, 9, NOV) == pc.DE_ALTA
    assert pc.situacao_no_mes(p, 2026, 11, NOV) == pc.FORA  # depois de finalizar


def test_nao_marca_mes_que_nao_chegou():
    with pytest.raises(pc.PacienteInvalido, match="não chegou"):
        pc.marcar_atendido(_paciente(), "2026-12", True, NOV)


def test_historico_do_paciente_conta_so_meses_fechados_ou_marcados():
    p = _paciente(atendidos={"2026-09": "x", "2026-10": "x"})
    h = pc.historico_do_paciente(p, NOV)
    assert [(m["mes"], m["situacao"]) for m in h["meses"]] == [
        (11, pc.FALTA_VIR), (10, pc.VEIO), (9, pc.VEIO), (8, pc.NAO_VEIO)]
    assert (h["veio"], h["esperados"]) == (2, 3)


def test_meses_ate_vira_o_ano():
    assert pc.meses_ate(2027, 2, 4) == [(2026, 11), (2026, 12), (2027, 1), (2027, 2)]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "abrir_link", lambda u: None)
    return Api()


def test_api_atendido_e_historico(api):
    r = api.agendamentos_salvar({"nome": "Ana"})
    pid = r["ativos"][0]["id"]
    assert r["ativos"][0]["atendido"] is False
    mes = date.today().isoformat()[:7]
    r = api.agendamentos_marcar_atendido(pid, mes, True)
    assert r["ativos"][0]["atendido"] is True
    h = api.agendamentos_historico(date.today().year, date.today().month, 3)
    assert len(h["meses"]) == 3 and h["meses"][-1]["veio"] == 1
    assert h["pacientes"][0]["meses"][-1] == pc.VEIO
    hp = api.agendamentos_historico_paciente(pid)
    assert hp["nome"] == "Ana" and hp["veio"] == 1
    assert "erro" in api.agendamentos_marcar_atendido(pid, "2999-01", True)


def test_historico_deixa_de_fora_quem_nao_era_paciente_no_periodo(api):
    api.agendamentos_salvar({"nome": "Ana"})
    assert api.agendamentos_historico(2020, 6, 6)["pacientes"] == []


# --- Resumo do ano ----------------------------------------------------------------------


def _nota(numero, valor, competencia):
    return Nota(numero, "X", Decimal(valor), competencia, competencia, f"{numero}.pdf")


def test_resumo_mes_sem_nota_fica_em_branco_e_o_atual_nao_entra_na_media():
    notas = [_nota(1, "100", date(2026, 9, 5)), _nota(2, "300", date(2026, 10, 5)),
             _nota(3, "50", date(2026, 11, 2)), _nota(4, "999", date(2025, 10, 1))]
    r = resumo.montar(2026, NOV, notas, {10: (40000, 15000)}, {11: {"recebido_centavos": 500, "pendente_centavos": 100, "qtd": 2}})
    meses = {m["mes"]: m for m in r["meses"]}
    assert meses[8]["faturamento_centavos"] is None and meses[9]["faturamento_centavos"] == 10000
    assert r["faturamento_centavos"] == 45000  # o ano todo, com o mês atual
    assert r["media_centavos"] == 20000 and r["meses_na_media"] == 2  # setembro e outubro
    assert (r["melhor"], r["pior"]) == (10, 9)
    assert r["sem_notas"] == [1, 2, 3, 4, 5, 6, 7, 8]  # novembro ainda pode ganhar notas
    assert meses[10]["entradas_centavos"] == 40000 and meses[9]["entradas_centavos"] is None
    assert meses[11]["recebido_centavos"] == 500
    assert r["comparacao"] == {"mes": 10, "anterior": 9, "variacao": 200.0}


def test_resumo_sem_pasta_de_notas():
    r = resumo.montar(2026, NOV, None, None, {})
    assert r["notas_lidas"] is False and r["sem_notas"] == [] and r["faturamento_centavos"] is None


def test_resumo_de_ano_que_passou_conta_os_12_meses():
    r = resumo.montar(2025, NOV, [_nota(1, "10", date(2025, 12, 1))], None, {})
    assert r["sem_notas"] == list(range(1, 12)) and r["meses_na_media"] == 1


def test_api_resumo_com_a_pasta_de_exemplo(api, tmp_path):
    pasta = criar_pasta_exemplo(tmp_path / "NFS-e 2026")
    api._cfg.update(pasta_notas=str(pasta), pasta_extratos=str(pasta / "Extratos"))
    api.pagamentos_salvar({"nome": "Ana", "data": "2026-10-05", "valor": "100"})
    r = api.resumo_ano(2026)
    out = r["meses"][9]
    assert out["notas"] > 0 and out["faturamento_centavos"] > 0 and out["entradas_centavos"] is not None
    assert out["pendente_centavos"] == 10000
    assert 2026 in r["anos"]


# --- Início --------------------------------------------------------------------------------


def test_api_painel_tem_todos_os_cartoes_mesmo_sem_pastas(api):
    r = api.inicio_painel()
    for nome in ("contas", "ficha", "orto", "notas_enviar", "fechamento", "resumo"):
        assert nome in r and "erro" not in r[nome], (nome, r[nome])
    assert r["notas_enviar"] == {"sem_pasta": True}


def test_api_painel_um_cartao_com_erro_nao_derruba_os_outros(api, monkeypatch):
    monkeypatch.setattr(type(api), "_cartao_orto", lambda self, hoje: 1 / 0)
    r = api.inicio_painel()
    assert "erro" in r["orto"] and "erro" not in r["contas"]


def test_api_painel_pendencias(api):
    caminho = config.caminho_whatsapp()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps({"contas": [{"nome": "Luz", "dia": 1, "criada_em": "2020-01-01", "pagas": {}}]}),
                       encoding="utf-8")
    r = api.inicio_painel()
    assert r["contas"]["nao_pagas_mes_passado"] == ["Luz"]
    assert r["contas"]["abertas"][0]["nome"] == "Luz"


def test_cartoes_da_tela_inicial():
    padrao = config.normalizar({})["inicio_cartoes"]
    assert [c["id"] for c in padrao] == [c["id"] for c in config.CARTOES_INICIO]
    escolhidos = config.normalizar({"inicio_cartoes": [
        {"id": "resumo", "visivel": False, "largo": False}, {"id": "nao_existe"}, {"id": "resumo"}, "lixo",
    ]})["inicio_cartoes"]
    assert escolhidos[0] == {"id": "resumo", "visivel": False, "largo": False}
    assert len(escolhidos) == len(config.CARTOES_INICIO)  # os que faltaram voltam no fim
    assert config.normalizar({"abrir_em": "x"})["abrir_em"] == "inicio"
