"""Estilo comum das planilhas geradas pelo OMAC."""

from __future__ import annotations

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
COR = "1F6F78"
MOEDA = '"R$" #,##0.00;[Red]-"R$" #,##0.00'
DATA = "DD/MM/YYYY"


def cabecalho(ws, colunas: list[str]) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill

    ws.append(colunas)
    fundo = PatternFill("solid", fgColor=COR)
    for c in ws[ws.max_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fundo
        c.alignment = Alignment(horizontal="center", vertical="center")


def larguras(ws, colunas: str, valores: tuple[int, ...]) -> None:
    for letra, largura in zip(colunas, valores):
        ws.column_dimensions[letra].width = largura


def linha_de_total(ws, linha: int, colunas: int) -> None:
    from openpyxl.styles import Border, Font, Side

    borda = Border(top=Side(style="medium", color=COR))
    for col in range(1, colunas + 1):
        c = ws.cell(linha, col)
        c.font = Font(bold=True)
        c.border = borda
