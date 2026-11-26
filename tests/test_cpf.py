"""1.9.0: CPF no contato, sugestão pelas notas e a janela "Emitir nota"."""

from datetime import date
from decimal import Decimal

import pytest

from omac import sistema
from omac.app import Api
from omac.contatos import cpf as cpfs
from omac.notas.leitor import Nota
from tests.fabrica import cpf_ficticio, criar_pasta_exemplo

VALIDO = cpf_ficticio(529982247)  # 529.982.247-25
NUMEROS = VALIDO.replace(".", "").replace("-", "")


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    abertos = []
    monkeypatch.setattr(sistema, "abrir_link", abertos.append)
    a = Api()
    a.abertos = abertos
    a._cfg.update(pasta_notas=str(criar_pasta_exemplo(tmp_path / "NFS-e 2026")))
    return a


def _salvar(api, contato_id=None, **dados):
    r = api.contatos_salvar(dados, contato_id)
    assert "erro" not in r, r
    return r


def _por_nome(r):
    return {c["nome"]: c for c in r["contatos"]}


# --- Conferir e formatar -------------------------------------------------------------------


def test_cpf_ficticio_e_valido_e_formatado():
    assert VALIDO == "529.982.247-25"
    assert cpfs.confere(NUMEROS)


@pytest.mark.parametrize("digitado", ["529.982.247-25", "52998224725", "529.982.247.25", " 529.982.247-25 ",
                                      "529982247-25"])
def test_aceita_os_jeitos_de_escrever_com_11_numeros(digitado):
    assert cpfs.limpar(digitado) == NUMEROS
    assert cpfs.formatar(cpfs.limpar(digitado)) == VALIDO


@pytest.mark.parametrize("digitado, trecho", [
    ("529 982 247 25", "só pode ter números"),  # espaço no meio
    ("529.982.247-2a", "só pode ter números"),
    ("CPF 529.982.247-25", "só pode ter números"),
    ("529/982/247-25", "só pode ter números"),
    ("529.982247-25", "pontos e o traço"),  # ponto num lugar e no outro não
    ("5299.82.247-25", "pontos e o traço"),
    ("529..982.247-25", "pontos e o traço"),
])
def test_recusa_cpf_com_outros_caracteres(digitado, trecho):
    """1.15.0: letra, espaço ou símbolo no meio não são mais jogados fora sem avisar."""
    with pytest.raises(cpfs.CpfInvalido, match=trecho):
        cpfs.limpar(digitado)


@pytest.mark.parametrize("ruim, trecho", [
    ("529.982.247-26", "não confere"),  # último dígito errado
    ("529.982.274-25", "não confere"),  # dois números trocados
    ("111.111.111-11", "não confere"),  # todos iguais passam na conta, mas não valem
    ("5299822472", "11 números (tem 10)"),
    ("529.982.247-255", "11 números (tem 12)"),
])
def test_recusa_cpf_errado(ruim, trecho):
    with pytest.raises(cpfs.CpfInvalido, match=trecho.replace("(", r"\(").replace(")", r"\)")):
        cpfs.limpar(ruim)


def test_vazio_continua_vazio():
    assert cpfs.limpar("") == "" and cpfs.limpar("   ") == "" and cpfs.limpar(None) == ""


# --- No contato ----------------------------------------------------------------------------


def test_contato_guarda_so_os_numeros(api):
    r = _salvar(api, nome="Ana Souza", cpf="529.982.247.25")
    ana = _por_nome(r)["Ana Souza"]
    assert ana["cpf"] == NUMEROS
    # Alterar sem mandar o campo (tela antiga) não apaga; mandar vazio apaga.
    r = _salvar(api, ana["id"], nome="Ana Souza")
    assert _por_nome(r)["Ana Souza"]["cpf"] == NUMEROS
    r = _salvar(api, ana["id"], nome="Ana Souza", cpf="")
    assert _por_nome(r)["Ana Souza"]["cpf"] == ""


def test_cpf_errado_nao_salva_nada(api):
    assert "não confere" in api.contatos_salvar({"nome": "Ana", "cpf": "123.456.789-00"})["erro"]
    assert api.contatos_listar()["contatos"] == []
    r = api.contatos_salvar({"nome": "Bia", "responsaveis": [{"nome": "Mãe da Bia", "papel": "mae", "cpf": "123"}]})
    assert "CPF de Mãe da Bia precisa ter 11 números" in r["erro"]
    assert api.contatos_listar()["contatos"] == []


def test_cpf_do_responsavel_vai_para_o_contato_dele(api):
    r = _salvar(api, nome="Pedro", responsaveis=[{"nome": "Helena", "papel": "mae", "cpf": VALIDO}])
    assert _por_nome(r)["Helena"]["cpf"] == NUMEROS
    pedro = _por_nome(r)["Pedro"]
    assert pedro["responsaveis"][0]["cpf"] == NUMEROS
    # Linha sem CPF não apaga o que o responsável já tinha.
    r = _salvar(api, pedro["id"], nome="Pedro", responsaveis=[{"nome": "Helena", "papel": "mae", "cpf": ""}])
    assert _por_nome(r)["Helena"]["cpf"] == NUMEROS


# --- Sugestão pelas notas ------------------------------------------------------------------


def _nota(numero, arquivo_nome, tomador, cpf, emissao=date(2026, 10, 1), paciente=None, dependente=False):
    return Nota(numero=numero, paciente=paciente or arquivo_nome, valor=Decimal("100"), emissao=emissao,
                competencia=emissao, arquivo=f"NFS-e Nº {numero:09d} - {arquivo_nome} - 01-10 -.pdf",
                dependente=dependente, tomador=tomador, cpf_tomador=cpf)


def test_sugestao_pega_a_nota_mais_recente_do_nome():
    outro = cpf_ficticio(111222333).replace(".", "").replace("-", "")
    notas = [_nota(1, "ANA SOUZA", "ANA SOUZA LIMA", outro, date(2026, 9, 1)),
             _nota(2, "ANA SOUZA", "ANA SOUZA LIMA", NUMEROS, date(2026, 10, 1))]
    assert cpfs.sugestao("Ana Souza", notas) == {"cpf": NUMEROS, "numero": 2}
    # O nome completo do tomador também vale.
    assert cpfs.sugestao("ana souza lima", notas)["numero"] == 2


def test_sugestao_ignora_dependente_cpf_invalido_e_nomes_que_nao_batem():
    notas = [_nota(3, "FERNANDA COSTA", "FERNANDA COSTA", NUMEROS, paciente="LUCAS COSTA", dependente=True),
             _nota(4, "JOSE", "JOSE", "00000000000")]
    assert cpfs.sugestao("Fernanda Costa", notas)["cpf"] == NUMEROS
    assert cpfs.sugestao("Lucas Costa", notas) is None  # o CPF da nota é da mãe
    assert cpfs.sugestao("Jose", notas) is None
    assert cpfs.sugestao("Maria", notas) is None


def test_nomes_parecidos_com_cpfs_diferentes_nao_sugerem():
    a = cpf_ficticio(111222333).replace(".", "").replace("-", "")
    notas = [_nota(5, "JOAO SILVA SANTOS", "JOAO SILVA SANTOS", a), _nota(6, "JOAO SILVA COSTA", "JOAO SILVA COSTA", NUMEROS)]
    assert cpfs.sugestao("Joao Silva", notas) is None


def test_leitor_acha_o_cpf_do_tomador_nas_notas_de_exemplo(api):
    notas = {n.numero: n for n in api._servico_notas.ler().notas}
    assert notas[801].cpf_tomador == cpf_ficticio(123456801).replace(".", "").replace("-", "")
    assert notas[801].tomador == "ANA BEATRIZ MOREIRA"


# --- Janela "Emitir nota" ------------------------------------------------------------------


def test_janela_emitir_com_responsaveis_e_sugestao(api):
    # Lucas é dependente da Fernanda: a nota 803 tem o CPF dela.
    r = _salvar(api, nome="LUCAS COSTA RIBEIRO", responsaveis=[{"nome": "FERNANDA COSTA", "papel": "mae"}])
    lucas = _por_nome(r)["LUCAS COSTA RIBEIRO"]
    v = api.contatos_cpf(lucas["id"])
    assert [p["nome"] for p in v["pessoas"]] == ["LUCAS COSTA RIBEIRO", "FERNANDA COSTA"]
    assert [p["papel"] for p in v["pessoas"]] == ["", "mãe"]
    fernanda = v["pessoas"][1]
    assert fernanda["cpf"] == "" and fernanda["sugestao"] == {"cpf": cpf_ficticio(123456803), "numero": 803}
    assert v["pessoas"][0]["sugestao"] is None
    # Quem tem sugestão já vem escolhido.
    assert v["escolhido"] == fernanda["contato_id"]

    v = api.contatos_salvar_cpf(lucas["id"], fernanda["contato_id"], fernanda["sugestao"]["cpf"])
    assert v["pessoas"][1]["cpf"] == cpf_ficticio(123456803) and v["pessoas"][1]["sugestao"] is None
    assert v["escolhido"] == fernanda["contato_id"]

    # Escolher o próprio paciente fica guardado para a próxima vez.
    api.contatos_nota_para(lucas["id"], lucas["id"])
    assert api.contatos_cpf(lucas["id"])["escolhido"] == lucas["id"]
    # Um contato que não é dele não vale.
    outro = _por_nome(_salvar(api, nome="Outra Pessoa"))["Outra Pessoa"]
    api.contatos_nota_para(lucas["id"], outro["id"])
    assert api.contatos_cpf(lucas["id"])["escolhido"] == lucas["id"]


def test_cpf_guardado_diferente_da_nota_avisa(api):
    r = _salvar(api, nome="ANA BEATRIZ MOREIRA", cpf=VALIDO)
    ana = _por_nome(r)["ANA BEATRIZ MOREIRA"]
    p = api.contatos_cpf(ana["id"])["pessoas"][0]
    assert p["cpf"] == VALIDO and p["sugestao"]["numero"] == 801


def test_salvar_cpf_errado_pela_janela(api):
    ana = _por_nome(_salvar(api, nome="Ana"))["Ana"]
    assert "não confere" in api.contatos_salvar_cpf(ana["id"], ana["id"], "529.982.247-26")["erro"]
    assert api.contatos_salvar_cpf(ana["id"], ana["id"], "52998224725")["pessoas"][0]["cpf"] == VALIDO
    assert api.contatos_salvar_cpf(ana["id"], ana["id"], "")["pessoas"][0]["cpf"] == ""


def test_sugestao_para_a_janela_de_contato(api):
    assert api.contatos_sugestao_cpf("Carlos Eduardo Lima")["sugestao"]["numero"] == 802
    assert api.contatos_sugestao_cpf("Ninguém")["sugestao"] is None
    assert api.contatos_sugestao_cpf("  ")["sugestao"] is None


def test_sem_pasta_de_notas_a_janela_funciona(api):
    api._cfg["pasta_notas"] = ""
    ana = _por_nome(_salvar(api, nome="Ana", cpf=VALIDO))["Ana"]
    v = api.contatos_cpf(ana["id"])
    assert v["pessoas"][0]["cpf"] == VALIDO and v["pessoas"][0]["sugestao"] is None


def test_juntar_contatos_leva_o_cpf(api):
    r = _salvar(api, nome="Rafael Martins")
    _salvar(api, nome="Rafael Martins Costa", cpf=VALIDO)
    c = _por_nome(api.contatos_listar())
    r = api.contatos_juntar(c["Rafael Martins"]["id"], c["Rafael Martins Costa"]["id"])
    assert _por_nome(r)["Rafael Martins"]["cpf"] == NUMEROS


def test_site_da_nota(api):
    assert "Configurações" in api.abrir_site_nota()["erro"]
    api._cfg["site_nota"] = "www.nfse.gov.br/EmissorNacional"
    assert api.abrir_site_nota() == {}
    assert api.abertos == ["https://www.nfse.gov.br/EmissorNacional"]
    ana = _por_nome(_salvar(api, nome="Ana"))["Ana"]
    assert api.contatos_cpf(ana["id"])["site"] == "www.nfse.gov.br/EmissorNacional"


# --- 1.10.1: nascimento e comandos na janela Emitir ------------------------------------------


def test_nascimento_no_contato(api):
    ana = _por_nome(_salvar(api, nome="Ana", nascimento="2015-03-14"))["Ana"]
    assert ana["nascimento"] == "2015-03-14"
    assert _por_nome(_salvar(api, ana["id"], nome="Ana"))["Ana"]["nascimento"] == "2015-03-14"  # sem o campo: fica
    assert "depois de hoje" in api.contatos_salvar({"nome": "Bia", "nascimento": "2999-01-01"})["erro"]
    assert "Confira" in api.contatos_salvar({"nome": "Bia", "nascimento": "14/03/2015"})["erro"]


def test_dependente_pela_janela_emitir(api):
    r = _salvar(api, nome="LUCAS", responsaveis=[{"nome": "FERNANDA", "papel": "mae"}])
    lucas = _por_nome(r)["LUCAS"]
    v = api.contatos_salvar_nascimento(lucas["id"], lucas["id"], "2015-03-14")
    assert v["pessoas"][0]["nascimento"] == "2015-03-14"
    assert "erro" in api.contatos_salvar_nascimento(lucas["id"], lucas["id"], "amanhã")
    assert api.contatos_salvar_nascimento(lucas["id"], lucas["id"], "")["pessoas"][0]["nascimento"] == ""


def test_categoria_da_emissao_fica_guardada(api):
    ana = _por_nome(_salvar(api, nome="Ana"))["Ana"]
    assert api.contatos_cpf(ana["id"])["categoria"] == ""
    assert api.contatos_categoria_emissao("abc123") == {}
    assert api.contatos_cpf(ana["id"])["categoria"] == "abc123"
