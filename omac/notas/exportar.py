"""Gera a planilha do mês (XLSX ou CSV) com as notas por competência."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from ..planilha import DATA, MESES, MOEDA, cabecalho, larguras, linha_de_total
from .leitor import Nota

COLUNAS = ["Nº", "Paciente", "Valor", "Emissão", "Competência"]


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

    wb = Workbook()
    ws = wb.active
    ws.title = f"NFS-e {mes:02d}-{ano}"
    preencher_aba(ws, notas)
    wb.save(destino)


def preencher_aba(ws, notas: list[Nota]) -> None:
    """Escreve as notas em uma aba de planilha (também usada pelo fechamento do mês)."""
    from openpyxl.styles import Alignment

    cabecalho(ws, COLUNAS)
    for n in notas:
        ws.append([n.numero, n.paciente, n.valor, n.emissao, n.competencia])

    ultima = ws.max_row
    for linha in ws.iter_rows(min_row=2, max_row=ultima):
        linha[0].alignment = Alignment(horizontal="center")
        linha[2].number_format = MOEDA
        linha[3].number_format = DATA
        linha[4].number_format = DATA
        linha[3].alignment = linha[4].alignment = Alignment(horizontal="center")

    total = ultima + 1
    ws.cell(total, 2, f"TOTAL ({len(notas)} {'nota' if len(notas) == 1 else 'notas'})")
    ws.cell(total, 3, f"=SUM(C2:C{ultima})" if notas else Decimal("0"))
    ws.cell(total, 3).number_format = MOEDA
    linha_de_total(ws, total, len(COLUNAS))

    larguras(ws, "ABCDE", (10, 42, 16, 14, 14))
    ws.freeze_panes = "A2"
    if notas:
        ws.auto_filter.ref = f"A1:E{ultima}"
