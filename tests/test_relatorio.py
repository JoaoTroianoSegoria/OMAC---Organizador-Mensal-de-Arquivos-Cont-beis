"""Relatório mensal (1.8.0): pesquisa de notas e envio de várias notas de uma vez."""

from datetime import date
from decimal import Decimal

import pytest

from omac import config, sistema
from omac.app import Api
from omac.notas import pesquisa
from omac.notas.leitor import Nota
from omac.whatsapp import mensagens as msg
from tests.fabrica import criar_pasta_exemplo, nome_arquivo

TEL = "5561900000000"


def _nota(numero, paciente, valor, comp, emissao=None, arquivo=None):
    return Nota(numero, paciente, Decimal(valor), emissao or comp, comp,
                arquivo or nome_arquivo(numero, paciente, emissao or comp))


NOTAS = [
    _nota(10, "MARIA DA SILVA", "150.00", date(2026, 3, 5)),
    _nota(11, "JOSÉ SOUZA", "1500.00", date(2026, 3, 20), emissao=date(2026, 4, 2)),
    _nota(12, "MARIA DA SILVA", "250.50", date(2026, 4, 9)),
    _nota(13, "LUCAS RIBEIRO", "90.00", date(2026, 5, 1), arquivo=nome_arquivo(13, "ANA RIBEIRO", date(2026, 5, 1))),
]


def _numeros(notas):
    return [n.numero for n in notas]


# --- Pesquisa ------------------------------------------------------------------------


def test_sem_texto_devolve_todas_em_ordem():
    assert _numeros(pesquisa.filtrar(list(reversed(NOTAS)))) == [10, 11, 12, 13]


@pytest.mark.parametrize("texto, esperado", [
    ("maria", [10, 12]),
    ("Maria Silva", [10, 12]),
    ("josé", [11]),
    ("JOSE", [11]),
    ("ribeiro", [13]),       # dependente
    ("ana ribeiro", [13]),   # responsável (nome do arquivo)
    ("11", [11]),            # número
    ("150", [10]),           # valor redondo
    ("150,00", [10]),
    ("R$ 1.500,00", [11]),
    ("1500", [11]),
    ("250,5", [12]),
    ("250,50", [12]),
    ("05/03", [10]),         # dia/mês da competência
    ("02/04", [11]),         # ou da emissão
    ("09/04/2026", [12]),
    ("09/04/26", [12]),
    ("03/2026", [10, 11]),
    ("maria 150", [10]),     # todas as palavras precisam aparecer
    ("maria 90", []),
    ("pedro", []),
])
def test_pesquisa_por_nome_numero_valor_ou_data(texto, esperado):
    assert _numeros(pesquisa.filtrar(NOTAS, texto)) == esperado


def test_periodo_pela_competencia_com_as_pontas():
    assert _numeros(pesquisa.filtrar(NOTAS, "", date(2026, 3, 20), date(2026, 4, 9))) == [11, 12]
    assert _numeros(pesquisa.filtrar(NOTAS, "", de=date(2026, 4, 1))) == [12, 13]
    assert _numeros(pesquisa.filtrar(NOTAS, "maria", ate=date(2026, 3, 31))) == [10]


# --- Mensagem de várias notas ---------------------------------------------------------------


def test_mensagem_de_uma_nota_e_a_de_sempre():
    assert msg.mensagem_das_notas("", "ANA", [("ANA", date(2026, 1, 2))]) == msg.mensagem_da_nota(
        "", "ANA", date(2026, 1, 2))


def test_mensagem_de_varias_notas_do_mesmo_paciente():
    texto = msg.mensagem_das_notas("João", "MARIA DA SILVA", [
        ("MARIA DA SILVA", date(2026, 3, 12)), ("MARIA DA SILVA", date(2026, 3, 5)),
        ("MARIA DA SILVA", date(2026, 3, 19))])
    assert texto == ("*Assistente João:* Olá, Maria.\nSeguem as 3 notas fiscais referentes ao "
                     "tratamento odontológico realizado nos dias 05/03, 12/03 e 19/03.")


def test_mensagem_de_notas_de_pacientes_diferentes_lista_cada_um():
    texto = msg.mensagem_das_notas("", "FERNANDA COSTA", [
        ("LUCAS RIBEIRO", date(2026, 3, 5)), ("FERNANDA COSTA", date(2026, 3, 6)),
        ("LUCAS RIBEIRO", date(2026, 3, 9))])
    assert texto == ("Olá, Fernanda.\nSeguem as 3 notas fiscais referentes ao tratamento odontológico:\n"
                     "• Fernanda Costa: 06/03\n• Lucas Ribeiro: 05/03 e 09/03")


# --- API ------------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    abertos, copiados, mostrados = [], [], []
    monkeypatch.setattr(sistema, "abrir_link", abertos.append)
    monkeypatch.setattr(sistema, "copiar_arquivos", lambda cs: copiados.append([c.name for c in cs]) or True)
    monkeypatch.setattr(sistema, "mostrar_na_pasta", mostrados.append)
    monkeypatch.setattr(sistema, "colar_sozinho_disponivel", lambda: True)
    a = Api()
    a.abertos, a.copiados, a.mostrados = abertos, copiados, mostrados
    a._cfg.update(pasta_notas=str(criar_pasta_exemplo(tmp_path / "NFS-e 2026")), assistente_nome="João")
    return a


def test_api_pesquisa_no_mes_no_ano_e_no_periodo(api):
    mes = api.notas_pesquisar("", "mes", 2026, 10)
    assert len(mes["notas"]) == 11 and mes["notas"][0]["responsavel"] == "ANA BEATRIZ MOREIRA"
    assert [n["numero"] for n in api.notas_pesquisar("costa", "ano", 2026, 1)["notas"]] == [803]
    assert api.notas_pesquisar("lucas", "ano", 2026, 1)["notas"][0]["responsavel"] == "FERNANDA COSTA"
    periodo = api.notas_pesquisar("", "periodo", 0, 0, "2026-10-31", "2026-10-28")  # de–até trocados
    assert [n["numero"] for n in periodo["notas"]] == [809, 810, 811]
    assert periodo["total_centavos"] == 22000 + 47500 + 38000
    assert [n["numero"] for n in api.notas_pesquisar("", "periodo", 0, 0, "2026-11-01", "")["notas"]] == [812]


def test_lote_da_mesma_pessoa_sugere_o_contato_e_os_responsaveis(api):
    api.contatos_salvar({"nome": "Fernanda Costa", "telefone": "(61) 90000-0000"})
    fernanda = api.contatos_listar()["contatos"][0]
    api.contatos_salvar({"nome": "Lucas Costa Ribeiro", "telefone": "(61) 98888-0000",
                         "responsaveis": [{"contato_id": fernanda["id"], "papel": "mae"}]})
    r = api.notas_preparar_lote([803])
    assert r["mesma_pessoa"] and r["nome"] == "Fernanda Costa" and r["escolhido"] == fernanda["id"]
    assert [d["nome"] for d in r["destinos"]] == ["Fernanda Costa"]
    assert "Segue a nota fiscal" in r["destinos"][0]["mensagem"]
    # Escolhendo o Lucas na lista: ele e a mãe.
    lucas = next(c for c in r["contatos"] if c["nome"] == "Lucas Costa Ribeiro")
    r = api.notas_preparar_lote([803], lucas["id"])
    assert [(d["nome"], d["papel"]) for d in r["destinos"]] == [
        ("Lucas Costa Ribeiro", ""), ("Fernanda Costa", "mãe")]


def test_lote_de_quem_ainda_nao_e_contato(api):
    r = api.notas_preparar_lote([802, 801, 801])
    assert not r["mesma_pessoa"] and r["destinos"] == [] and r["nome"] == ""
    assert [n["numero"] for n in r["notas"]] == [801, 802] and r["total_centavos"] == 155000
    r = api.notas_preparar_lote([801])
    assert r["mesma_pessoa"] and r["contato_id"] == "" and r["destinos"][0]["nome"] == "ANA BEATRIZ MOREIRA"
    # Pessoas diferentes, com um nome novo digitado: vira contato no envio.
    r = api.notas_preparar_lote([801, 802], "", "  Clínica   Exemplo ")
    assert [d["nome"] for d in r["destinos"]] == ["Clínica Exemplo"] and r["contato_id"] == ""
    assert "Olá, Clínica." in r["destinos"][0]["mensagem"]


def test_lote_sem_nota_ou_com_nota_que_nao_existe(api):
    assert "Escolha" in api.notas_preparar_lote([])["erro"]
    assert "nº 999" in api.notas_preparar_lote([801, 999])["erro"]


def test_enviar_lote_copia_todos_os_pdfs_e_cria_o_contato(api):
    r = api.notas_enviar_lote([802, 801], "", "", "Ana Beatriz Moreira", "(61) 90000-0000", "oi", False)
    assert r == {"pdf_copiado": True, "colando": False, "qtd": 2}
    assert [len(c) for c in api.copiados] == [2] and "000000801" in api.copiados[0][0]
    assert api.abertos[0].startswith(f"whatsapp://send?phone={TEL}")
    [contato] = api.contatos_listar()["contatos"]
    assert (contato["nome"], contato["telefone"]) == ("Ana Beatriz Moreira", TEL)
    assert api.notas_enviadas()["numeros"] == []  # quem confirma é a pessoa


def test_enviar_lote_para_o_responsavel_lembra_a_escolha(api):
    api.contatos_salvar({"nome": "Fernanda Costa", "telefone": ""})
    fernanda = api.contatos_listar()["contatos"][0]
    api.contatos_salvar({"nome": "Lucas Costa Ribeiro", "telefone": "",
                         "responsaveis": [{"contato_id": fernanda["id"], "papel": "mae"}]})
    lucas = next(c for c in api.contatos_listar()["contatos"] if c["nome"] == "Lucas Costa Ribeiro")
    api.notas_enviar_lote([803], lucas["id"], fernanda["id"], "", "61900000000", "oi")
    r = api.notas_preparar_lote([803], lucas["id"])
    assert r["escolhido"] == fernanda["id"]
    assert next(d for d in r["destinos"] if d["contato_id"] == fernanda["id"])["telefone"] == TEL
    # Quem não é responsável não pode receber em nome do contato.
    outro = api.contatos_salvar({"nome": "Outra Pessoa"})
    outro_id = next(c["id"] for c in outro["contatos"] if c["nome"] == "Outra Pessoa")
    assert "Escolha" in api.notas_enviar_lote([803], lucas["id"], outro_id, "", TEL, "oi")["erro"]


def test_enviar_lote_recusa_telefone_ou_pdf_que_sumiu(api, tmp_path):
    assert "telefone" in api.notas_enviar_lote([801], "", "", "Ana", "123", "oi")["erro"]
    api._servico_notas.atual()
    next((tmp_path / "NFS-e 2026").glob("*000000802*")).unlink()
    assert "nº 802" in api.notas_enviar_lote([801, 802], "", "", "Ana", TEL, "oi")["erro"]
    assert api.abertos == [] and api.copiados == []


def test_sem_copiar_mostra_o_pdf_na_pasta(api, monkeypatch):
    monkeypatch.setattr(sistema, "copiar_arquivos", lambda cs: False)
    r = api.notas_enviar_lote([801], "", "", "Ana", TEL, "oi", True)
    assert r["pdf_copiado"] is False and r["colando"] is False and len(api.mostrados) == 1


def test_colar_sozinho_e_lembrado_e_so_no_aplicativo(api, monkeypatch):
    colagens = []
    monkeypatch.setattr(sistema, "colar_quando_abrir", lambda: colagens.append(1) or True)
    assert api.notas_preparar_lote([801])["colar_disponivel"] is True
    r = api.notas_enviar_lote([801], "", "", "Ana", TEL, "oi", True)
    assert r["colando"] is True
    assert config.carregar()["colar_sozinho"] is True
    assert api.notas_preparar_lote([801])["colar_sozinho"] is True
    api._cfg["whatsapp_destino"] = "web"
    assert api.notas_preparar_lote([801])["colar_disponivel"] is False
    assert api.notas_enviar_lote([801], "", "", "Ana", TEL, "oi", True)["colando"] is False


def test_marcar_varias_como_enviadas_e_desfazer(api):
    api.notas_marcar_enviadas([801, 802, "803"])
    assert api.notas_enviadas()["numeros"] == [801, 802, 803]
    api.notas_marcar_enviadas([801, 803], False)
    assert api.notas_enviadas()["numeros"] == [802]
