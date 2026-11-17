import sys
from datetime import date
from urllib.parse import unquote

import pytest

from omac import config, sistema
from omac.app import Api
from omac.notas.leitor import Nota
from omac.lembretes import contas as lb
from omac.whatsapp import mensagens as msg
from omac.notas.envio import responsavel
from omac.dados import esquema
from tests.fabrica import criar_pasta_exemplo

TEL = "5561900000000"


# --- Telefone e links -------------------------------------------------------------


@pytest.mark.parametrize("digitado", ["(61) 90000-0000", "61900000000", "+55 61 90000-0000", "061 90000-0000"])
def test_normaliza_telefone(digitado):
    assert msg.normalizar_telefone(digitado) == TEL


def test_telefone_fixo_com_dez_digitos():
    assert msg.normalizar_telefone("(61) 3000-0000") == "556130000000"


@pytest.mark.parametrize("ruim", ["", "123", "900000000", "1 212 555 0000 00000"])
def test_recusa_telefone_invalido(ruim):
    with pytest.raises(msg.TelefoneInvalido):
        msg.normalizar_telefone(ruim)


def test_link_do_aplicativo_tem_o_site_como_segunda_opcao():
    primeiro, segundo = msg.links(TEL, "Olá,\nFulano & cia", "app")
    assert primeiro.startswith(f"whatsapp://send?phone={TEL}&text=")
    assert segundo.startswith(f"https://wa.me/{TEL}?text=")
    assert unquote(primeiro.split("text=")[1]) == "Olá,\nFulano & cia"
    assert "&" not in primeiro.split("text=")[1]


def test_link_do_web():
    assert msg.links(TEL, "oi", "web") == [f"https://web.whatsapp.com/send?phone={TEL}&text=oi"]


# --- Mensagens ---------------------------------------------------------------------


def test_mensagem_da_nota():
    assert msg.mensagem_da_nota("João", "FERNANDA COSTA", date(2026, 10, 30)) == (
        "*Assistente João:* Olá, Fernanda.\n"
        "Segue a nota fiscal referente ao tratamento odontológico realizado dia 30/10."
    )


def test_sem_nome_de_assistente_nao_assina():
    assert msg.mensagem_da_nota("", "ANA", date(2026, 1, 2)).startswith("Olá, Ana.")


def test_mensagem_de_lembrete():
    contas = [{"nome": "Aluguel", "situacao": "vence amanhã (05/11)"},
              {"nome": "Internet", "situacao": "vence hoje (04/11)"}]
    assert msg.mensagem_de_lembrete("João", "Dra. Exemplo", contas) == (
        "*Assistente João:* Olá, Dra. Exemplo.\n"
        "Lembrete de pagamento:\n"
        "• Aluguel: vence amanhã (05/11)\n"
        "• Internet: vence hoje (04/11)"
    )


def test_nota_de_dependente_vai_para_o_responsavel():
    nota = Nota(1, "LUCAS COSTA RIBEIRO", 0, date(2026, 1, 1), date(2026, 1, 1),
                "NFS-e Nº 000000001 - FERNANDA COSTA - 01-01 -.pdf", dependente=True)
    assert responsavel(nota) == "FERNANDA COSTA"


def test_nome_de_arquivo_fora_do_padrao_usa_o_paciente():
    nota = Nota(1, "TOMADOR", 0, date(2026, 1, 1), date(2026, 1, 1), "qualquer.pdf")
    assert responsavel(nota) == "TOMADOR"


# --- Lembretes ---------------------------------------------------------------------

ALUGUEL = {"nome": "Aluguel", "dia": 10}


def _situacoes(contas, hoje, ultima=None):
    return [c["situacao"] for c in lb.contas_a_avisar(contas, hoje, ultima)]


def test_avisa_um_dia_antes_e_no_dia():
    assert _situacoes([ALUGUEL], date(2026, 11, 9), date(2026, 11, 8)) == ["vence amanhã (10/11)"]
    assert _situacoes([ALUGUEL], date(2026, 11, 10), date(2026, 11, 9)) == ["vence hoje (10/11)"]


def test_nao_avisa_nos_outros_dias():
    assert _situacoes([ALUGUEL], date(2026, 11, 8), date(2026, 11, 7)) == []
    assert _situacoes([ALUGUEL], date(2026, 11, 11), date(2026, 11, 10)) == []


def test_app_fechado_nos_dois_dias_avisa_que_venceu():
    assert _situacoes([ALUGUEL], date(2026, 11, 12), date(2026, 11, 8)) == ["venceu dia 10/11"]


def test_app_fechado_so_no_dia_tambem_avisa():
    assert _situacoes([ALUGUEL], date(2026, 11, 11), date(2026, 11, 9)) == ["venceu dia 10/11"]


def test_primeira_vez_nao_cobra_contas_passadas():
    assert _situacoes([ALUGUEL], date(2026, 11, 20)) == []
    assert _situacoes([ALUGUEL], date(2026, 11, 10)) == ["vence hoje (10/11)"]


def test_virada_de_mes_e_de_ano():
    conta = {"nome": "X", "dia": 1}
    assert _situacoes([conta], date(2026, 12, 31), date(2026, 12, 30)) == ["vence amanhã (01/01)"]


def test_dia_31_vence_no_ultimo_dia_do_mes_curto():
    conta = {"nome": "X", "dia": 31}
    assert _situacoes([conta], date(2026, 2, 28), date(2026, 2, 27)) == ["vence hoje (28/02)"]


def test_muito_tempo_fechado_nao_lista_o_ano_inteiro():
    assert len(lb.contas_a_avisar([ALUGUEL], date(2026, 11, 20), date(2025, 1, 1))) == 1


def test_lembretes_em_ordem_de_vencimento():
    contas = [{"nome": "B", "dia": 11}, {"nome": "A", "dia": 10}]
    assert [c["nome"] for c in lb.contas_a_avisar(contas, date(2026, 11, 10), date(2026, 11, 9))] == ["A", "B"]


def test_aviso_de_fechamento():
    assert lb.aviso_de_fechamento(5, date(2026, 11, 5), date(2026, 11, 4)) == (
        "Hora de gerar o fechamento de Outubro de 2026.")
    assert lb.aviso_de_fechamento(5, date(2026, 11, 6), date(2026, 11, 5)) == ""
    assert "Outubro" in lb.aviso_de_fechamento(5, date(2026, 11, 7), date(2026, 11, 2))
    assert lb.aviso_de_fechamento(0, date(2026, 11, 5), date(2026, 11, 4)) == ""
    assert "Dezembro de 2025" in lb.aviso_de_fechamento(1, date(2026, 1, 1), date(2025, 12, 31))


@pytest.mark.parametrize("ruim", [{"nome": "", "dia": 5}, {"nome": "X", "dia": 0}, {"nome": "X", "dia": 32},
                                  {"nome": "X", "dia": "abc"}, {"nome": "X"}])
def test_conta_invalida(ruim):
    with pytest.raises(lb.ContaInvalida):
        lb.adicionar_conta([], ruim)


def test_editar_e_remover_conta():
    contas = lb.adicionar_conta([], {"nome": "Água", "dia": 5})
    contas = lb.adicionar_conta(contas, {"nome": "agua", "dia": 6})
    assert [(c["nome"], c["dia"]) for c in contas] == [("agua", 6)]
    contas = lb.adicionar_conta(contas, {"nome": "Luz", "dia": 7}, antiga={"nome": "AGUA"})
    assert [(c["nome"], c["dia"]) for c in contas] == [("Luz", 7)]
    assert lb.remover_conta(contas, "luz") == []


# --- API, sem abrir nada de verdade -------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    abertos = []
    monkeypatch.setattr(sistema, "abrir_link", abertos.append)
    monkeypatch.setattr(sistema, "copiar_arquivo", lambda c: True)
    monkeypatch.setattr(sistema, "mostrar_na_pasta", lambda c: None)
    a = Api()
    a.abertos = abertos
    a._cfg.update(pasta_notas=str(criar_pasta_exemplo(tmp_path / "NFS-e 2026")), assistente_nome="João")
    return a


def _comecar_em(api, dia="2026-01-01"):
    with api._enviadas() as d:
        d["inicio"] = dia


def test_nota_antiga_fica_fora_de_a_enviar(api):
    _comecar_em(api, "2999-01-01")
    assert api.notas_a_enviar()["notas"] == []


def test_a_enviar_tira_a_enviada_e_desfaz(api):
    _comecar_em(api)
    numeros = [n["numero"] for n in api.notas_a_enviar()["notas"]]
    assert numeros == list(range(801, 813))
    api.notas_marcar_enviada(801)
    assert 801 not in [n["numero"] for n in api.notas_a_enviar()["notas"]]
    assert api.notas_enviadas()["numeros"] == [801]
    api.notas_marcar_enviada(801, False)
    assert api.notas_enviadas()["numeros"] == []


def test_enviar_nota_guarda_o_contato_pelo_responsavel(api):
    preparada = api.notas_preparar_envio(803)  # nota de dependente
    assert preparada["nome"] == "FERNANDA COSTA"
    assert preparada["telefone"] == ""
    assert "Olá, Fernanda." in preparada["mensagem"]
    assert "*Assistente João:*" in preparada["mensagem"]

    r = api.notas_enviar(803, "(61) 90000-0000", preparada["mensagem"])
    assert r == {"pdf_copiado": True}
    assert api.abertos[0].startswith(f"whatsapp://send?phone={TEL}")
    assert api.notas_preparar_envio(803)["telefone"] == TEL
    # Quem recebe a nota vira contato.
    [contato] = api.contatos_listar()["contatos"]
    assert (contato["nome"], contato["telefone"]) == ("FERNANDA COSTA", TEL)
    # Abrir a conversa não marca como enviada: quem envia é a pessoa.
    assert api.notas_enviadas()["numeros"] == []


def test_contato_ja_cadastrado_da_o_telefone_da_nota(api):
    api.contatos_salvar({"nome": "Fernanda Costa", "telefone": "(61) 90000-0000"})
    assert api.notas_preparar_envio(803)["telefone"] == TEL


def test_telefone_invalido_nao_abre_nem_guarda(api):
    r = api.notas_enviar(801, "123", "oi")
    assert "telefone" in r["erro"]
    assert api.abertos == []
    assert api.contatos_listar()["contatos"] == []


def test_web_abre_o_site(api):
    api._cfg["whatsapp_destino"] = "web"
    api.notas_enviar(801, "61900000000", "oi")
    assert api.abertos[0].startswith("https://web.whatsapp.com/")


def test_aplicativo_ausente_cai_no_site(api, monkeypatch):
    abertos = []

    def abrir(url):
        if url.startswith("whatsapp:"):
            raise OSError("sem aplicativo")
        abertos.append(url)

    monkeypatch.setattr(sistema, "abrir_link", abrir)
    assert "erro" not in api.notas_enviar(801, "61900000000", "oi")
    assert abertos[0].startswith("https://wa.me/")


def test_sem_copiar_o_pdf_mostra_na_pasta(api, monkeypatch):
    mostrados = []
    monkeypatch.setattr(sistema, "copiar_arquivo", lambda c: False)
    monkeypatch.setattr(sistema, "mostrar_na_pasta", mostrados.append)
    assert api.notas_enviar(801, "61900000000", "oi") == {"pdf_copiado": False}
    assert mostrados[0].name.startswith("NFS-e Nº 000000801")


def test_lembrete_so_na_primeira_abertura_do_dia(api):
    hoje = date.today()
    api.lembretes_salvar_conta({"nome": "Aluguel", "dia": min(hoje.day, 28)})
    api._cfg["lembrete_fechamento_dia"] = 0
    with api._contas() as d:
        d["contas"] = [{"nome": "Aluguel", "dia": hoje.day}]

    primeira = api.lembretes_do_dia()
    assert primeira["mostrar"] is True
    assert primeira["contas"][0]["nome"] == "Aluguel"
    assert api.lembretes_do_dia() == {"mostrar": False}
    # O botão "ver os lembretes" mostra de novo.
    assert api.lembretes_do_dia(True)["mostrar"] is True


def test_lembrete_sem_telefone_pede_contato(api):
    assert api.lembretes_enviar("oi") == {"sem_contato": True, "nome": ""}
    api.lembretes_definir_destinatario("Dra. Exemplo")
    assert api.lembretes_enviar("oi") == {"sem_contato": True, "nome": "Dra. Exemplo"}
    contato = api.lembretes_destinatario()["contato"]
    api.contatos_salvar({"nome": contato["nome"], "telefone": "(61) 90000-0000"}, contato["id"])
    assert api.lembretes_enviar("oi") == {}
    assert TEL in api.abertos[0]


def test_escolher_quem_recebe_os_lembretes(api):
    api.contatos_salvar({"nome": "Dra. Exemplo", "telefone": "(61) 90000-0000"})
    r = api.lembretes_definir_destinatario("dra.  EXEMPLO")
    assert r["contato"]["nome"] == "Dra. Exemplo" and r["nomes"] == ["Dra. Exemplo"]
    assert len(api.contatos_listar()["contatos"]) == 1  # usou o contato que já existia
    assert api.lembretes_definir_destinatario("")["contato"] is None


def test_arquivo_ruim_nao_e_apagado(api):
    arquivo = config.pasta_dados() / esquema.LEMBRETES
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("{ quebrado", encoding="utf-8")
    assert "erro" in api.lembretes_contas()
    assert "erro" in api.lembretes_salvar_conta({"nome": "Luz", "dia": 3})
    assert arquivo.read_text(encoding="utf-8") == "{ quebrado"


def test_configuracoes_novas_sao_validadas(tmp_path, monkeypatch):
    limpo = config.normalizar({"whatsapp_destino": "outro", "lembrete_fechamento_dia": 99})
    assert limpo["whatsapp_destino"] == "app"
    assert limpo["lembrete_fechamento_dia"] == 28
    assert config.normalizar({"lembrete_fechamento_dia": "x"})["lembrete_fechamento_dia"] == 1


# --- Windows ------------------------------------------------------------------------


def test_fora_do_exe_nao_oferece_abrir_com_o_windows(api):
    assert api.inicio_automatico()["disponivel"] is False
    assert "erro" in api.definir_inicio_automatico(True)


@pytest.mark.skipif(sys.platform != "win32", reason="registro do Windows")
def test_registro_de_abrir_com_o_windows():
    nome = "OMAC-teste"
    try:
        sistema.definir_inicio_automatico(True, nome, comando='"C:\\x\\OMAC.exe"')
        assert sistema.inicio_automatico_ligado(nome) == '"C:\\x\\OMAC.exe"'
    finally:
        sistema.definir_inicio_automatico(False, nome)
    assert sistema.inicio_automatico_ligado(nome) == ""
    sistema.definir_inicio_automatico(False, nome)  # desligar duas vezes não dá erro


@pytest.mark.skipif(sys.platform != "win32", reason="área de transferência do Windows")
def test_copiar_arquivo_com_aspas_no_nome_nao_quebra(tmp_path):
    arquivo = tmp_path / "nota d'água.pdf"
    arquivo.write_bytes(b"x")
    assert isinstance(sistema.copiar_arquivo(arquivo), bool)


# --- 1.7.0: enviar lembrete de conta a qualquer momento --------------------------------------

def test_texto_da_situacao_para_qualquer_dia():
    hoje = date(2026, 11, 17)
    assert lb._situacao(date(2026, 11, 17), hoje) == "vence hoje (17/11)"
    assert lb._situacao(date(2026, 11, 18), hoje) == "vence amanhã (18/11)"
    assert lb._situacao(date(2026, 11, 25), hoje) == "vence dia 25/11"
    assert lb._situacao(date(2026, 11, 10), hoje) == "venceu dia 10/11"


def test_contas_em_aberto_deste_mes_e_nao_pagas_do_mes_passado():
    hoje = date(2026, 11, 17)
    contas = [
        {"nome": "Aluguel", "dia": 10, "criada_em": "2026-09-01", "pagas": {"2026-10": "x"}},  # outubro paga
        {"nome": "Luz", "dia": 25, "criada_em": "2026-09-01", "pagas": {}},  # outubro não paga, novembro em aberto
        {"nome": "Água", "dia": 5, "criada_em": "2026-09-01", "pagas": {"2026-10": "x", "2026-11": "x"}},  # tudo pago
        {"nome": "Nova", "dia": 3, "criada_em": "2026-11-15", "pagas": {}},  # começou agora: outubro não conta
    ]
    itens = lb.contas_em_aberto(contas, hoje)
    assert [(i["nome"], i["mes"], i["situacao"]) for i in itens] == [
        ("Luz", "2026-10", "venceu dia 25/10"),
        ("Nova", "2026-11", "venceu dia 03/11"),
        ("Aluguel", "2026-11", "venceu dia 10/11"),
        ("Luz", "2026-11", "vence dia 25/11"),
    ]
    assert [i["mes"] for i in lb.contas_em_aberto(contas, hoje, "luz")] == ["2026-10", "2026-11"]
    assert lb.contas_em_aberto(contas, hoje, "Água") == []


def _conta_vencida(api):
    hoje = date.today()
    with api._contas() as d:
        d["contas"] = [{"nome": "Internet", "dia": 1, "criada_em": "2020-01-01", "pagas": {}}]
    return hoje


def test_api_preparar_lembrete_de_uma_conta_ou_de_todas(api):
    _conta_vencida(api)
    api.lembretes_salvar_conta({"nome": "Luz", "dia": 28})
    api.lembretes_definir_destinatario("Dra. Exemplo")
    r = api.lembretes_preparar_contas("Internet")
    assert [c["nome"] for c in r["contas"]] == ["Internet", "Internet"]  # mês passado e este
    assert "venceu dia 01/" in r["mensagem"] and "Olá, Dra. Exemplo." in r["mensagem"]
    assert r["destinatario"] == "Dra. Exemplo" and r["telefone"] == ""
    todas = api.lembretes_preparar_contas()
    assert {c["nome"] for c in todas["contas"]} == {"Internet", "Luz"}
    assert "erro" in api.lembretes_preparar_contas("Não existe")
    # Marcar como paga tira da lista.
    mes = date.today().isoformat()[:7]
    api.lembretes_marcar_paga("Luz", mes, True)
    assert "Luz" not in {c["nome"] for c in api.lembretes_preparar_contas()["contas"]}


def test_api_lista_de_contas_diz_quais_tem_o_que_lembrar(api):
    _conta_vencida(api)
    with api._contas() as d:
        d["contas"].append({"nome": "Paga", "dia": 1, "criada_em": date.today().isoformat(),
                            "pagas": {date.today().isoformat()[:7]: "x"}})
    r = api.lembretes_contas()
    assert {c["nome"]: c["em_aberto"] for c in r["contas"]} == {"Internet": True, "Paga": False}


def test_preparar_nao_mexe_no_aviso_automatico(api):
    _conta_vencida(api)
    with api._contas() as d:
        d["ultima_abertura"] = "2020-01-01"
    api.lembretes_preparar_contas()
    with api._contas() as d:
        assert d["ultima_abertura"] == "2020-01-01"


# --- 1.7.0: lembretes livres ---------------------------------------------------------------------

from omac.lembretes import comandos as cm  # noqa: E402
from omac.lembretes import livres as lv  # noqa: E402


def test_livre_precisa_de_titulo_e_guarda_a_observacao():
    livres = []
    with pytest.raises(lv.LembreteInvalido):
        lv.salvar(livres, {"titulo": "  "}, None, date(2026, 11, 17))
    item = lv.salvar(livres, {"titulo": " Comprar  luvas ", "observacao": " tamanho M\nazul \n"}, None, date(2026, 11, 17))
    assert (item["titulo"], item["observacao"], item["criado_em"], item["feito_em"]) == \
        ("Comprar luvas", "tamanho M\nazul", "2026-11-17", "")


def test_api_livres_feito_desfazer_apagar(api):
    a = api.lembretes_salvar_livre({"titulo": "Ligar para o laboratório"})["salvo"]
    b = api.lembretes_salvar_livre({"titulo": "Comprar luvas", "observacao": "tamanho M"})["salvo"]
    r = api.lembretes_marcar_feito(a["id"], True)
    assert [x["titulo"] for x in r["em_aberto"]] == ["Comprar luvas"]
    assert [x["titulo"] for x in r["feitos"]] == ["Ligar para o laboratório"] and r["feitos"][0]["feito_em"]
    r = api.lembretes_marcar_feito(a["id"], False)
    assert [x["titulo"] for x in r["em_aberto"]] == ["Ligar para o laboratório", "Comprar luvas"]
    r = api.lembretes_salvar_livre({"titulo": "Comprar luvas e máscaras", "observacao": ""}, b["id"])
    assert r["em_aberto"][1]["titulo"] == "Comprar luvas e máscaras" and r["em_aberto"][1]["id"] == b["id"]
    r = api.lembretes_apagar_livre(a["id"])
    assert [x["titulo"] for x in r["em_aberto"]] == ["Comprar luvas e máscaras"] and r["posicao"] == 0
    api.lembretes_restaurar_livre(r["apagado"], r["posicao"])
    r = api.lembretes_restaurar_livre(r["apagado"], r["posicao"])  # duas vezes não duplica
    assert [x["titulo"] for x in r["em_aberto"]] == ["Ligar para o laboratório", "Comprar luvas e máscaras"]
    assert "erro" in api.lembretes_marcar_feito("sumiu", True)


def test_widget_mostra_os_livres_em_aberto(api):
    a = api.lembretes_salvar_livre({"titulo": "Um"})["salvo"]
    api.lembretes_salvar_livre({"titulo": "Dois"})
    api.lembretes_marcar_feito(a["id"], True)
    w = api.inicio_painel()["widgets"]["lembretes"]
    assert [x["titulo"] for x in w["livres"]] == ["Dois"]


# --- 1.7.0: comandos -------------------------------------------------------------------------------


def test_texto_do_comando_fica_exato_tirando_so_as_pontas():
    assert cm.texto_limpo("  \n Olá, tudo bem?\r\n\n  Linha 3  \n\n") == "Olá, tudo bem?\n\n  Linha 3"
    assert cm.texto_limpo("Pix: 12.345.678/0001-90") == "Pix: 12.345.678/0001-90"


def test_api_categorias_e_comandos(api):
    geral = api.comandos_salvar_categoria("  Geral ")["salva"]
    assert geral["nome"] == "Geral" and geral["comandos"] == []
    assert "Já existe" in api.comandos_salvar_categoria("geral")["erro"]
    pos = api.comandos_salvar_categoria("Pós-atendimento")["salva"]
    r = api.comandos_salvar_categoria("Depois do atendimento", pos["id"])
    assert [c["nome"] for c in r["categorias"]] == ["Geral", "Depois do atendimento"]

    c1 = api.comandos_salvar(geral["id"], {"nome": "Endereço", "texto": "Rua Exemplo, 123\nSala 4\n"})["salvo"]
    assert c1["texto"] == "Rua Exemplo, 123\nSala 4"
    assert "texto" in api.comandos_salvar(geral["id"], {"nome": "Vazio", "texto": " \n "})["erro"]
    assert "Já existe" in api.comandos_salvar(geral["id"], {"nome": "endereço", "texto": "x"})["erro"]
    c2 = api.comandos_salvar(geral["id"], {"nome": "Horário", "texto": "8h às 18h"})["salvo"]
    r = api.comandos_mover(geral["id"], c2["id"], -1)
    assert [c["nome"] for c in r["categorias"][0]["comandos"]] == ["Horário", "Endereço"]
    r = api.comandos_salvar(geral["id"], {"nome": "Endereço da clínica", "texto": "Rua Exemplo, 123"}, c1["id"])
    assert r["salvo"]["id"] == c1["id"] and r["categorias"][0]["comandos"][1]["nome"] == "Endereço da clínica"

    r = api.comandos_apagar(geral["id"], c2["id"])
    assert r["posicao"] == 0 and len(r["categorias"][0]["comandos"]) == 1
    r = api.comandos_restaurar(geral["id"], r["apagado"], r["posicao"])
    assert [c["nome"] for c in r["categorias"][0]["comandos"]] == ["Horário", "Endereço da clínica"]

    r = api.comandos_apagar_categoria(geral["id"])
    assert [c["nome"] for c in r["categorias"]] == ["Depois do atendimento"]
    r = api.comandos_restaurar_categoria(r["apagada"], r["posicao"])
    assert [c["nome"] for c in r["categorias"]] == ["Geral", "Depois do atendimento"]
    assert len(r["categorias"][0]["comandos"]) == 2  # volta com os comandos
    r = api.comandos_mover_categoria(geral["id"], 1)
    assert [c["nome"] for c in r["categorias"]] == ["Depois do atendimento", "Geral"]
    # Gravado em comandos.json, que entra no backup.
    assert api._armazem.ler("comandos.json")["categorias"][1]["comandos"][0]["texto"] == "8h às 18h"
