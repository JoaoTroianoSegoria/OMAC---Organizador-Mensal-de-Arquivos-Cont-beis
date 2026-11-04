"""Escreve as abas do extrato: lançamentos do mês e resumo por operação."""

from __future__ import annotations

from decimal import Decimal

from ..planilha import DATA, MOEDA, cabecalho, larguras, linha_de_total
from .leitor import Lancamento

ABA_EXTRATO = "Extrato Banco"
ABA_RESUMO = "Resumo"
COLUNAS = ["Data", "Valor", "Operação", "Descrição no banco", "Saldo"]
SEM_OPERACAO = "Sem operação preenchida"


def descricao_para_planilha(l: Lancamento) -> str:
    """O nome de quem mandou Pix é dado de paciente: não vai para a contabilidade."""
    if l.tipo.lower() == "pix recebido":
        return l.tipo
    return f"{l.tipo}: {l.descricao}" if l.descricao else l.tipo


def preencher_extrato(ws, itens: list[tuple[Lancamento, str]]) -> None:
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, PatternFill

    cabecalho(ws, COLUNAS)
    for l, operacao in itens:
        ws.append([l.data, l.valor, operacao or None, descricao_para_planilha(l), l.saldo])

    ultima = ws.max_row
    for linha in ws.iter_rows(min_row=2, max_row=ultima):
        linha[0].number_format = DATA
        linha[0].alignment = Alignment(horizontal="center")
        linha[1].number_format = MOEDA
        linha[4].number_format = MOEDA

    if itens:
        # Amarelo só enquanto estiver vazio: some quando a operação é digitada.
        ws.conditional_formatting.add(
            f"C2:C{ultima}",
            FormulaRule(formula=["ISBLANK(C2)"], fill=PatternFill(bgColor="FFF2B3")),
        )
        ws.auto_filter.ref = f"A1:E{ultima}"
        valores = f"B2:B{ultima}"
        for i, (rotulo, formula) in enumerate((
            ("TOTAL DE ENTRADAS", f'=SUMIF({valores},">0")'),
            ("TOTAL DE SAÍDAS", f'=SUMIF({valores},"<0")'),
            ("RESULTADO DO MÊS", f"=SUM({valores})"),
        )):
            linha = ultima + 2 + i
            ws.cell(linha, 2, formula).number_format = MOEDA
            ws.cell(linha, 3, rotulo)
            linha_de_total(ws, linha, len(COLUNAS))

    larguras(ws, "ABCDE", (13, 16, 52, 58, 16))
    ws.freeze_panes = "A2"


def preencher_resumo(ws, itens: list[tuple[Lancamento, str]]) -> None:
    """Total de cada operação. São fórmulas: o que for digitado depois entra na conta."""
    from openpyxl.styles import Font

    ultima = len(itens) + 1
    valores = f"'{ABA_EXTRATO}'!$B$2:$B${ultima}"
    operacoes = f"'{ABA_EXTRATO}'!$C$2:$C${ultima}"
    negrito = Font(bold=True)

    cabecalho(ws, ["Resumo do mês", "Valor"])

    def linha(rotulo: str, valor, forte: bool = False) -> int:
        ws.append([rotulo, valor])
        n = ws.max_row
        ws.cell(n, 2).number_format = MOEDA
        if forte:
            ws.cell(n, 1).font = negrito
            ws.cell(n, 2).font = negrito
        return n

    primeiro = itens[0][0]
    linha("Saldo no início do mês", primeiro.saldo - primeiro.valor)

    totais = []
    for titulo, sentido, comparacao in (("Entradas", "entrada", ">0"), ("Saídas", "saida", "<0")):
        ws.append([])
        linha(titulo, None, forte=True)
        nomes = sorted({op for l, op in itens if op and l.sentido == sentido})
        inicio = ws.max_row + 1
        for nome in nomes:
            n = ws.max_row + 1
            linha(nome, f'=SUMIFS({valores},{operacoes},A{n},{valores},"{comparacao}")')
        fim = ws.max_row
        # Total calculado direto dos lançamentos; a diferença é o que falta preencher.
        total = f'SUMIF({valores},"{comparacao}")'
        listados = f"SUM(B{inicio}:B{fim})" if nomes else "0"
        linha(f"{SEM_OPERACAO} ou digitada depois", f"={total}-{listados}")
        totais.append(linha(f"Total de {titulo.lower()}", f"={total}", forte=True))

    ws.append([])
    linha("Resultado do mês", f"=B{totais[0]}+B{totais[1]}", forte=True)
    linha("Saldo no fim do mês", itens[-1][0].saldo, forte=True)

    larguras(ws, "AB", (58, 18))
    ws.freeze_panes = "A2"


def totais(lancamentos: list[Lancamento]) -> dict[str, Decimal]:
    return {
        "entradas": sum((l.valor for l in lancamentos if l.valor > 0), Decimal("0")),
        "saidas": sum((l.valor for l in lancamentos if l.valor < 0), Decimal("0")),
    }
