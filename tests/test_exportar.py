from datetime import date, datetime
from decimal import Decimal

from openpyxl import load_workbook

from omac.notas.exportar import COLUNAS, exportar, nome_sugerido
from omac.notas.leitor import Nota
from omac.planilha import MOEDA


def notas():
    return [
        Nota(801, "ANA EXEMPLO", Decimal("350.00"), date(2026, 10, 1), date(2026, 10, 1), "a.pdf"),
        Nota(802, "JOSÉ ÇÃO", Decimal("1234.56"), date(2026, 11, 3), date(2026, 10, 31), "b.pdf"),
    ]


def test_nome_sugerido():
    assert nome_sugerido(2026, 10, "xlsx") == "Notas fiscais - Outubro 2026.xlsx"


def test_xlsx(tmp_path):
    destino = exportar(notas(), tmp_path / "saida.xlsx", 2026, 10)
    ws = load_workbook(destino).active
    linhas = list(ws.iter_rows(values_only=True))
    assert list(linhas[0]) == COLUNAS
    assert linhas[1][:2] == (801, "ANA EXEMPLO")
    assert linhas[2][2] == 1234.56
    assert linhas[2][3] == datetime(2026, 11, 3)
    assert linhas[2][4] == datetime(2026, 10, 31)
    assert linhas[3][1] == "TOTAL (2 notas)"
    assert linhas[3][2] == "=SUM(C2:C3)"
    assert ws["C2"].number_format == MOEDA
    assert ws["D2"].number_format == "DD/MM/YYYY"


def test_xlsx_vazio(tmp_path):
    ws = load_workbook(exportar([], tmp_path / "vazio.xlsx", 2026, 10)).active
    assert ws.max_row == 2
    assert ws["B2"].value == "TOTAL (0 notas)"


def test_csv(tmp_path):
    destino = exportar(notas(), tmp_path / "saida.csv", 2026, 10)
    conteudo = destino.read_text(encoding="utf-8-sig").splitlines()
    assert conteudo[0] == "Nº;Paciente;Valor;Emissão;Competência"
    assert conteudo[2] == "802;JOSÉ ÇÃO;1234,56;03/11/2026;31/10/2026"
    assert destino.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM: acentos certos no Excel
