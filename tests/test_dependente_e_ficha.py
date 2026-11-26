"""1.15.0: nota de dependente com o nome dele no arquivo, a descrição esperada com dependente,
campos de pessoa que só aceitam o que faz sentido, e a ficha do paciente."""

from datetime import date

import pytest

from omac import sistema
from omac.app import Api
from omac.notas.leitor import Regras, interpretar_texto, problema_no_nome
from omac.texto import NomeInvalido, nome_de_pessoa
from tests.fabrica import cpf_ficticio, criar_nota, criar_pasta_exemplo
from tests.test_leitor import texto_nota

DESCRICAO = "TRATAMENTO ODONTOLÓGICO REFERENTE AO(A) DEPENDENTE LUCAS COSTA RIBEIRO"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "colar_sozinho_disponivel", lambda: False)
    monkeypatch.setattr(sistema, "abrir_link", lambda u: None)
    a = Api()
    a.pasta = criar_pasta_exemplo(tmp_path / "NFS-e 2026")
    a._cfg.update(pasta_notas=str(a.pasta))
    return a


# --- Leitura da nota -------------------------------------------------------------------


def test_arquivo_com_o_nome_do_dependente_e_o_certo():
    n = interpretar_texto(texto_nota(descricao=DESCRICAO, tomador="FERNANDA COSTA"),
                          "NFS-e Nº 000000835 - LUCAS COSTA RIBEIRO - 30-10 -.pdf")
    assert n.paciente == "LUCAS COSTA RIBEIRO" and n.dependente
    assert n.responsavel == "FERNANDA COSTA"  # quem recebe vem do PDF (o tomador)
    assert n.avisos == [] and problema_no_nome(n) == ""


def test_arquivo_antigo_com_o_nome_do_responsavel_continua_lido_e_pede_renomear():
    n = interpretar_texto(texto_nota(descricao=DESCRICAO, tomador="FERNANDA COSTA"),
                          "NFS-e Nº 000000835 - FERNANDA COSTA - 30-10 -.pdf")
    assert n.paciente == "LUCAS COSTA RIBEIRO" and n.responsavel == "FERNANDA COSTA"
    assert problema_no_nome(n) == "nome_do_responsavel"


def test_o_modelo_das_configuracoes_diz_onde_esta_o_nome_do_dependente():
    regras = Regras(servico_dependente="tratamento do paciente menor [nome-do-dependente], filho do responsável")
    n = interpretar_texto(texto_nota(descricao="TRATAMENTO DO PACIENTE MENOR JOÃO PEDRO ALVES, FILHO DO RESPONSÁVEL"),
                          "NFS-e Nº 000000835 - JOÃO PEDRO ALVES - 30-10 -.pdf", regras)
    assert n.paciente == "JOÃO PEDRO ALVES" and n.dependente and n.avisos == []
    # Texto depois do nome sem pontuação no meio também é cortado.
    regras = Regras(servico_dependente="referente a [nome-do-dependente] menor de idade")
    n = interpretar_texto(texto_nota(descricao="REFERENTE A ANA CLARA SOUZA MENOR DE IDADE"), "x.pdf", regras)
    assert n.paciente == "ANA CLARA SOUZA"


@pytest.mark.parametrize("descricao", [
    DESCRICAO,
    "TRATAMENTO ODONTOLÓGICO REFERENTE A(AO) DEPENDENTE LUCAS COSTA RIBEIRO",
    "Tratamento odontológico referente à dependente Lucas Costa Ribeiro.",
])
def test_descricao_com_dependente_nao_liga_para_artigo_e_pontuacao(descricao):
    n = interpretar_texto(texto_nota(descricao=descricao), "NFS-e Nº 000000835 - LUCAS COSTA RIBEIRO - 30-10 -.pdf")
    assert n.avisos == []


def test_aviso_quando_a_descricao_de_dependente_nao_esta_como_a_esperada():
    n = interpretar_texto(texto_nota(descricao="LIMPEZA DO DEPENDENTE LUCAS COSTA RIBEIRO"),
                          "NFS-e Nº 000000835 - LUCAS COSTA RIBEIRO - 30-10 -.pdf")
    assert n.dependente
    assert n.avisos == ["A descrição do serviço não está como a de dependente: "
                        "“tratamento odontológico referente ao(a) dependente LUCAS COSTA RIBEIRO”."]
    # Sem o modelo de dependente, vale a descrição de sempre.
    n = interpretar_texto(texto_nota(descricao="LIMPEZA DO DEPENDENTE LUCAS COSTA RIBEIRO"), "x.pdf",
                          Regras(servico_dependente=""))
    assert n.paciente == "LUCAS COSTA RIBEIRO" and n.avisos[0] == "A descrição do serviço não contém “tratamento odontológico”."


# --- Renomear (o bug da 1.14.0) ----------------------------------------------------------


def test_nota_de_dependente_vai_com_o_nome_dele_mesmo_com_o_cpf_do_responsavel_nos_contatos(api):
    """O bug: o Renomear achava o contato pelo CPF da nota, que é do responsável."""
    mae = api.contatos_salvar({"nome": "Fernanda Costa", "cpf": cpf_ficticio(5)})["salvo"]
    api.contatos_salvar({"nome": "Lucas Costa Ribeiro",
                         "responsaveis": [{"contato_id": mae["id"], "nome": "Fernanda Costa", "papel": "mae"}]})
    criar_nota(api.pasta / "1234567890.pdf", 813, date(2026, 11, 21), date(2026, 11, 23), "180.00",
               descricao=DESCRICAO, tomador="FERNANDA COSTA", cpf_tomador=cpf_ficticio(5))
    nota = next(n for n in api.notas_do_mes(2026, 11)["notas"] if n["numero"] == 813)
    assert nota["renomear"]["nome"] == "Lucas Costa Ribeiro"  # como está nos Contatos
    assert nota["renomear"]["para"] == "NFS-e Nº 000000813 - Lucas Costa Ribeiro - 23-11 - COMP 21-11.pdf"

    assert api.notas_renomear("1234567890.pdf", nota["renomear"]["para"])["arquivo"]
    nota = next(n for n in api.notas_do_mes(2026, 11)["notas"] if n["numero"] == 813)
    assert nota["renomear"] is None and nota["paciente"] == "LUCAS COSTA RIBEIRO"
    assert nota["responsavel"] == "FERNANDA COSTA"  # o envio pelo WhatsApp continua indo para ela


def test_nota_antiga_de_dependente_com_o_nome_do_responsavel_ganha_o_renomear(api):
    nota = next(n for n in api.notas_do_mes(2026, 10)["notas"] if n["numero"] == 803)  # fabrica: FERNANDA COSTA
    assert nota["renomear"]["motivo"] == "nome_do_responsavel"
    assert " - Lucas Costa Ribeiro - " in nota["renomear"]["para"]  # só as iniciais maiúsculas
    sem = [n for n in api.notas_do_mes(2026, 10)["notas"] if not n["dependente"]]
    assert all(n["renomear"] is None for n in sem)


def test_renomear_a_mao_qualquer_nota(api):
    nota = next(n for n in api.notas_do_mes(2026, 10)["notas"] if n["numero"] == 801)
    assert nota["renomear"] is None
    novo = nota["arquivo"].replace("ANA BEATRIZ MOREIRA", "Ana Beatriz Moreira")
    assert api.notas_renomear(nota["arquivo"], novo) == {"arquivo": novo}
    assert next(n for n in api.notas_do_mes(2026, 10)["notas"] if n["numero"] == 801)["arquivo"] == novo


def test_regras_guardam_a_descricao_com_dependente(api):
    padrao = api.notas_regras_padrao()
    assert padrao["servico_dependente"] == "tratamento odontológico referente ao(a) dependente [nome-do-dependente]"
    r = api.notas_salvar_regras(api._cfg["formato_arquivo"], "tratamento", "  referente  ao  menor [nome-do-dependente] ")
    assert r["config"]["servico_dependente"] == "referente ao menor [nome-do-dependente]"
    r = api.notas_salvar_regras(api._cfg["formato_arquivo"], "tratamento")  # tela antiga: não mexe
    assert r["config"]["servico_dependente"] == "referente ao menor [nome-do-dependente]"
    assert api._regras_notas().servico_dependente == "referente ao menor [nome-do-dependente]"


@pytest.mark.parametrize("pdf, sugerido", [
    ("LUCAS DA SILVA", "Lucas da Silva"),
    ("ANA-CLARA D'ÁVILA DOS SANTOS E SOUZA", "Ana-Clara D'Ávila dos Santos e Souza"),
    ("ÉRICA  ÇÃO", "Érica Ção"),
    ("Lucas Costa Ribeiro", "Lucas Costa Ribeiro"),
    ("DA SILVA", "Da Silva"),  # a primeira palavra é sempre maiúscula
])
def test_nome_sugerido_so_com_as_iniciais_maiusculas(pdf, sugerido):
    from omac.texto import nome_bonito
    assert nome_bonito(pdf) == sugerido


# --- Campos de pessoa --------------------------------------------------------------------


@pytest.mark.parametrize("nome", ["Ana", "  Ana   Clara  ", "Ana-Clara D'Ávila", "Dra. Ana Souza", "J. Silva Jr.",
                                  "João D’Ávila", "ÉRICA ÇÃO"])
def test_nomes_que_valem(nome):
    assert nome_de_pessoa(nome) == " ".join(nome.split())


@pytest.mark.parametrize("nome", ["Ana 2", "Ana_Clara", "Ana@", "(mãe) Ana", "Ana -", "Ana..", "Ana--Clara", "-Ana",
                                  "Ana / Bia", "123"])
def test_nomes_que_nao_valem(nome):
    with pytest.raises(NomeInvalido):
        nome_de_pessoa(nome)


def test_contato_e_atendimento_recusam_nome_com_numero(api):
    assert "Confira o nome" in api.contatos_salvar({"nome": "Ana 2"})["erro"]
    assert "Confira o nome" in api.contatos_salvar({
        "nome": "Lucas", "responsaveis": [{"nome": "Mãe 1", "papel": "mae"}]})["erro"]
    assert "Confira o nome" in api.atendimentos_salvar({"nome": "Paciente 1", "data": "2026-11-10"})["erro"]
    assert api.contatos_listar()["contatos"] == []  # nada ficou pela metade
    assert "erro" not in api.contatos_salvar({"nome": "Dra. Ana D'Ávila-Souza"})


def test_contato_antigo_fora_da_regra_continua_funcionando(api):
    """Salvo antes da 1.15.0: o atendimento acha pelo nome; só ao alterar o contato pede para corrigir."""
    from omac.dados import esquema
    with api._armazem.editar(esquema.CONTATOS) as d:
        d["contatos"].append({"id": "antigo", "nome": "Maria 2", "telefone": "", "cpf": "", "responsaveis": [],
                              "envia_para": "", "nota_para": "", "criado_em": "", "nascimento": ""})
    assert "erro" not in api.atendimentos_salvar({"nome": "Maria 2", "data": "2026-11-10"})
    assert "Confira o nome" in api.contatos_salvar({"nome": "Maria 2"}, "antigo")["erro"]


def test_telefone_so_com_numeros_e_sinais_de_telefone(api):
    assert "erro" not in api.contatos_salvar({"nome": "Ana", "telefone": "+55 (61) 98888-7777"})
    assert "só pode ter números" in api.contatos_salvar({"nome": "Bia", "telefone": "61 9888a-7777"})["erro"]


# --- Ficha do paciente ---------------------------------------------------------------------


def test_ficha_do_dependente_e_do_responsavel(api):
    mae = api.contatos_salvar({"nome": "Fernanda Costa", "telefone": "61 98888-7777", "cpf": cpf_ficticio(5)})["salvo"]
    lucas = api.contatos_salvar({
        "nome": "Lucas Costa Ribeiro", "nascimento": "2015-03-02",
        "responsaveis": [{"contato_id": mae["id"], "nome": "Fernanda Costa", "papel": "mae"}],
        "orto": True, "valor": "180", "situacao": "ativo"})["salvo"]
    api.atendimentos_salvar({"nome": "Lucas Costa Ribeiro", "data": "2026-10-06", "valor": "180", "pago": True,
                             "tratamento": "Manutenção"})
    api.atendimentos_salvar({"nome": "Lucas Costa Ribeiro", "data": "2026-11-06", "valor": "200"})
    api.notas_do_mes(2026, 10)  # lê a pasta (a nota 803 é do Lucas, no CPF da Fernanda)

    f = api.contatos_ficha(lucas["id"])
    assert f["nome"] == "Lucas Costa Ribeiro" and f["nascimento"] == "2015-03-02" and f["idade"] >= 11
    assert [(v["nome"], v["tipo"], v["relacao"], v["telefone"]) for v in f["vinculos"]] == [
        ("Fernanda Costa", "responsavel", "mãe", "5561988887777")]
    assert f["vinculos"][0]["cpf"] == cpf_ficticio(5)
    assert f["tratamento"]["situacao"] == "Em tratamento" and f["tratamento"]["valor_centavos"] == 18000
    a = f["atendimentos"]
    assert a["qtd"] == 2 and a["pago_centavos"] == 18000 and a["a_receber_centavos"] == 20000
    assert [x["data"] for x in a["ultimos"]] == ["2026-11-06", "2026-10-06"]  # o mais novo primeiro
    assert [n["numero"] for n in f["notas"]["ultimas"]] == [803] and f["notas"]["ultimas"][0]["de"] == ""

    f = api.contatos_ficha(mae["id"])
    assert [(v["nome"], v["tipo"], v["relacao"]) for v in f["vinculos"]] == [
        ("Lucas Costa Ribeiro", "dependente", "filho ou filha")]
    # A nota do Lucas aparece para ela como responsável (é no CPF dela).
    assert f["notas"]["ultimas"][0]["numero"] == 803 and f["notas"]["ultimas"][0]["de"] == "Lucas Costa Ribeiro"
    assert f["tratamento"] is None and f["atendimentos"]["qtd"] == 0


def test_ficha_sem_notas_lidas_e_de_contato_apagado(api):
    api._cfg.update(pasta_notas="")
    ana = api.contatos_salvar({"nome": "Ana"})["salvo"]
    assert api.contatos_ficha(ana["id"])["notas"] is None
    assert "Não encontrei" in api.contatos_ficha("nao-existe")["erro"]


def test_idade():
    from omac.contatos.ficha import idade
    assert idade("2015-03-02", date(2026, 3, 1)) == 10 and idade("2015-03-02", date(2026, 3, 2)) == 11
    assert idade("", date(2026, 1, 1)) is None and idade("xx", date(2026, 1, 1)) is None
