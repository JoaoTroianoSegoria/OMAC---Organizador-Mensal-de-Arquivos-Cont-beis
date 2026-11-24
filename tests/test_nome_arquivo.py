"""1.10.2: o PDF que o site baixa com um nome só de números, o número da próxima nota
(variável [numero-nota] da janela Emitir) e o nome certo do arquivo."""

from datetime import date
from decimal import Decimal

import pytest

from omac import sistema
from omac.app import Api
from omac.notas.leitor import Nota, Regras, nome_certo, problema_no_nome
from tests.fabrica import cpf_ficticio, criar_nota, criar_pasta_exemplo, nome_arquivo

NUMERICO = "589129308401233923233.pdf"


def _nota(arquivo, numero=13):
    return Nota(numero, "X", Decimal("180"), date(2026, 11, 23), date(2026, 11, 21), arquivo)


def test_nome_certo_no_jeito_da_clinica():
    n = _nota(NUMERICO)
    assert problema_no_nome(n) == "fora_do_formato"
    assert nome_certo(n, "Cintia Emi Nakaya Otta") == "NFS-e Nº 000000013 - Cintia Emi Nakaya Otta - 23-11 - COMP 21-11.pdf"


def test_nome_certo_segue_o_formato_das_configuracoes():
    regras = Regras("Nota [numero-da-nota] - [nome-do-paciente] ([data-competencia])")
    assert nome_certo(_nota(NUMERICO), "Ana", regras) == "Nota 000000013 - Ana (21-11).pdf"


def test_nome_certo_tira_o_que_o_windows_nao_aceita():
    assert nome_certo(_nota(NUMERICO), 'Ana/Bia: "X"') == "NFS-e Nº 000000013 - Ana Bia X - 23-11 - COMP 21-11.pdf"


def test_problema_no_nome():
    assert problema_no_nome(_nota("NFS-e Nº 000000013 - ANA - 23-11 -.pdf")) == ""
    assert problema_no_nome(_nota("NFS-e Nº 000000012 - ANA - 23-11 -.pdf")) == "numero_diferente"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "colar_sozinho_disponivel", lambda: False)
    a = Api()
    a.pasta = criar_pasta_exemplo(tmp_path / "NFS-e 2026")
    a._cfg.update(pasta_notas=str(a.pasta))
    return a


def _baixada(api, numero=813, tomador="RAFAEL MARTINS", cpf=None, nome=NUMERICO):
    """Uma nota como o site baixa: nome do arquivo só com números."""
    criar_nota(api.pasta / nome, numero, date(2026, 11, 21), date(2026, 11, 23), "180.00",
               tomador=tomador, cpf_tomador=cpf or cpf_ficticio(1))
    return nome


def test_proximo_numero_conta_as_canceladas(api):
    contato = api.contatos_salvar({"nome": "Ana"})["salvo"]
    assert api.contatos_cpf(contato["id"])["proximo_numero"] == 813
    canceladas = api.pasta / "Canceladas"
    canceladas.mkdir(exist_ok=True)
    (canceladas / nome_arquivo(820, "ALGUEM", date(2026, 11, 5))).write_bytes(b"%PDF")  # só o nome importa
    assert api.contatos_cpf(contato["id"])["proximo_numero"] == 821


def test_sem_pasta_ou_pasta_vazia_nao_chuta_o_numero(api, tmp_path):
    contato = api.contatos_salvar({"nome": "Ana"})["salvo"]
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    api._cfg.update(pasta_notas=str(vazia))
    assert api.contatos_cpf(contato["id"])["proximo_numero"] is None
    api._cfg.update(pasta_notas="")
    assert api.contatos_cpf(contato["id"])["proximo_numero"] is None


def test_nota_nova_com_nome_de_numeros_vem_com_o_nome_certo(api):
    api.notas_do_mes(2026, 11)
    _baixada(api)
    r = api.notas_do_mes(2026, 11)
    assert r["novas"] == [{"numero": 813, "paciente": "RAFAEL MARTINS", "renomear": {
        "motivo": "fora_do_formato", "de": NUMERICO, "nome": "RAFAEL MARTINS",
        "para": "NFS-e Nº 000000813 - RAFAEL MARTINS - 23-11 - COMP 21-11.pdf"}}]
    nota = next(n for n in r["notas"] if n["numero"] == 813)
    assert nota["renomear"]["para"].startswith("NFS-e Nº 000000813")
    assert all(n["renomear"] is None for n in r["notas"] if n["numero"] != 813)


def test_o_nome_vem_do_contato_pelo_cpf_ou_pelo_nome(api):
    cintia = api.contatos_salvar({"nome": "Cintia Emi Nakaya Otta"})["salvo"]
    api.contatos_salvar_cpf(cintia["id"], cintia["id"], cpf_ficticio(77))
    _baixada(api, tomador="OUTRO NOME NO PDF", cpf=cpf_ficticio(77))
    nota = next(n for n in api.notas_do_mes(2026, 11)["notas"] if n["numero"] == 813)
    assert nota["renomear"]["para"] == "NFS-e Nº 000000813 - Cintia Emi Nakaya Otta - 23-11 - COMP 21-11.pdf"

    api.contatos_salvar({"nome": "Rafael Martins"})
    _baixada(api, numero=814, nome="999.pdf")
    nota = next(n for n in api.notas_do_mes(2026, 11)["notas"] if n["numero"] == 814)
    assert " - Rafael Martins - " in nota["renomear"]["para"]


def test_renomear_e_ler_de_novo(api):
    api.notas_do_mes(2026, 11)
    _baixada(api)
    para = api.notas_do_mes(2026, 11)["novas"][0]["renomear"]["para"]
    assert api.notas_renomear(NUMERICO, para) == {"arquivo": para}
    assert not (api.pasta / NUMERICO).exists() and (api.pasta / para).is_file()
    nota = next(n for n in api.notas_do_mes(2026, 11)["notas"] if n["numero"] == 813)
    assert nota["arquivo"] == para and nota["renomear"] is None and nota["avisos"] == []
    assert nota["paciente"] == "RAFAEL MARTINS"


def test_renomear_nao_passa_por_cima_nem_aceita_nome_errado(api):
    api.notas_do_mes(2026, 11)
    _baixada(api)
    api.notas_do_mes(2026, 11)
    ocupado = next(api.pasta.glob("NFS-e Nº 000000812*")).name
    # Nome de outro arquivo (com o número 813, para passar da conferência do número)
    copia = ocupado.replace("000000812", "000000813")
    (api.pasta / copia).write_bytes((api.pasta / ocupado).read_bytes())
    assert "Já existe" in api.notas_renomear(NUMERICO, copia)["erro"]
    assert "diferente" in api.notas_renomear(NUMERICO, "NFS-e Nº 000000999 - ANA - 23-11")["erro"]
    assert "formato" in api.notas_renomear(NUMERICO, "qualquer coisa")["erro"]
    assert "não pode" in api.notas_renomear(NUMERICO, "NFS-e Nº 000000813 - A/B - 23-11")["erro"]
    assert "Não encontrei" in api.notas_renomear("sumiu.pdf", "NFS-e Nº 000000813 - ANA - 23-11")["erro"]
    assert (api.pasta / NUMERICO).is_file()  # nada mudou
