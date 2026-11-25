"""Planilha da ficha do mês, com as mesmas colunas do papel, pronta para imprimir."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from ..planilha import DATA, MESES, MOEDA, cabecalho, larguras, linha_de_total
from . import ficha as fc

COLUNAS = ["Paciente", "Tratamento", "Data", "Valor", "Forma de pag.", "Dividido", "Pago", "Nota"]
PAGO_POR_EXTENSO = {fc.PAGO: "Sim", fc.AGUARDANDO: "", fc.NAO_PAGO: "Não"}
NOTA_POR_EXTENSO = {fc.NOTA_OK: "ok", fc.NOTA_NAO_PRECISA: "não precisa", fc.FALTA: ""}


def nome_sugerido(ano: int, mes: int, lista: str = "") -> str:
    """Com mais de uma lista, o nome dela vai junto: "Atendimentos - Novembro 2026 - Brasília.xlsx"."""
    fim = f" - {_sem_proibidos(lista)}" if lista.strip() else ""
    return f"Atendimentos - {MESES[mes - 1]} {ano}{fim}.xlsx"


def _sem_proibidos(nome: str) -> str:
    """Tira o que o Windows não aceita em nome de arquivo."""
    return "".join(c for c in nome if c not in '\\/:*?"<>|').strip()


def _dividido(a: dict) -> str:
    if a["forma"] != "credito":
        return ""
    return f"{a['parcelas']}x" if a["parcelas"] > 1 else "à vista"


def exportar(lista: list[dict], destino: Path, ano: int, mes: int, nome_lista: str = "") -> Path:
    """`lista` vem da API: cada atendimento já tem "nome", "situacao" e "nota_situacao".
    `nome_lista` (com mais de uma lista) sai no alto de cada folha impressa."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment

    wb = Workbook()
    ws = wb.active
    ws.title = f"Atendimentos {mes:02d}-{ano}"
    cabecalho(ws, COLUNAS)
    for a in lista:
        valor = Decimal(a["valor_centavos"]) / 100 if a["valor_centavos"] is not None else None
        ws.append([
            a["nome"], a["tratamento"], date.fromisoformat(a["data"]), valor,
            fc.FORMAS.get(a["forma"], ""), _dividido(a), PAGO_POR_EXTENSO[a["situacao"]],
            NOTA_POR_EXTENSO[a["nota_situacao"]],
        ])

    ultima = ws.max_row
    for linha in ws.iter_rows(min_row=2, max_row=ultima):
        linha[2].number_format = DATA
        linha[3].number_format = MOEDA
        for c in linha[2:3] + linha[5:8]:
            c.alignment = Alignment(horizontal="center")

    total = ultima + 1
    ws.cell(total, 1, f"TOTAL ({len(lista)} {'atendimento' if len(lista) == 1 else 'atendimentos'})")
    ws.cell(total, 4, f"=SUM(D2:D{ultima})" if lista else Decimal("0"))
    ws.cell(total, 4).number_format = MOEDA
    linha_de_total(ws, total, len(COLUNAS))

    larguras(ws, "ABCDEFGH", (34, 20, 12, 14, 15, 10, 8, 12))
    ws.freeze_panes = "A2"
    # Cabe numa folha deitada, como o papel.
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "1:1"
    if nome_lista.strip():
        # "&" é código no cabeçalho do Excel: "&&" escreve um "&".
        ws.oddHeader.center.text = f"Atendimentos de {MESES[mes - 1]} de {ano} - {nome_lista.strip()}".replace("&", "&&")
    destino = Path(destino).with_suffix(".xlsx")
    wb.save(destino)
    return destino
