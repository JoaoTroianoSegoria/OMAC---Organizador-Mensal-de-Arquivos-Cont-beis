"""Contatos: cadastro único, responsáveis, apagar com desfazer e "Conferir contatos"."""

import pytest

from omac import sistema
from omac.app import Api
from omac.contatos import contatos as ct
from omac.dados import esquema

TEL, TEL2 = "5561900000000", "5561922222222"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "abrir_link", lambda u: None)
    return Api()


def _salvar(api, contato_id=None, **dados):
    r = api.contatos_salvar(dados, contato_id)
    assert "erro" not in r, r
    return r


def _por_nome(r):
    return {c["nome"]: c for c in r["contatos"]}


# --- Cadastro -----------------------------------------------------------------------------


def test_cria_altera_e_lista_em_ordem(api):
    _salvar(api, nome="  Bia   Lima ", telefone="(61) 90000-0000")
    r = _salvar(api, nome="Ana Souza")
    assert [c["nome"] for c in r["contatos"]] == ["Ana Souza", "Bia Lima"]
    bia = _por_nome(r)["Bia Lima"]
    assert bia["telefone"] == TEL and bia["tratamento"] is None and bia["atendimentos"] == 0
    r = _salvar(api, bia["id"], nome="Beatriz Lima", telefone="")
    assert _por_nome(r)["Beatriz Lima"]["id"] == bia["id"] and _por_nome(r)["Beatriz Lima"]["telefone"] == ""


@pytest.mark.parametrize("dados, trecho", [
    ({"nome": " "}, "nome"),
    ({"nome": "Ana", "telefone": "123"}, "telefone"),
    ({"nome": "Ana", "responsaveis": [{"nome": "Mãe", "papel": "tia"}]}, "Escolha quem é"),
    ({"nome": "Ana", "responsaveis": [{"nome": "ana", "papel": "mae"}]}, "outra pessoa"),
    ({"nome": "Ana", "orto": True, "valor": "abc"}, "valor"),
    ({"nome": "Ana", "orto": True, "situacao": "alta"}, "alta foi dada"),
])
def test_dados_ruins_nao_salvam_nada(api, dados, trecho):
    assert trecho in api.contatos_salvar(dados)["erro"]
    assert api.contatos_listar()["contatos"] == []
    assert api.tratamentos_listar()["ativos"] == []


def test_nome_repetido_e_recusado(api):
    _salvar(api, nome="Joana Exemplo")
    assert "Já existe" in api.contatos_salvar({"nome": "JOANÁ  exemplo"})["erro"]
    j = api.contatos_listar()["contatos"][0]
    assert "erro" not in api.contatos_salvar({"nome": "Joana Exemplo", "telefone": TEL}, j["id"])


def test_responsavel_escolhido_da_lista_ou_criado_na_hora(api):
    mae = _salvar(api, nome="Helena Lima")["salvo"]
    r = _salvar(api, nome="Pedro Lima", responsaveis=[
        {"contato_id": mae["id"], "nome": "Helena Lima", "telefone": "(61) 92222-2222", "papel": "mae"},
        {"nome": "Carlos Lima", "papel": "pai"},
        {"nome": "", "papel": "outro"},  # linha vazia é ignorada
    ])
    c = _por_nome(r)
    assert [(x["nome"], x["papel_texto"]) for x in c["Pedro Lima"]["responsaveis"]] == [("Helena Lima", "mãe"),
                                                                                       ("Carlos Lima", "pai")]
    assert c["Helena Lima"]["telefone"] == TEL2  # o telefone digitado ali é o do responsável
    assert c["Carlos Lima"]["dependentes"] == ["Pedro Lima"]


def test_conjuge_e_outro_tambem_sao_responsaveis(api):
    r = _salvar(api, nome="Ana", responsaveis=[{"nome": "Bruno", "papel": "conjuge"}, {"nome": "Tia Rosa", "papel": "outro"}])
    assert [x["papel_texto"] for x in _por_nome(r)["Ana"]["responsaveis"]] == ["cônjuge", "responsável"]


def test_orto_liga_e_desliga_pela_janela_de_contato(api):
    r = _salvar(api, nome="Ana", orto=True, valor="250")
    ana = _por_nome(r)["Ana"]
    assert ana["tratamento"]["situacao"] == "ativo" and ana["tratamento"]["valor_centavos"] == 25000
    r = _salvar(api, ana["id"], nome="Ana", orto=False)
    assert r["tratamento_apagado"]["contato_id"] == ana["id"] and _por_nome(r)["Ana"]["tratamento"] is None
    api.contatos_restaurar_tratamento(r["tratamento_apagado"])
    assert _por_nome(api.contatos_listar())["Ana"]["tratamento"]["valor_centavos"] == 25000


# --- Apagar e desfazer ------------------------------------------------------------------------


def test_apagar_leva_o_tratamento_e_os_vinculos_e_desfaz_tudo(api):
    _salvar(api, nome="Pedro", orto=True, responsaveis=[{"nome": "Helena", "papel": "mae"}])
    helena = _por_nome(api.contatos_listar())["Helena"]
    pedro = _por_nome(api.contatos_listar())["Pedro"]
    api.whatsapp_definir_destinatario("Helena")
    # Pedro manda para a mãe:
    mae = api.tratamentos_preparar_mensagens(api.tratamentos_listar()["ativos"][0]["id"])["destinos"][1]
    api.tratamentos_enviar(api.tratamentos_listar()["ativos"][0]["id"], mae["contato_id"], TEL, "oi")

    r = api.contatos_apagar(helena["id"])
    assert set(_por_nome(r)) == {"Pedro"} and _por_nome(r)["Pedro"]["responsaveis"] == []
    assert api.whatsapp_destinatario()["contato"] is None
    r = api.contatos_restaurar(r["apagado"])
    p = _por_nome(r)["Pedro"]
    assert [x["contato_id"] for x in p["responsaveis"]] == [helena["id"]] and p["envia_para"] == helena["id"]
    assert api.whatsapp_destinatario()["contato"]["id"] == helena["id"]

    r = api.contatos_apagar(pedro["id"])
    assert api.tratamentos_listar()["ativos"] == []
    api.contatos_restaurar(r["apagado"])
    api.contatos_restaurar(r["apagado"])  # desfazer duas vezes não duplica
    assert len(api.tratamentos_listar()["ativos"]) == 1 and len(api.contatos_listar()["contatos"]) == 2


def test_quem_tem_atendimento_nao_pode_ser_apagado(api):
    api.atendimentos_salvar({"nome": "Ana", "data": "2026-11-03"})
    ana = api.contatos_listar()["contatos"][0]
    assert "1 atendimento" in api.contatos_apagar(ana["id"])["erro"]
    assert len(api.contatos_listar()["contatos"]) == 1


# --- Para quem vai a mensagem ------------------------------------------------------------------


def test_destinos_e_ultima_escolha():
    contatos = [ct.novo("Pedro"), ct.novo("Helena", TEL)]
    pedro, helena = contatos
    pedro["responsaveis"] = [{"contato_id": helena["id"], "papel": "mae"}]
    assert [d["papel"] for d in ct.destinos(contatos, pedro)] == ["", "mãe"]
    assert ct.destino_escolhido(contatos, pedro)["nome"] == "Pedro"
    pedro["envia_para"] = helena["id"]
    assert ct.destino_escolhido(contatos, pedro)["telefone"] == TEL
    pedro["envia_para"] = "sumiu"
    assert ct.destino_escolhido(contatos, pedro)["nome"] == "Pedro"


def test_tirar_o_responsavel_escolhido_volta_para_o_proprio(api):
    _salvar(api, nome="Pedro", orto=True, responsaveis=[{"nome": "Helena", "papel": "mae"}])
    t = api.tratamentos_listar()["ativos"][0]
    mae = api.tratamentos_preparar_mensagens(t["id"])["destinos"][1]
    api.tratamentos_enviar(t["id"], mae["contato_id"], TEL, "oi")
    _salvar(api, t["contato_id"], nome="Pedro", orto=True, responsaveis=[])
    assert api.tratamentos_listar()["ativos"][0]["destino"]["nome"] == "Pedro"


# --- Conferir contatos -------------------------------------------------------------------------


def _com_a_conferir(api, itens):
    with api._armazem.editar(esquema.CONTATOS) as d:
        d["a_conferir"] = itens


def test_parecidos():
    contatos = [ct.novo("Pedro Lima"), ct.novo("PEDRO SOUZA LIMA"), ct.novo("Pedro"), ct.novo("Ana Lima")]
    assert ct.parecidos(contatos) == [[contatos[0]["id"], contatos[1]["id"]]]


def test_juntar_passa_tudo_para_quem_fica(api):
    _salvar(api, nome="Pedro Lima", orto=True)
    _salvar(api, nome="PEDRO SOUZA LIMA", telefone=TEL)
    _salvar(api, nome="Bia", responsaveis=[{"nome": "PEDRO SOUZA LIMA", "papel": "pai"}])
    api.atendimentos_salvar({"nome": "PEDRO SOUZA LIMA", "data": "2026-11-03"})
    api.whatsapp_definir_destinatario("PEDRO SOUZA LIMA")
    c = _por_nome(api.contatos_listar())
    fica, sai = c["Pedro Lima"], c["PEDRO SOUZA LIMA"]
    _com_a_conferir(api, [{"tipo": "parecidos", "ids": [fica["id"], sai["id"]]}])
    assert api.contatos_listar()["a_conferir"][0]["nomes"] == ["Pedro Lima", "PEDRO SOUZA LIMA"]

    r = api.contatos_juntar(fica["id"], sai["id"])
    c = _por_nome(r)
    assert set(c) == {"Pedro Lima", "Bia"} and r["a_conferir"] == []
    assert c["Pedro Lima"]["telefone"] == TEL and c["Pedro Lima"]["atendimentos"] == 1
    assert c["Bia"]["responsaveis"][0]["contato_id"] == fica["id"]
    assert api.whatsapp_destinatario()["contato"]["id"] == fica["id"]
    assert api.tratamentos_listar()["ativos"][0]["nome"] == "Pedro Lima"


def test_nao_junta_dois_pacientes_de_orto(api):
    a = _salvar(api, nome="Pedro Lima", orto=True)["salvo"]
    b = _salvar(api, nome="Pedro Souza Lima", orto=True)["salvo"]
    assert "Tratamentos" in api.contatos_juntar(a["id"], b["id"])["erro"]
    assert len(api.contatos_listar()["contatos"]) == 2


def test_sao_pessoas_diferentes(api):
    a = _salvar(api, nome="Pedro Lima")["salvo"]
    b = _salvar(api, nome="Pedro Souza Lima")["salvo"]
    _com_a_conferir(api, [{"tipo": "parecidos", "ids": [a["id"], b["id"]]}])
    r = api.contatos_sao_diferentes([b["id"], a["id"]])
    assert r["a_conferir"] == [] and len(r["contatos"]) == 2


def test_escolher_o_telefone_certo(api):
    a = _salvar(api, nome="Maria", telefone=TEL)["salvo"]
    _com_a_conferir(api, [{"tipo": "telefone", "id": a["id"], "telefones": [TEL, TEL2]}])
    item = api.contatos_listar()["a_conferir"][0]
    assert (item["nome"], item["atual"]) == ("Maria", TEL)
    r = api.contatos_escolher_telefone(a["id"], TEL2)
    assert r["a_conferir"] == [] and r["contatos"][0]["telefone"] == TEL2


def test_a_conferir_de_contato_apagado_some_sozinho(api):
    a = _salvar(api, nome="Pedro Lima")["salvo"]
    b = _salvar(api, nome="Pedro Souza Lima")["salvo"]
    _com_a_conferir(api, [{"tipo": "parecidos", "ids": [a["id"], b["id"]]}])
    api.contatos_apagar(b["id"])
    assert api.contatos_listar()["a_conferir"] == []
    assert api.inicio_painel()["widgets"]["contatos"]["a_conferir"] == 0
