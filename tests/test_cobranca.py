"""1.12.0: cobrar um atendimento pelo WhatsApp (Atendimentos) e o modelo da mensagem."""

from datetime import date

import pytest

from omac import sistema
from omac.app import Api
from omac.whatsapp import catalogo as cat


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
    texto = cat.cobranca({"assistente_nome": "Exemplo", "chave_pix": "chave@x.com"}, "HELENA ALVES", "mãe",
                         "PEDRO ALVES SOUZA", date(2026, 11, 21), "Manutenção", 22000)
    assert texto.startswith("*Assistente Exemplo:* Olá, Helena.")
    assert "atendimento de Pedro em 21/11 (Manutenção), no valor de R$ 220,00." in texto
    assert "chave@x.com" in texto


def test_para_o_proprio_paciente_e_o_seu_atendimento():
    texto = cat.cobranca({}, "Pedro", "", "Pedro", date(2026, 11, 21), "", None)
    assert texto.startswith("Olá, Pedro.\nPassando para lembrar do pagamento do seu atendimento em 21/11.")
    assert "()" not in texto and "no valor de" not in texto


def test_modelo_nas_configuracoes(api):
    grupos = api.mensagens_modelos()["grupos"]
    cobranca = next(m for g in grupos for m in g["mensagens"] if m["tipo"] == "cobranca")
    assert {v["nome"] for v in cobranca["variaveis"]} >= {"data-do-atendimento", "chave-pix", "valor"}
    assert [v["versao"] for v in cobranca["versoes"]] == ["paciente", "responsavel"]
    assert "erro" in api.mensagens_salvar("cobranca", "paciente", "Oi [numero-da-nota]")  # variável de nota não vale
    api.mensagens_salvar("cobranca", "paciente", "Oi [primeiro-nome-do-paciente], falta o de [data-do-atendimento].")
    a = _atendimento(api)
    r = api.atendimentos_preparar_cobranca(a["id"])
    assert r["destinos"][0]["mensagem"] == "Oi Pedro, falta o de 21/11."
    assert r["sem_pix"] is False  # a chave está preenchida
    previa = api.mensagens_previa("cobranca", "responsavel", cobranca["versoes"][1]["padrao"])
    assert "Olá, Fernanda" in previa["texto"] and "de Lucas" in previa["texto"] and previa["desconhecidas"] == []
    assert "cobranca" not in api.mensagens_padrao("cobranca", "paciente")["config"]["mensagens"]


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
