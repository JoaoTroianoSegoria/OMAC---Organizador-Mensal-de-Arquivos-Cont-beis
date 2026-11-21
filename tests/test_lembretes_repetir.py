"""1.9.0: lembretes que repetem (todo dia, toda semana, todo mês, numa data) e o envio pelo WhatsApp."""

from datetime import date, timedelta
from unittest import mock

import pytest

from omac import sistema
from omac.app import Api
from omac.lembretes import livres as lv
from omac.whatsapp import mensagens as msg

SEG = date(2026, 11, 16)  # uma segunda-feira
TEL = "5561900000000"


def _item(**campos):
    base = {"id": "x", "titulo": "T", "observacao": "", "feito_em": "", "criado_em": "2026-11-01",
            "desde": "2026-11-01", "repetir": "nao", "dia_semana": 0, "dia_mes": 1, "data": "", "destinatario": ""}
    return {**base, **campos}


# --- Quando aparece --------------------------------------------------------------------------


def test_sem_repetir_continua_como_antes():
    item = _item()
    assert lv.pendente(item, SEG) and not lv.terminado(item) and lv.proxima(item, SEG) is None
    item["feito_em"] = "2026-11-16"
    assert not lv.pendente(item, SEG) and lv.terminado(item)


def test_todo_dia_volta_no_dia_seguinte():
    item = _item(repetir="dia")
    assert lv.pendente(item, SEG)
    lv.marcar_feito(item, True, SEG)
    assert not lv.pendente(item, SEG)
    assert lv.pendente(item, SEG + timedelta(days=1))
    assert lv.proxima(item, SEG) == SEG + timedelta(days=1)
    assert not lv.terminado(item)


def test_toda_semana_no_dia_escolhido():
    item = _item(repetir="semana", dia_semana=2)  # quarta
    assert lv.ocorrencia(item, SEG) == date(2026, 11, 11)  # a quarta passada
    assert lv.pendente(item, SEG)  # ficou sem fazer: continua aparecendo
    lv.marcar_feito(item, True, SEG)
    assert not lv.pendente(item, SEG + timedelta(days=1))  # terça
    assert lv.pendente(item, date(2026, 11, 18))  # quarta
    assert lv.proxima(item, SEG) == date(2026, 11, 18)
    assert lv.quando(item) == "toda quarta"
    assert lv.quando(_item(repetir="semana", dia_semana=5)) == "todo sábado"


def test_todo_mes_e_dia_31_em_mes_curto():
    item = _item(repetir="mes", dia_mes=31, desde="2026-01-01")
    assert lv.ocorrencia(item, date(2027, 2, 27)) == date(2027, 1, 31)
    assert lv.ocorrencia(item, date(2027, 2, 28)) == date(2027, 2, 28)
    lv.marcar_feito(item, True, date(2027, 2, 28))
    assert not lv.pendente(item, date(2027, 3, 30))
    assert lv.pendente(item, date(2027, 3, 31))
    assert lv.proxima(item, date(2027, 2, 28)) == date(2027, 3, 31)
    assert lv.quando(item) == "todo dia 31 do mês"


def test_vezes_de_antes_de_criar_nao_contam():
    # Criado dia 21 para lembrar todo dia 5: o primeiro é o de dezembro.
    item = _item(repetir="mes", dia_mes=5, criado_em="2026-11-21", desde="2026-11-21")
    assert not lv.pendente(item, date(2026, 11, 21))
    assert lv.proxima(item, date(2026, 11, 21)) == date(2026, 12, 5)
    assert lv.pendente(item, date(2026, 12, 5))
    # Criado no próprio dia: já aparece.
    assert lv.pendente(_item(repetir="mes", dia_mes=21, desde="2026-11-21"), date(2026, 11, 21))


def test_num_dia_especifico_aparece_e_depois_de_feito_nao_volta():
    item = _item(repetir="data", data="2026-12-24")
    assert not lv.pendente(item, SEG) and lv.proxima(item, SEG) == date(2026, 12, 24)
    assert lv.pendente(item, date(2026, 12, 24))
    assert lv.pendente(item, date(2026, 12, 26))  # PC desligado no dia: aparece depois
    lv.marcar_feito(item, True, date(2026, 12, 26))
    assert not lv.pendente(item, date(2027, 1, 10)) and lv.terminado(item)
    assert lv.quando(item) == "em 24/12/2026"


@pytest.mark.parametrize("dados, trecho", [
    ({"titulo": "A", "repetir": "ano"}, "quando repetir"),
    ({"titulo": "A", "repetir": "semana", "dia_semana": 7}, "dia da semana"),
    ({"titulo": "A", "repetir": "mes", "dia_mes": 0}, "1 a 31"),
    ({"titulo": "A", "repetir": "data", "data": "31/12"}, "data"),
])
def test_repeticao_invalida(dados, trecho):
    with pytest.raises(lv.LembreteInvalido, match=trecho):
        lv.salvar([], dados, None, SEG)


def test_mudar_a_repeticao_recomeca_de_hoje():
    livres = []
    item = lv.salvar(livres, {"titulo": "Pagar", "repetir": "mes", "dia_mes": 10}, None, date(2026, 11, 1))
    lv.marcar_feito(item, True, date(2026, 11, 10))
    lv.salvar(livres, {"titulo": "Pagar", "repetir": "mes", "dia_mes": 10}, item["id"], date(2026, 11, 12))
    assert item["feito_em"] == "2026-11-10" and item["desde"] == "2026-11-01"  # mesma regra: nada muda
    lv.salvar(livres, {"titulo": "Pagar", "repetir": "mes", "dia_mes": 5}, item["id"], date(2026, 11, 12))
    assert item["desde"] == "2026-11-12" and item["feito_em"] == ""
    assert not lv.pendente(item, date(2026, 11, 12))  # o dia 5 de novembro já passou antes da mudança
    assert lv.pendente(item, date(2026, 12, 5))


def test_listas_da_tela():
    livres = [_item(id="a"), _item(id="b", repetir="dia"), _item(id="c", repetir="data", data="2026-12-24"),
              _item(id="d", feito_em="2026-11-10"), _item(id="e", repetir="mes", dia_mes=20, feito_em="2026-11-16")]
    assert [x["id"] for x in lv.em_aberto(livres, SEG)] == ["a", "b"]
    assert [x["id"] for x in lv.programados(livres, SEG)] == ["e", "c"]  # 20/11 antes de 24/12
    assert [x["id"] for x in lv.feitos(livres)] == ["d"]
    assert [x["id"] for x in lv.a_lembrar_ao_abrir(livres, SEG)] == ["b"]  # só os que repetem


# --- Pela API ------------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    abertos = []
    monkeypatch.setattr(sistema, "abrir_link", abertos.append)
    a = Api()
    a.abertos = abertos
    a._cfg.update(assistente_nome="João", lembrete_fechamento_dia=0)
    return a


def test_lembrete_que_repete_aparece_toda_vez_que_o_app_abre(api):
    item = api.lembretes_salvar_livre({"titulo": "Lembrar a Dra. da reunião", "repetir": "dia"})["salvo"]
    api.lembretes_salvar_livre({"titulo": "Sem repetir"})
    primeira = api.lembretes_do_dia()
    assert primeira["mostrar"] and [x["titulo"] for x in primeira["livres"]] == ["Lembrar a Dra. da reunião"]
    assert primeira["livres"][0]["quando"] == "todo dia"
    # Abriu de novo no mesmo dia: as contas não, mas o lembrete sim.
    segunda = api.lembretes_do_dia()
    assert segunda["mostrar"] and segunda["contas"] == [] and len(segunda["livres"]) == 1
    api.lembretes_marcar_feito(item["id"], True)
    assert api.lembretes_do_dia()["mostrar"] is False


def test_tela_tem_programados_e_quem_recebe(api):
    api.lembretes_definir_destinatario("Dra. Exemplo")
    amanha = (date.today() + timedelta(days=1)).isoformat()
    r = api.lembretes_salvar_livre({"titulo": "Comprar flores", "repetir": "data", "data": amanha,
                                    "destinatario": "Recepção"})
    assert r["em_aberto"] == [] and [x["titulo"] for x in r["programados"]] == ["Comprar flores"]
    p = r["programados"][0]
    assert p["proxima"] == amanha and p["destinatario_nome"] == "Recepção" and p["quando"].startswith("em ")
    assert r["padrao"] == "Dra. Exemplo" and "Recepção" in r["nomes"]
    # Escrever o nome de quem já recebe os lembretes é o mesmo que deixar em branco.
    r = api.lembretes_salvar_livre({"titulo": "Comprar flores", "repetir": "dia", "destinatario": "dra. exemplo"},
                                   p["id"])
    assert r["em_aberto"][0]["destinatario"] == ""


def test_titulo_vazio_nao_cria_contato(api):
    r = api.lembretes_salvar_livre({"titulo": " ", "destinatario": "Pessoa Nova"})
    assert "erro" in r
    assert api.contatos_listar()["contatos"] == []


def test_enviar_lembrete_pelo_whatsapp(api):
    api.lembretes_definir_destinatario("Dra. Exemplo")
    dra = api.lembretes_destinatario()["contato"]
    api.contatos_salvar({"nome": dra["nome"], "telefone": "(61) 90000-0000"}, dra["id"])
    item = api.lembretes_salvar_livre({"titulo": "Assinar os contratos", "observacao": "Estão na gaveta",
                                       "repetir": "semana", "dia_semana": 0})["salvo"]
    r = api.lembretes_preparar_livre(item["id"])
    assert r["destinatario"] == "Dra. Exemplo" and r["telefone"] == TEL and r["contato_id"] == dra["id"]
    assert r["mensagem"] == "*Assistente João:* Olá, Dra. Exemplo.\nLembrete: Assinar os contratos\nEstão na gaveta"
    with mock.patch.object(msg, "abrir_conversa") as abrir:
        assert api.lembretes_enviar(r["mensagem"], r["contato_id"]) == {}
    assert abrir.call_args.args[0] == TEL


def test_enviar_para_outra_pessoa_e_sem_telefone(api):
    item = api.lembretes_salvar_livre({"titulo": "Avisar", "destinatario": "Recepção"})["salvo"]
    r = api.lembretes_preparar_livre(item["id"])
    assert r["destinatario"] == "Recepção" and r["telefone"] == ""
    assert api.lembretes_enviar("oi", r["contato_id"]) == {"sem_contato": True, "nome": "Recepção"}
    # Contato apagado: volta para quem recebe os lembretes de contas (aqui, ninguém).
    api.contatos_apagar(r["contato_id"])
    r = api.lembretes_preparar_livre(item["id"])
    assert r["destinatario"] == "" and r["mensagem"].endswith("Olá.\nLembrete: Avisar")


def test_widget_mostra_a_repeticao(api):
    api.lembretes_salvar_livre({"titulo": "Um", "repetir": "dia"})
    w = api.inicio_painel()["widgets"]["lembretes"]
    assert w["livres"][0]["quando"] == "todo dia"


def test_lembretes_antigos_ganham_os_campos_novos(api):
    with api._armazem.editar("lembretes.json") as d:
        d["livres"] = [{"id": "v", "titulo": "Da 1.8", "observacao": "", "criado_em": "2026-11-17", "feito_em": ""}]
    api._armazem.esquecer()  # como ao abrir a 1.9.0: lê o arquivo gravado pela 1.8.0
    r = api.lembretes_livres()
    assert r["em_aberto"][0]["repetir"] == "nao" and r["em_aberto"][0]["quando"] == ""
