"""Gera a planilha do mês (XLSX ou CSV) com as notas por competência."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from .leitor import Nota

COLUNAS = ["Nº", "Paciente", "Valor", "Emissão", "Competência"]
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def nome_sugerido(ano: int, mes: int, formato: str) -> str:
    return f"Notas fiscais - {MESES[mes - 1]} {ano}.{formato}"


def exportar(notas: list[Nota], destino: Path, ano: int, mes: int) -> Path:
    destino = Path(destino)
    if destino.suffix.lower() == ".csv":
        _csv(notas, destino)
    else:
        destino = destino.with_suffix(".xlsx")
        _xlsx(notas, destino, ano, mes)
    return destino


def _csv(notas: list[Nota], destino: Path) -> None:
    # Ponto e vírgula + UTF-8 com BOM: abre certinho no Excel em português.
    with destino.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(COLUNAS)
        for n in notas:
            w.writerow([
                n.numero,
                n.paciente,
                f"{n.valor:.2f}".replace(".", ","),
                n.emissao.strftime("%d/%m/%Y"),
                n.competencia.strftime("%d/%m/%Y"),
            ])


def _xlsx(notas: list[Nota], destino: Path, ano: int, mes: int) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = f"NFS-e {mes:02d}-{ano}"

    ws.append(COLUNAS)
    cabecalho = PatternFill("solid", fgColor="1F6F78")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = cabecalho
        c.alignment = Alignment(horizontal="center", vertical="center")

    for n in notas:
        ws.append([n.numero, n.paciente, n.valor, n.emissao, n.competencia])

    ultima = ws.max_row
    for linha in ws.iter_rows(min_row=2, max_row=ultima):
        linha[0].alignment = Alignment(horizontal="center")
        linha[2].number_format = '"R$" #,##0.00'
        linha[3].number_format = "DD/MM/YYYY"
        linha[4].number_format = "DD/MM/YYYY"
        linha[3].alignment = linha[4].alignment = Alignment(horizontal="center")

    total = ultima + 1
    ws.cell(total, 2, f"TOTAL ({len(notas)} {'nota' if len(notas) == 1 else 'notas'})")
    ws.cell(total, 3, f"=SUM(C2:C{ultima})" if notas else Decimal("0"))
    ws.cell(total, 3).number_format = '"R$" #,##0.00'
    borda = Border(top=Side(style="medium", color="1F6F78"))
    for col in range(1, 6):
        c = ws.cell(total, col)
        c.font = Font(bold=True)
        c.border = borda

    for letra, largura in zip("ABCDE", (10, 42, 16, 14, 14)):
        ws.column_dimensions[letra].width = largura
    ws.freeze_panes = "A2"
    if notas:
        ws.auto_filter.ref = f"A1:E{ultima}"

    wb.save(destino)
