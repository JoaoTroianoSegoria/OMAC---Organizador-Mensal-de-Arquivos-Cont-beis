"""1.12.0: cobrar um atendimento pelo WhatsApp (Atendimentos) e o modelo da mensagem."""

from datetime import date

import pytest

from omac import sistema
from omac.app import Api
from omac.whatsapp import variaveis as vr


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    abertos = []
    monkeypatch.setattr(sistema, "abrir_link", abertos.append)
    a = Api()
    a.abertos = abertos
    a._cfg.update(assistente_nome="Exemplo", chave_pix="chave@exemplo.com")
    return a


def _atendimento(api, nome="Pedro Alves Souza", **campos):
    dados = {"nome": nome, "tratamento": "Manutenção", "data": "2026-11-21", "valor": "220,00",
             "forma": "pix_pj", **campos}
    r = api.atendimentos_salvar(dados)
    return next(a for a in r["atendimentos"] if a["nome"] == nome)


def test_mensagem_padrao_com_tudo():
    texto = vr.mensagem_cobranca({"assistente_nome": "Exemplo", "chave_pix": "chave@x.com"}, "HELENA ALVES",
                                 "PEDRO ALVES SOUZA", date(2026, 11, 21), "Manutenção", 22000)
    assert texto.startswith("*Assistente Exemplo:* Olá, Helena.")
    assert "atendimento de Pedro em 21/11 (Manutenção), no valor de R$ 220,00." in texto
    assert "chave@x.com" in texto


def test_sem_tratamento_nem_valor_o_texto_fica_limpo():
    texto = vr.mensagem_cobranca({}, "Pedro", "Pedro", date(2026, 11, 21), "", None)
    assert "atendimento de Pedro em 21/11." in texto
    assert "()" not in texto and "no valor de" not in texto


def test_modelo_nas_configuracoes(api):
    modelos = api.mensagens_modelos()
    assert modelos["cobranca"]["modelo"] == vr.MODELO_COBRANCA
    assert {v["nome"] for v in modelos["cobranca"]["variaveis"]} >= {"data-do-atendimento", "chave-pix", "valor"}
    assert "erro" in api.mensagens_salvar("cobranca", "Oi [numero-da-nota]")  # variável de nota não vale aqui
    api.mensagens_salvar("cobranca", "Oi [primeiro-nome-do-responsavel], falta o de [data-do-atendimento].")
    a = _atendimento(api)
    r = api.atendimentos_preparar_cobranca(a["id"])
    assert r["destinos"][0]["mensagem"] == "Oi Pedro, falta o de 21/11."
    assert r["sem_pix"] is False  # o modelo não usa a chave Pix
    previa = api.mensagens_previa("cobranca", vr.MODELO_COBRANCA)
    assert "Lucas" in previa["texto"] and previa["desconhecidas"] == []
    assert api.mensagens_padrao("cobranca")["config"]["mensagem_cobranca"] == ""


def test_preparar_e_cobrar_guarda_o_telefone_e_a_escolha(api):
    helena = api.contatos_salvar({"nome": "Helena Alves"})["salvo"]
    api.contatos_salvar({"nome": "Pedro Alves Souza",
                         "responsaveis": [{"contato_id": helena["id"], "papel": "mae"}]})
    a = _atendimento(api)
    r = api.atendimentos_preparar_cobranca(a["id"])
    assert [d["nome"] for d in r["destinos"]] == ["Pedro Alves Souza", "Helena Alves"]
    assert "Olá, Helena." in r["destinos"][1]["mensagem"]
    assert r["valor_centavos"] == 22000 and r["sem_pix"] is False
    assert "telefone" in api.atendimentos_cobrar(a["id"], helena["id"], "123", "oi")["erro"]
    assert api.atendimentos_cobrar(a["id"], helena["id"], "(61) 90000-0005", "oi") == {}
    assert api.abertos and "5561900000005" in api.abertos[0]
    # Da próxima vez já vem escolhida a mãe, com o telefone.
    r = api.atendimentos_preparar_cobranca(a["id"])
    assert r["escolhido"] == helena["id"] and r["destinos"][1]["telefone"] == "5561900000005"


def test_sem_chave_pix_avisa(api):
    api._cfg["chave_pix"] = ""
    a = _atendimento(api)
    assert api.atendimentos_preparar_cobranca(a["id"])["sem_pix"] is True


def test_quem_nao_e_responsavel_nao_recebe(api):
    a = _atendimento(api)
    outro = api.contatos_salvar({"nome": "Outra Pessoa"})["salvo"]
    assert "Escolha" in api.atendimentos_cobrar(a["id"], outro["id"], "(61) 90000-0005", "oi")["erro"]
