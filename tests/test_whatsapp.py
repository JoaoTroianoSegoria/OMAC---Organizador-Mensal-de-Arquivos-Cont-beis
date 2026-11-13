import sys
from datetime import date
from urllib.parse import unquote

import pytest

from omac import config, sistema
from omac.app import Api
from omac.notas.leitor import Nota
from omac.whatsapp import lembretes as lb
from omac.whatsapp import mensagens as msg
from omac.whatsapp.api import responsavel
from omac.whatsapp.dados import DadosIlegiveis, carregar
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
    with api._dados() as d:
        d["inicio"] = dia


def test_nota_antiga_fica_fora_de_a_enviar(api):
    _comecar_em(api, "2999-01-01")
    assert api.whatsapp_a_enviar()["notas"] == []


def test_a_enviar_tira_a_enviada_e_desfaz(api):
    _comecar_em(api)
    numeros = [n["numero"] for n in api.whatsapp_a_enviar()["notas"]]
    assert numeros == list(range(801, 813))
    api.whatsapp_marcar_enviada(801)
    assert 801 not in [n["numero"] for n in api.whatsapp_a_enviar()["notas"]]
    assert api.whatsapp_enviadas()["numeros"] == [801]
    api.whatsapp_marcar_enviada(801, False)
    assert api.whatsapp_enviadas()["numeros"] == []


def test_enviar_nota_guarda_o_contato_pelo_responsavel(api):
    preparada = api.whatsapp_preparar_nota(803)  # nota de dependente
    assert preparada["nome"] == "FERNANDA COSTA"
    assert preparada["telefone"] == ""
    assert "Olá, Fernanda." in preparada["mensagem"]
    assert "*Assistente João:*" in preparada["mensagem"]

    r = api.whatsapp_enviar_nota(803, "(61) 90000-0000", preparada["mensagem"])
    assert r == {"pdf_copiado": True}
    assert api.abertos[0].startswith(f"whatsapp://send?phone={TEL}")
    assert api.whatsapp_preparar_nota(803)["telefone"] == TEL
    # Abrir a conversa não marca como enviada: quem envia é a pessoa.
    assert api.whatsapp_enviadas()["numeros"] == []


def test_telefone_invalido_nao_abre_nem_guarda(api):
    r = api.whatsapp_enviar_nota(801, "123", "oi")
    assert "telefone" in r["erro"]
    assert api.abertos == []
    assert api.whatsapp_contatos()["contatos"] == []


def test_web_abre_o_site(api):
    api._cfg["whatsapp_destino"] = "web"
    api.whatsapp_enviar_nota(801, "61900000000", "oi")
    assert api.abertos[0].startswith("https://web.whatsapp.com/")


def test_aplicativo_ausente_cai_no_site(api, monkeypatch):
    abertos = []

    def abrir(url):
        if url.startswith("whatsapp:"):
            raise OSError("sem aplicativo")
        abertos.append(url)

    monkeypatch.setattr(sistema, "abrir_link", abrir)
    assert "erro" not in api.whatsapp_enviar_nota(801, "61900000000", "oi")
    assert abertos[0].startswith("https://wa.me/")


def test_sem_copiar_o_pdf_mostra_na_pasta(api, monkeypatch):
    mostrados = []
    monkeypatch.setattr(sistema, "copiar_arquivo", lambda c: False)
    monkeypatch.setattr(sistema, "mostrar_na_pasta", mostrados.append)
    assert api.whatsapp_enviar_nota(801, "61900000000", "oi") == {"pdf_copiado": False}
    assert mostrados[0].name.startswith("NFS-e Nº 000000801")


def test_lembrete_so_na_primeira_abertura_do_dia(api):
    hoje = date.today()
    api.whatsapp_salvar_conta({"nome": "Aluguel", "dia": min(hoje.day, 28)})
    api._cfg["lembrete_fechamento_dia"] = 0
    with api._dados() as d:
        d["contas"] = [{"nome": "Aluguel", "dia": hoje.day}]

    primeira = api.whatsapp_lembretes()
    assert primeira["mostrar"] is True
    assert primeira["contas"][0]["nome"] == "Aluguel"
    assert api.whatsapp_lembretes() == {"mostrar": False}
    # O botão "ver os lembretes" mostra de novo.
    assert api.whatsapp_lembretes(True)["mostrar"] is True


def test_lembrete_sem_telefone_pede_contato(api):
    assert api.whatsapp_enviar_lembrete("oi") == {"sem_contato": True}
    api._cfg["lembrete_telefone"] = "(61) 90000-0000"
    assert api.whatsapp_enviar_lembrete("oi") == {}
    assert TEL in api.abertos[0]


def test_arquivo_ruim_nao_e_apagado(api):
    arquivo = config.caminho_whatsapp()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("{ quebrado", encoding="utf-8")
    assert "erro" in api.whatsapp_contatos()
    assert arquivo.read_text(encoding="utf-8") == "{ quebrado"
    with pytest.raises(DadosIlegiveis):
        carregar(arquivo)


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
