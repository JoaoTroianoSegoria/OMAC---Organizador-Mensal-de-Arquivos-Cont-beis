"""1.10.0: formato do nome dos arquivos, descrição esperada do serviço e mensagem da nota com variáveis."""

import shutil
from datetime import date
from decimal import Decimal

import pytest

from omac import sistema
from omac.app import Api
from omac.notas import leitor as lt
from omac.notas.leitor import Regras
from omac.whatsapp import mensagens as msg
from omac.whatsapp import variaveis as vr
from tests.fabrica import criar_nota, criar_pasta_exemplo

# --- Formato do nome do arquivo ----------------------------------------------------------


@pytest.mark.parametrize("arquivo, esperado", [
    ("NFS-e Nº 000000836 - JOAO OTAVIO TROIANO - 30-10 -.pdf", (836, "JOAO OTAVIO TROIANO")),
    ("NFS-e Nº 000000836 - JOAO OTAVIO TROIANO - 30-10 - COMP - 02-10 -.pdf", (836, "JOAO OTAVIO TROIANO")),
    ("NFS-e Nº 000000811 - TATIANE MENDES - 03-11 - 31-10.pdf", (811, "TATIANE MENDES")),
    ("qualquer coisa.pdf", None),
])
def test_formato_padrao_continua_igual(arquivo, esperado):
    assert lt.ler_nome_arquivo(arquivo) == esperado
    assert lt.compilar_formato(lt.FORMATO_PADRAO) is lt._RE_ARQUIVO


@pytest.mark.parametrize("formato, arquivo, esperado", [
    ("Nota [numero-da-nota] - [nome-do-paciente]", "Nota 812 - Rafael Martins.pdf", (812, "RAFAEL MARTINS")),
    ("Nota [numero-da-nota] - [nome-do-paciente]", "nota 0812 – Rafael Martins -.pdf", (812, "RAFAEL MARTINS")),
    ("[data-de-emissao] [nome-do-paciente] (NF [numero-da-nota])", "30-10-2026 Ana Souza (NF 836).pdf",
     (836, "ANA SOUZA")),
    ("NF[numero-da-nota]_[nome-do-paciente]_[data-competencia]", "NF836_ANA SOUZA_30.10.pdf", (836, "ANA SOUZA")),
    ("NFSe [numero-da-nota] [nome-do-paciente] [data-de-emissao] fim", "NFSe 7 Bia Lima 01.11.pdf", (7, "BIA LIMA")),
    ("Nota [numero-da-nota] - [nome-do-paciente]", "Recibo 812 - Rafael.pdf", None),
])
def test_formatos_de_outras_empresas(formato, arquivo, esperado):
    assert lt.ler_nome_arquivo(arquivo, Regras(formato)) == esperado


@pytest.mark.parametrize("formato, trecho", [
    ("Nota [numero] - [nome-do-paciente]", "Não conheço [numero]"),
    ("Nota [nome-do-paciente]", "[numero-da-nota] uma vez"),
    ("[numero-da-nota] [numero-da-nota] [nome-do-paciente]", "[numero-da-nota] uma vez"),
    ("[numero-da-nota] [nome-do-paciente] [data-de-emissao] [data-de-emissao]", "uma vez só"),
])
def test_formato_invalido(formato, trecho):
    with pytest.raises(lt.FormatoInvalido, match=trecho.replace("[", r"\[").replace("]", r"\]")):
        lt.compilar_formato(formato)


def test_formato_invalido_salvo_por_fora_cai_no_padrao():
    assert lt.ler_nome_arquivo("NFS-e Nº 000000836 - ANA - 30-10 -.pdf", Regras("[x]")) == (836, "ANA")


# --- Descrição esperada do serviço --------------------------------------------------------


def _texto(descricao):
    return ("NÚMERO DA NFS-E\n836\nCOMPETÊNCIA DA NFS-E\n30/10/2026\nDATA E HORA DA EMISSÃO DA NFS-E\n30/10/2026\n"
            "VALOR DA OPERAÇÃO / SERVIÇO\nR$ 100,00\nDescrição do Serviço\n" + descricao + "\nTRIBUTAÇÃO MUNICIPAL\n")


def test_servico_esperado():
    arquivo = "NFS-e Nº 000000836 - ANA SOUZA - 30-10 -.pdf"
    assert lt.interpretar_texto(_texto("TRATAMENTO ODONTOLOGICO"), arquivo).avisos == []
    aviso = lt.interpretar_texto(_texto("CONSULTA"), arquivo).avisos
    assert aviso == ["A descrição do serviço não contém “tratamento odontológico”."]
    outra = Regras(servico="Fisioterapia")
    assert lt.interpretar_texto(_texto("SESSÃO DE FISIOTERAPIA"), arquivo, outra).avisos == []
    assert "Fisioterapia" in lt.interpretar_texto(_texto("CONSULTA"), arquivo, outra).avisos[0]
    assert lt.interpretar_texto(_texto("CONSULTA"), arquivo, Regras(servico="")).avisos == []


# --- Pela API: testar, salvar e ler de novo ------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "abrir_link", lambda u: None)
    a = Api()
    a._cfg.update(pasta_notas=str(criar_pasta_exemplo(tmp_path / "NFS-e 2026")), assistente_nome="João")
    return a


def test_testar_formato_na_pasta(api):
    r = api.notas_testar_formato(lt.FORMATO_PADRAO)
    assert r["total"] == r["entendidos"] == 13 and r["fora"] == []  # 12 + a cancelada
    assert r["exemplos"][0]["numero"] == 812
    r = api.notas_testar_formato("Nota [numero-da-nota] - [nome-do-paciente]")
    assert r["entendidos"] == 0 and len(r["fora"]) == 5
    assert "Não conheço" in api.notas_testar_formato("[numero] [nome-do-paciente]")["erro"]
    api._cfg["pasta_notas"] = ""
    assert api.notas_testar_formato(lt.FORMATO_PADRAO) == {"sem_pasta": True}


def test_trocar_o_formato_le_as_notas_de_novo(api, tmp_path):
    pasta = tmp_path / "NFS-e 2026"
    for p in list(pasta.glob("*.pdf")):
        p.unlink()
    criar_nota(pasta / "Nota 900 - Bia Lima.pdf", 900, date(2026, 10, 5), date(2026, 10, 5), "200.00",
               tomador="BEATRIZ LIMA SOUZA")
    notas = api.notas_do_mes(2026, 10)["notas"]
    assert notas[0]["responsavel"] == "BEATRIZ LIMA SOUZA"  # fora do formato: usa o tomador
    assert any("fora do formato" in a for a in notas[0]["avisos"])

    assert "erro" in api.notas_salvar_regras("[numero] [nome-do-paciente]", "")
    r = api.notas_salvar_regras("Nota [numero-da-nota] - [nome-do-paciente]", "  ")
    assert r["config"]["formato_arquivo"] == "Nota [numero-da-nota] - [nome-do-paciente]"
    assert r["config"]["servico_esperado"] == ""
    notas = api.notas_do_mes(2026, 10)["notas"]
    assert notas[0]["responsavel"] == "BIA LIMA" and notas[0]["paciente"] == "BIA LIMA"
    assert notas[0]["avisos"] == []
    # Formato vazio volta ao padrão.
    assert api.notas_salvar_regras("", "x")["config"]["formato_arquivo"] == lt.FORMATO_PADRAO


def test_cache_de_outras_regras_nao_vale(tmp_path):
    from omac.notas.pasta import Cache, varrer

    pasta = criar_pasta_exemplo(tmp_path / "n")
    cache = tmp_path / "cache.json"
    varrer(pasta, Cache(cache))
    assert Cache(cache).itens
    assert Cache(cache, Regras(servico="outro")).itens == {}
    shutil.rmtree(pasta)


# --- Mensagem com variáveis ----------------------------------------------------------------


def _nota(numero, paciente, dia, valor="180.00"):
    return vr.NotaDaMensagem(numero, paciente, date(2026, 10, dia), date(2026, 10, dia), Decimal(valor))


def test_modelo_padrao_e_o_texto_de_sempre():
    nota = _nota(836, "LUCAS COSTA RIBEIRO", 30)
    texto = vr.preencher(vr.MODELO_NOTA, vr.valores("João", "FERNANDA COSTA", [nota]))
    assert texto == msg.mensagem_da_nota("João", "FERNANDA COSTA", date(2026, 10, 30))


def test_todas_as_variaveis():
    v = vr.valores("João", "MARIA DA SILVA", [_nota(838, "SOFIA SILVA", 16, "250.00"), _nota(836, "LUCAS SILVA", 2),
                                              _nota(837, "LUCAS SILVA", 16)])
    assert v["nome-do-responsavel"] == "Maria da Silva" and v["primeiro-nome-do-responsavel"] == "Maria"
    assert v["nome-do-paciente"] == "Sofia Silva e Lucas Silva"
    assert v["primeiro-nome-do-paciente"] == "Sofia e Lucas"
    assert v["data-competencia"] == "02/10 e 16/10" and v["mes-competencia"] == "outubro"
    assert v["numero-da-nota"] == "836, 837 e 838" and v["valor"] == "R$ 610,00"
    assert v["quantidade-de-notas"] == "3"
    assert v["lista-das-notas"] == "• Lucas Silva: 02/10 e 16/10\n• Sofia Silva: 16/10"
    assert v["assinatura"] == "*Assistente João:* "


def test_preencher_deixa_o_que_nao_e_variavel():
    assert vr.preencher("Oi [Nome-do-Responsavel], [x] e [ valor ]", {"nome-do-responsavel": "Ana", "valor": "R$ 1,00"}) \
        == "Oi Ana, [x] e R$ 1,00"


def test_validar_modelo():
    assert vr.validar("  Oi [nome-do-responsavel]\r\n ", vr.NOTA) == "Oi [nome-do-responsavel]"
    with pytest.raises(vr.ModeloInvalido, match="vazia"):
        vr.validar("  ", vr.NOTA)
    with pytest.raises(vr.ModeloInvalido, match=r"\[nome\]"):
        vr.validar("Oi [nome]", vr.NOTA)
    with pytest.raises(vr.ModeloInvalido, match="lista-das-notas"):
        vr.validar("[lista-das-notas]", vr.NOTA)  # só existe na de várias notas
    assert vr.validar("[lista-das-notas]", vr.NOTAS) == "[lista-das-notas]"


def test_api_modelos_previa_salvar_e_padrao(api):
    r = api.mensagens_modelos()
    assert r["nota"]["modelo"] == vr.MODELO_NOTA and "lista-das-notas" in [v["nome"] for v in r["notas"]["variaveis"]]
    p = api.mensagens_previa("nota", "Oi [primeiro-nome-do-responsavel], nota [numero-da-nota] [nada]")
    assert p["texto"] == "Oi Fernanda, nota 836 [nada]" and p["desconhecidas"] == ["nada"]
    assert "Não conheço [nada]" in api.mensagens_salvar("nota", "Oi [nada]")["erro"]
    r = api.mensagens_salvar("nota", "Bom dia, [nome-do-responsavel]! Nota nº [numero-da-nota] de [mes-competencia].")
    assert r["config"]["mensagem_nota"].startswith("Bom dia")
    # Salvar igual ao padrão guarda vazio.
    assert api.mensagens_salvar("notas", vr.MODELO_NOTAS)["config"]["mensagem_notas"] == ""
    assert api.mensagens_padrao("nota")["config"]["mensagem_nota"] == ""


def test_envio_usa_o_modelo(api):
    api.mensagens_salvar("nota", "Bom dia, [nome-do-responsavel]! Nota nº [numero-da-nota] de [mes-competencia].")
    r = api.notas_preparar_lote([803])
    assert r["destinos"][0]["mensagem"] == "Bom dia, Fernanda Costa! Nota nº 803 de outubro."
    api.mensagens_salvar("notas", "[quantidade-de-notas] notas para [primeiro-nome-do-responsavel]:\n[lista-das-notas]")
    r = api.notas_preparar_lote([801, 802], "", "Fulana de Tal")
    assert r["destinos"][0]["mensagem"] == ("2 notas para Fulana:\n• Ana Beatriz Moreira: 01/10\n"
                                            "• Carlos Eduardo Lima: 03/10")
    # Uma nota só no lote usa o modelo de uma nota.
    r = api.notas_preparar_lote([803])
    assert r["destinos"][0]["mensagem"].startswith("Bom dia, Fernanda Costa!")


def test_link_do_github(api):
    assert api.atualizacao_link()["link"].startswith("https://github.com/JoaoTroianoSegoria/")
