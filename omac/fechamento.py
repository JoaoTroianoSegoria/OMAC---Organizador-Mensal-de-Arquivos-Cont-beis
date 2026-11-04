"""Planilha do fechamento do mês, a que vai para a contabilidade."""

from __future__ import annotations

from pathlib import Path

from .extrato import exportar as extrato
from .extrato.leitor import Lancamento
from .notas import exportar as notas_exp
from .notas.leitor import Nota
from .planilha import MESES

ABA_NOTAS = "Notas Fiscais"


def nome_sugerido(ano: int, mes: int) -> str:
    return f"Fechamento - {MESES[mes - 1]} {ano}.xlsx"


def gerar(destino: Path, itens: list[tuple[Lancamento, str]], notas: list[Nota] | None) -> Path:
    """Abas: Extrato Banco, Notas Fiscais (se houver pasta de notas) e Resumo."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = extrato.ABA_EXTRATO
    extrato.preencher_extrato(ws, itens)
    if notas is not None:
        notas_exp.preencher_aba(wb.create_sheet(ABA_NOTAS), notas)
    extrato.preencher_resumo(wb.create_sheet(extrato.ABA_RESUMO), itens)
    destino = Path(destino)
    wb.save(destino)
    return destino
