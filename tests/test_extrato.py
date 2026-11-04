from datetime import date
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from omac import fechamento
from omac.extrato import regras as rg
from omac.extrato.exportar import ABA_EXTRATO, ABA_RESUMO, COLUNAS, descricao_para_planilha
from omac.extrato.leitor import ExtratoIlegivel, Lancamento, interpretar_texto, ler_extrato
from omac.extrato.pasta import consolidar, varrer
from tests.fabrica import criar_extrato, criar_nota, criar_pasta_extratos

CABECALHO = """Solicitado em: 02/10/2026 - 16h33
CLINICA EXEMPLO LTDA
CPF/CNPJ: 00.000.000/0001-00, Instituição: Banco Inter, Agência: 0001-9, Conta: 000000-0
Período: 01/09/2026 a 30/09/2026
Saldo total
R$ 900,00
"""


def linha(data, tipo, valor, saldo=Decimal("0"), descricao=""):
    return Lancamento(data, tipo, descricao, Decimal(valor), Decimal(saldo))


# --- Leitura -------------------------------------------------------------------


def test_le_os_formatos_de_lancamento():
    e = interpretar_texto(CABECALHO + """1 de Setembro de 2026 Saldo do dia: R$ 1.000,00 Valor Saldo por transação
Pix recebido: "PESSOA FICTICIA" R$ 200,00 R$ 1.000,00
2 de Setembro de 2026 Saldo do dia: R$ 900,00
Pix enviado: "Cp :60701190-FORNECEDOR FICTICIO" -R$ 50,00 R$ 950,00
SIMPLES NACIONAL -R$ 50,00 R$ 900,00
Fale com a gente
""", "x.pdf")
    assert (e.inicio, e.fim) == (date(2026, 9, 1), date(2026, 9, 30))
    assert e.solicitado_em.date() == date(2026, 10, 2)
    assert [(l.data.day, l.tipo, l.descricao, l.valor, l.saldo) for l in e.lancamentos] == [
        (1, "Pix recebido", "PESSOA FICTICIA", Decimal("200.00"), Decimal("1000.00")),
        (2, "Pix enviado", "FORNECEDOR FICTICIO", Decimal("-50.00"), Decimal("950.00")),
        (2, "SIMPLES NACIONAL", "", Decimal("-50.00"), Decimal("900.00")),
    ]
    assert e.avisos == []


def test_valor_com_milhar_e_saldo_negativo():
    e = interpretar_texto(CABECALHO + """1 de Setembro de 2026 Saldo do dia: -R$ 1.000,00
Aplicacao: "CDB" -R$ 12.345,67 -R$ 1.000,00
""")
    assert e.lancamentos[0].valor == Decimal("-12345.67")
    assert e.lancamentos[0].saldo == Decimal("-1000.00")
    assert e.lancamentos[0].sentido == "saida"


def test_avisa_quando_o_saldo_nao_fecha():
    e = interpretar_texto(CABECALHO + """1 de Setembro de 2026 Saldo do dia: R$ 500,00
Pix recebido: "A" R$ 100,00 R$ 100,00
Pix recebido: "B" R$ 100,00 R$ 500,00
""")
    assert any("saldo não fecha" in a for a in e.avisos)


def test_avisa_linha_com_valor_que_nao_deu_para_ler():
    e = interpretar_texto(CABECALHO + """1 de Setembro de 2026 Saldo do dia: R$ 100,00
Lancamento quebrado R$ 100,00
""")
    assert any("não consegui ler" in a for a in e.avisos)


def test_recusa_pdf_que_nao_e_extrato(tmp_path):
    with pytest.raises(ExtratoIlegivel):
        interpretar_texto("DANFSe v2.0\nNÚMERO DA NFS-E\n123")
    nota = criar_nota(tmp_path / "nota.pdf", 1, date(2026, 9, 1), date(2026, 9, 1), "10.00")
    with pytest.raises(ExtratoIlegivel):
        ler_extrato(nota)


def test_le_o_pdf_de_exemplo(tmp_path):
    c = varrer(criar_pasta_extratos(tmp_path))
    assert c.meses() == [(2026, 9, 4), (2026, 10, 11)]
    assert c.avisos == []
    assert all(not e.avisos for e in c.extratos)  # todos os saldos fecham
    assert c.do_mes(2026, 10)[-1].saldo == Decimal("10195.30")


# --- Vários extratos juntos ------------------------------------------------------


def _extrato(tmp_path, nome, inicio, fim, baixado, saldo, lancamentos):
    return ler_extrato(criar_extrato(tmp_path / nome, inicio, fim, baixado, saldo, lancamentos))


def test_dia_repetido_vem_do_extrato_mais_recente(tmp_path):
    # O primeiro foi baixado no meio do dia 04: ainda não tinha o Pix de 150.
    antigo = _extrato(tmp_path, "a.pdf", date(2026, 8, 4), date(2026, 9, 4), date(2026, 9, 4), "1000.00", [
        (date(2026, 9, 3), 'Pix recebido: "A"', "100.00"),
        (date(2026, 9, 4), 'Pix recebido: "B"', "200.00"),
    ])
    novo = _extrato(tmp_path, "b.pdf", date(2026, 9, 1), date(2026, 9, 30), date(2026, 10, 2), "1000.00", [
        (date(2026, 9, 3), 'Pix recebido: "A"', "100.00"),
        (date(2026, 9, 4), 'Pix recebido: "C"', "150.00"),
        (date(2026, 9, 4), 'Pix recebido: "B"', "200.00"),
    ])
    c = consolidar([novo, antigo])
    assert [l.descricao for l in c.do_mes(2026, 9)] == ["A", "C", "B"]


def test_dias_sem_extrato_com_saldo_diferente_geram_aviso(tmp_path):
    julho = _extrato(tmp_path, "j.pdf", date(2026, 7, 1), date(2026, 7, 31), date(2026, 8, 5), "1000.00",
                     [(date(2026, 7, 31), 'Pix recebido: "A"', "100.00")])
    agosto = _extrato(tmp_path, "a.pdf", date(2026, 8, 4), date(2026, 8, 31), date(2026, 9, 5), "1000.00",
                      [(date(2026, 8, 4), 'Pix recebido: "B"', "50.00")])
    avisos = consolidar([julho, agosto]).avisos_do_mes(2026, 8, hoje=date(2026, 11, 1))
    assert len(avisos) == 1
    assert "01/08/2026 a 03/08/2026" in avisos[0]["mensagem"]
    assert "-R$ 100,00" in avisos[0]["mensagem"]


def test_dias_sem_extrato_e_saldo_igual_nao_geram_aviso(tmp_path):
    julho = _extrato(tmp_path, "j.pdf", date(2026, 7, 1), date(2026, 7, 31), date(2026, 8, 5), "1000.00",
                     [(date(2026, 7, 31), 'Pix recebido: "A"', "100.00")])
    agosto = _extrato(tmp_path, "a.pdf", date(2026, 8, 4), date(2026, 8, 31), date(2026, 9, 5), "1100.00",
                      [(date(2026, 8, 4), 'Pix recebido: "B"', "50.00")])
    assert consolidar([julho, agosto]).avisos_do_mes(2026, 8, hoje=date(2026, 11, 1)) == []


def test_avisa_extrato_baixado_no_proprio_dia(tmp_path):
    e = _extrato(tmp_path, "s.pdf", date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 30), "1000.00",
                 [(date(2026, 9, 2), 'Pix recebido: "A"', "100.00")])
    avisos = consolidar([e]).avisos_do_mes(2026, 9, hoje=date(2026, 11, 1))
    assert any("próprio dia 30/09/2026" in a["mensagem"] for a in avisos)


def test_dias_depois_do_download_nao_contam_como_cobertos(tmp_path):
    e = _extrato(tmp_path, "s.pdf", date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 15), "1000.00",
                 [(date(2026, 9, 2), 'Pix recebido: "A"', "100.00")])
    avisos = consolidar([e]).avisos_do_mes(2026, 9, hoje=date(2026, 11, 1))
    assert any("16/09/2026 a 30/09/2026" in a["mensagem"] for a in avisos)


def test_pdf_estranho_na_pasta_vira_aviso_sem_travar(tmp_path):
    criar_pasta_extratos(tmp_path)
    criar_nota(tmp_path / "boleto.pdf", 1, date(2026, 9, 1), date(2026, 9, 1), "10.00")
    (tmp_path / "quebrado.pdf").write_bytes(b"nao e pdf")
    c = varrer(tmp_path)
    assert {a["arquivo"] for a in c.avisos} == {"boleto.pdf", "quebrado.pdf"}
    assert len(c.extratos) == 2


# --- Regras ----------------------------------------------------------------------


def test_regras_padrao_classificam_entradas():
    pix = linha(date(2026, 9, 1), "Pix recebido", "10", descricao="PESSOA")
    credito = linha(date(2026, 9, 1), "Credito domicilio cartao", "10", descricao="CARTAO DE CREDITO - X")
    debito = linha(date(2026, 9, 1), "Credito domicilio cartao", "10", descricao="CARTAO DE DEBITO - X")
    assert rg.classificar(pix, rg.REGRAS_PADRAO) == "RECEBIMENTO DE PIX PACIENTE"
    assert rg.classificar(credito, rg.REGRAS_PADRAO) == "ENTRADA DE PAGAMENTO CRÉDITO"
    assert rg.classificar(debito, rg.REGRAS_PADRAO) == "DÉBITO RECEBIMENTO"


def test_regra_respeita_o_sentido():
    regras = [{"sentido": "saida", "quando": "FORNECEDOR", "operacao": "COMPRA"}]
    assert rg.classificar(linha(date(2026, 9, 1), "Pagamento", "-5", descricao="FORNECEDOR"), regras) == "COMPRA"
    assert rg.classificar(linha(date(2026, 9, 1), "Estorno", "5", descricao="FORNECEDOR"), regras) == ""


def test_regra_ignora_acento_e_maiuscula_e_exige_palavra_inteira():
    regras = [{"sentido": "saida", "quando": "cêb", "operacao": "ENERGIA"}]
    assert rg.classificar(linha(date(2026, 9, 1), "Pagamento CEB Distribuicao", "-5"), regras) == "ENERGIA"
    assert rg.classificar(linha(date(2026, 9, 1), "Pix", "-5", descricao="RECEBEDOR"), regras) == ""


def test_regra_mais_especifica_ganha():
    regras = [
        {"sentido": "saida", "quando": "SEGURADORA", "operacao": "SEGURO"},
        {"sentido": "saida", "quando": "SEGURADORA SAUDE", "operacao": "PLANO DE SAÚDE"},
    ]
    assert rg.classificar(linha(date(2026, 9, 1), "Pag", "-5", descricao="SEGURADORA SAUDE S A"), regras) == "PLANO DE SAÚDE"


def test_adicionar_substitui_a_mesma_regra_e_edita():
    regras = rg.adicionar([], {"sentido": "saida", "quando": "X", "operacao": "A"})
    regras = rg.adicionar(regras, {"sentido": "saida", "quando": "x", "operacao": "B"})
    assert [r["operacao"] for r in regras] == ["B"]
    regras = rg.adicionar(regras, {"sentido": "saida", "quando": "Y", "operacao": "C"},
                          antiga={"sentido": "saida", "quando": "X"})
    assert [r["quando"] for r in regras] == ["Y"]
    assert rg.remover(regras, {"sentido": "saida", "quando": "y"}) == []


@pytest.mark.parametrize("ruim", [
    {"sentido": "saida", "quando": "", "operacao": "A"},
    {"sentido": "saida", "quando": "X", "operacao": "  "},
    {"sentido": "outro", "quando": "X", "operacao": "A"},
])
def test_regra_incompleta_e_recusada(ruim):
    with pytest.raises(rg.RegraInvalida):
        rg.adicionar([], ruim)


def test_regras_salvam_e_importam(tmp_path):
    arquivo = tmp_path / "r.json"
    assert rg.carregar(arquivo) == rg.REGRAS_PADRAO  # primeira vez
    rg.salvar(arquivo, [{"sentido": "saida", "quando": "X", "operacao": "A"}])
    assert rg.carregar(arquivo)[0]["quando"] == "X"
    juntas, qtd = rg.importar(rg.REGRAS_PADRAO, arquivo)
    assert qtd == 1 and len(juntas) == len(rg.REGRAS_PADRAO) + 1


def test_arquivo_de_regras_ruim_nao_e_sobrescrito_em_silencio(tmp_path):
    arquivo = tmp_path / "r.json"
    arquivo.write_text("{ quebrado", encoding="utf-8")
    with pytest.raises(rg.RegraInvalida):
        rg.carregar(arquivo)
    assert arquivo.read_text(encoding="utf-8") == "{ quebrado"


# --- Planilha ----------------------------------------------------------------------


def _itens(pasta, ano=2026, mes=10):
    c = varrer(criar_pasta_extratos(pasta))
    return [(l, rg.classificar(l, rg.REGRAS_PADRAO)) for l in c.do_mes(ano, mes)]


def test_nome_do_fechamento():
    assert fechamento.nome_sugerido(2026, 9) == "Fechamento - Setembro 2026.xlsx"


def test_fechamento_com_as_abas_e_operacao_em_branco(tmp_path):
    itens = _itens(tmp_path / "e")
    destino = fechamento.gerar(tmp_path / "f.xlsx", itens, [])
    wb = load_workbook(destino)
    assert wb.sheetnames == [ABA_EXTRATO, fechamento.ABA_NOTAS, ABA_RESUMO]

    ws = wb[ABA_EXTRATO]
    assert [c.value for c in ws[1]] == COLUNAS
    assert ws.max_row == len(itens) + 5  # cabeçalho + linhas + branco + 3 totais
    assert float(ws["B2"].value) == 180.0
    # Sem regra: fica em branco para preencher
    assert ws["C4"].value is None
    assert "DISTRIBUIDORA FICTICIA" in ws["D4"].value
    assert ws["C2"].value == "RECEBIMENTO DE PIX PACIENTE"


def test_fechamento_sem_pasta_de_notas_nao_tem_a_aba(tmp_path):
    wb = load_workbook(fechamento.gerar(tmp_path / "f.xlsx", _itens(tmp_path / "e"), None))
    assert fechamento.ABA_NOTAS not in wb.sheetnames


def test_nome_de_paciente_do_pix_nao_vai_para_a_planilha(tmp_path):
    itens = _itens(tmp_path / "e")
    ws = load_workbook(fechamento.gerar(tmp_path / "f.xlsx", itens, None))[ABA_EXTRATO]
    textos = " ".join(str(c.value) for r in ws.iter_rows() for c in r)
    assert "Paciente Ficticio" not in textos
    pix = linha(date(2026, 9, 1), "Pix recebido", "1", descricao="FULANO")
    assert descricao_para_planilha(pix) == "Pix recebido"
    enviado = linha(date(2026, 9, 1), "Pix enviado", "-1", descricao="LAB")
    assert descricao_para_planilha(enviado) == "Pix enviado: LAB"


def test_resumo_tem_saldos_e_uma_linha_por_operacao(tmp_path):
    itens = _itens(tmp_path / "e")
    ws = load_workbook(fechamento.gerar(tmp_path / "f.xlsx", itens, None))[ABA_RESUMO]
    rotulos = [r[0].value for r in ws.iter_rows()]
    assert "RECEBIMENTO DE PIX PACIENTE" in rotulos
    assert "Total de entradas" in rotulos and "Total de saídas" in rotulos
    linhas = {r[0].value: r[1].value for r in ws.iter_rows()}
    assert float(linhas["Saldo no início do mês"]) == 10459.75
    assert float(linhas["Saldo no fim do mês"]) == float(itens[-1][0].saldo)
