from datetime import date
from decimal import Decimal

import pytest

from omac.notas.leitor import NotaIlegivel, interpretar_texto, ler_nome_arquivo

ARQUIVO = "NFS-e Nº 000000835 - MARIA EXEMPLO - 30-10 -.pdf"


def texto_nota(
    numero="835",
    competencia="30/10/2026",
    emissao="30/10/2026 18:56:57",
    situacao="NFS-e gerada",
    descricao="TRATAMENTO ODONTOLÓGICO",
    valor="R$ 350,00",
    tomador="RESPONSAVEL EXEMPLO",
):
    # Mesma ordem em que o pdfium devolve o texto do DANFSe v2.0.
    return f"""DANFSe v2.0
Documento Auxiliar da NFS-e
NÚMERO DA NFS-E
{numero}
COMPETÊNCIA DA NFS-E
{competencia}
DATA E HORA DA EMISSÃO DA NFS-E
{emissao}
EMITENTE DA NFS-E
Prestador
SITUAÇÃO DA NFS-E
{situacao}
FINALIDADE
NFS-e regular
TOMADOR / ADQUIRENTE
CNPJ / CPF / NIF
000.000.000-00
Nome / Nome Empresarial
{tomador}
SERVIÇO PRESTADO
Descrição do Serviço
{descricao}
TRIBUTAÇÃO MUNICIPAL (ISSQN) Tipo de Tributação do ISSQN
VALOR TOTAL DA NFS-E VALOR DA OPERAÇÃO / SERVIÇO
{valor}
Desconto Incondicionado
Total das Retenções (ISSQN / Federais)
-
VALOR LÍQUIDO DA NFS-e
{valor}
"""


def test_nota_normal():
    n = interpretar_texto(texto_nota(), ARQUIVO)
    assert n.numero == 835
    assert n.paciente == "MARIA EXEMPLO"  # vem do nome do arquivo, não do tomador
    assert n.valor == Decimal("350.00")
    assert n.emissao == date(2026, 10, 30)
    assert n.competencia == date(2026, 10, 30)
    assert not n.dependente and not n.cancelada
    assert n.avisos == []


def test_competencia_diferente_da_emissao():
    n = interpretar_texto(texto_nota(competencia="31/10/2026", emissao="03/11/2026 09:00:00"), ARQUIVO)
    assert n.competencia == date(2026, 10, 31)
    assert n.emissao == date(2026, 11, 3)


def test_valor_com_milhar():
    n = interpretar_texto(texto_nota(valor="R$ 12.345,67"), ARQUIVO)
    assert n.valor == Decimal("12345.67")


def test_valor_total_preenchido_ao_lado():
    # Se "VALOR TOTAL" tiver valor, ele vem antes; o que vale é o do serviço.
    t = texto_nota().replace(
        "VALOR TOTAL DA NFS-E VALOR DA OPERAÇÃO / SERVIÇO\nR$ 350,00",
        "VALOR TOTAL DA NFS-E\nR$ 999,00\nVALOR DA OPERAÇÃO / SERVIÇO\nR$ 350,00",
    )
    assert interpretar_texto(t, ARQUIVO).valor == Decimal("350.00")


@pytest.mark.parametrize(
    "descricao, esperado",
    [
        ("TRATAMENTO ODONTOLÓGICO REFERENTE A(AO) DEPENDENTE JOSÉ DA SILVA", "JOSÉ DA SILVA"),
        ("TRATAMENTO ODONTOLÓGICO REFERENTE AO DEPENDENTE JOSÉ DA SILVA", "JOSÉ DA SILVA"),
        ("Tratamento odontológico referente à dependente Ana Clara Souza.", "ANA CLARA SOUZA"),
        ("TRATAMENTO ODONTOLÓGICO REFERENTE AO DEPENDENTE: PEDRO ALVES - CPF 123", "PEDRO ALVES"),
        ("TRATAMENTO ODONTOLÓGICO REFERENTE AO\nDEPENDENTE LUCAS\nRIBEIRO", "LUCAS RIBEIRO"),
    ],
)
def test_dependente_tem_prioridade(descricao, esperado):
    n = interpretar_texto(texto_nota(descricao=descricao), ARQUIVO)
    assert n.paciente == esperado
    assert n.dependente
    assert n.avisos == []


def test_aviso_sem_tratamento_odontologico():
    n = interpretar_texto(texto_nota(descricao="CONSULTA"), ARQUIVO)
    assert any("tratamento odontológico" in a for a in n.avisos)


def test_tratamento_sem_acento_nao_gera_aviso():
    n = interpretar_texto(texto_nota(descricao="TRATAMENTO ODONTOLOGICO"), ARQUIVO)
    assert n.avisos == []


def test_arquivo_fora_do_padrao_usa_tomador():
    n = interpretar_texto(texto_nota(), "nota qualquer.pdf")
    assert n.paciente == "RESPONSAVEL EXEMPLO"
    assert any("fora do padrão" in a for a in n.avisos)


def test_numero_do_arquivo_diferente():
    n = interpretar_texto(texto_nota(numero="836"), ARQUIVO)
    assert n.numero == 836
    assert any("diferente" in a for a in n.avisos)


@pytest.mark.parametrize("situacao", ["NFS-e cancelada", "Cancelada", "NFS-E CANCELADA"])
def test_cancelada(situacao):
    assert interpretar_texto(texto_nota(situacao=situacao), ARQUIVO).cancelada


def test_marca_dagua_cancelada():
    assert interpretar_texto(texto_nota() + "\nCANCELADA\n", ARQUIVO).cancelada


def test_marca_com_o_nome_do_documento_na_linha():
    assert interpretar_texto(texto_nota() + "\nNFS-e CANCELADA\n", ARQUIVO).cancelada


@pytest.mark.parametrize("trecho", [
    "Consulta cancelada dia 03 reagendada", "Paciente Cancelado Exemplo", "cancelado pela operadora: glosa",
])
def test_palavra_solta_nao_tira_a_nota_do_relatorio(trecho):
    nota = interpretar_texto(texto_nota() + f"\n{trecho}\n", ARQUIVO)
    assert not nota.cancelada
    assert any("cancelada" in a for a in nota.avisos)


def test_nota_normal_nao_ganha_aviso_de_cancelada():
    assert not any("cancelada" in a for a in interpretar_texto(texto_nota(), ARQUIVO).avisos)


def test_campos_faltando():
    with pytest.raises(NotaIlegivel, match="competência"):
        interpretar_texto(texto_nota().replace("COMPETÊNCIA DA NFS-E", "XXX"), ARQUIVO)


def test_pdf_sem_texto():
    with pytest.raises(NotaIlegivel, match="escaneada"):
        interpretar_texto("   \n", ARQUIVO)


@pytest.mark.parametrize(
    "nome, esperado",
    [
        ("NFS-e Nº 000000835 - MARIA EXEMPLO - 30-10 -.pdf", (835, "MARIA EXEMPLO")),
        ("NFS-e Nº 000000835 - MARIA EXEMPLO - 03-11 - 31-10.pdf", (835, "MARIA EXEMPLO")),
        ("NFS-e N° 000000012 - ANA-MARIA SOUZA - 1-2 -.pdf", (12, "ANA-MARIA SOUZA")),
        ("NFS-e Nº 000000835 - maria   exemplo - 30-10.pdf", (835, "MARIA EXEMPLO")),
        ("NFSe No 835 - JOÃO - 30-10 -.pdf", (835, "JOÃO")),
        ("Relatório.pdf", None),
    ],
)
def test_nome_arquivo(nome, esperado):
    assert ler_nome_arquivo(nome) == esperado
