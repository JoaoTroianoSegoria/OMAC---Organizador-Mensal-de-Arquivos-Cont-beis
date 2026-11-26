"""1.14.0: várias listas na ficha de atendimentos (ex.: Brasília e São Paulo)."""

import json

import pytest

from omac import config, sistema
from omac.app import Api
from omac.atendimentos import exportar as exp
from omac.atendimentos import listas as lst
from omac.dados import esquema
from tests.fabrica import criar_pasta_exemplo


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "abrir_link", lambda u: None)
    return Api()


def _salvar(api, nome, lista_id=None, data="2026-11-10", valor="100", **campos):
    dados = {"nome": nome, "data": data, "valor": valor, **campos}
    if lista_id is not None:
        dados["lista_id"] = lista_id
    r = api.atendimentos_salvar(dados)
    assert "erro" not in r, r
    return r


def test_sem_lista_guardada_existe_a_lista_1():
    assert lst.todas({"atendimentos": []}) == [{"id": "", "nome": "Lista 1"}]
    listas = [{"id": "a", "nome": "Brasília"}, {"id": "b", "nome": "São Paulo"}]
    # Atendimento de antes das listas (ou de lista apagada) aparece na primeira.
    assert lst.da({"lista_id": ""}, listas) == "a" and lst.da({"lista_id": "b"}, listas) == "b"
    assert lst.certa("sumiu", listas) == "a"


def test_atendimentos_antigos_ficam_na_lista_1(api):
    r = _salvar(api, "Ana Exemplo")
    assert r["listas"] == [{"id": "", "nome": "Lista 1", "qtd": 1, "total": 1}] and r["lista_id"] == ""
    salvo = json.loads((config.pasta_dados() / esquema.ATENDIMENTOS).read_text(encoding="utf-8"))
    assert salvo["atendimentos"][0]["lista_id"] == ""


def test_criar_renomear_e_separar(api):
    _salvar(api, "Ana Exemplo", valor="100", pago=True)
    r = api.atendimentos_lista_renomear("", "Brasília", 2026, 11)
    assert [x["nome"] for x in r["listas"]] == ["Brasília"]
    r = api.atendimentos_lista_criar("  São   Paulo ", 2026, 11)
    sp = r["lista_id"]
    assert [x["nome"] for x in r["listas"]] == ["Brasília", "São Paulo"] and r["atendimentos"] == []
    assert "erro" in api.atendimentos_lista_criar("sao paulo", 2026, 11)  # repetido (sem acento)
    assert "erro" in api.atendimentos_lista_criar("  ", 2026, 11)

    r = _salvar(api, "Bia Exemplo", sp, valor="250")
    assert r["lista_id"] == sp and [a["nome"] for a in r["atendimentos"]] == ["Bia Exemplo"]
    assert r["totais"]["a_receber_centavos"] == 25000 and r["totais"]["recebido_centavos"] == 0
    assert r["meses"] == [(2026, 11, 1)]
    assert [(x["nome"], x["qtd"]) for x in r["listas"]] == [("Brasília", 1), ("São Paulo", 1)]

    r = api.atendimentos_listar(2026, 11, "")
    assert [a["nome"] for a in r["atendimentos"]] == ["Ana Exemplo"] and r["totais"]["recebido_centavos"] == 10000

    # O Início (e o resto do app) continua somando todas as listas.
    widget = api._widget_atendimentos(__import__("datetime").date(2026, 11, 20))
    assert widget["qtd"] == 2 and widget["recebido_centavos"] == 10000 and widget["a_receber_centavos"] == 25000


def test_mudar_de_lista_ao_alterar(api):
    sp = api.atendimentos_lista_criar("São Paulo", 2026, 11)["lista_id"]
    r = _salvar(api, "Ana Exemplo", "")
    aid = r["atendimentos"][0]["id"]
    r = api.atendimentos_salvar({"nome": "Ana Exemplo", "data": "2026-11-10", "lista_id": sp}, aid)
    assert r["lista_id"] == sp and [a["id"] for a in r["atendimentos"]] == [aid]
    # Sem lista_id (tela antiga), o alterado fica onde está.
    r = api.atendimentos_salvar({"nome": "Ana Exemplo", "data": "2026-11-11"}, aid)
    assert r["lista_id"] == sp


def test_marcar_apagar_e_desfazer_ficam_na_lista(api):
    sp = api.atendimentos_lista_criar("São Paulo", 2026, 11)["lista_id"]
    aid = _salvar(api, "Bia", sp)["atendimentos"][0]["id"]
    _salvar(api, "Ana", "")
    assert api.atendimentos_marcar_pago(aid, True, 2026, 11, sp)["lista_id"] == sp
    r = api.atendimentos_apagar(aid, 2026, 11, sp)
    assert r["lista_id"] == sp and r["atendimentos"] == []
    r = api.atendimentos_restaurar(r["apagado"], 2026, 11, sp)
    assert [a["id"] for a in r["atendimentos"]] == [aid]


def test_so_apaga_lista_vazia_e_nunca_a_ultima(api):
    assert "erro" in api.atendimentos_lista_apagar("", 2026, 11)  # a única
    sp = api.atendimentos_lista_criar("São Paulo", 2026, 11)["lista_id"]
    _salvar(api, "Bia", sp, data="2026-03-02")  # em outro mês também conta
    erro = api.atendimentos_lista_apagar(sp, 2026, 11)["erro"]
    assert "São Paulo tem 1 atendimento" in erro
    r = api.atendimentos_lista_apagar("", 2026, 11)  # a Lista 1 está vazia
    assert [x["nome"] for x in r["listas"]] == ["São Paulo"] and r["lista_id"] == sp


def test_notas_ligadas_olhando_todas_as_listas(api, tmp_path):
    """A nota achada sozinha na pasta continua indo para o atendimento certo, em qualquer lista."""
    pasta = criar_pasta_exemplo(tmp_path / "NFS-e 2026")
    api._cfg["pasta_notas"] = str(pasta)
    nota = api.notas_do_mes(2026, 10)["notas"][0]
    sp = api.atendimentos_lista_criar("São Paulo", 2026, 10)["lista_id"]
    r = _salvar(api, nota["paciente"].title(), sp, data=nota["competencia"], valor="")
    a = next(x for x in r["atendimentos"] if x["nome"] == nota["paciente"].title())
    assert a["nota_situacao"] == "ok" and a["nota_numero"] == nota["numero"]


def test_planilha_com_o_nome_da_lista(tmp_path):
    from openpyxl import load_workbook

    assert exp.nome_sugerido(2026, 11) == "Atendimentos - Novembro 2026.xlsx"
    assert exp.nome_sugerido(2026, 11, "São Paulo") == "Atendimentos - Novembro 2026 - São Paulo.xlsx"
    assert exp.nome_sugerido(2026, 11, "A/B: C") == "Atendimentos - Novembro 2026 - AB C.xlsx"
    ws = load_workbook(exp.exportar([], tmp_path / "f", 2026, 11, "P&D")).active
    assert ws.oddHeader.center.text == "Atendimentos de Novembro de 2026 - P&&D"
    assert not load_workbook(exp.exportar([], tmp_path / "g", 2026, 11)).active.oddHeader.center.text
