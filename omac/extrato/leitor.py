"""Leitura do extrato em PDF do Banco Inter.

O pdfium entrega um dia por bloco e cada lançamento em uma linha:

    1 de Setembro de 2026 Saldo do dia: R$ 1.000,00
    Pix recebido: "NOME" R$ 200,00 R$ 800,00
    Pix enviado: "Cp :00000000-NOME" -R$ 45,00 R$ 755,00
    SIMPLES NACIONAL -R$ 300,00 R$ 455,00

O último valor é o saldo depois do lançamento. Ele serve de conferência: se o
saldo anterior + o valor não der o saldo informado, alguma linha foi perdida.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..pdf import PdfIlegivel, extrair_paginas

_MESES = {m: i + 1 for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split()
)}
_VALOR = r"(-?)R\$\s*([\d.]+,\d{2})"

_RE_PERIODO = re.compile(r"Período:\s*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})")
_RE_SOLICITADO = re.compile(r"Solicitado em:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2})h(\d{2})")
_RE_DIA = re.compile(r"^(\d{1,2}) de (\S+) de (\d{4})\s+Saldo do dia:")
_RE_LANCAMENTO = re.compile(rf"^(?P<texto>.*?)\s*{_VALOR}\s+{_VALOR}$")
_RE_TEXTO = re.compile(r'^(?P<tipo>[^:"]+?):?\s*"(?P<descricao>.*)"$')
_RE_CONTA_PIX = re.compile(r"^Cp\s*:\s*\d+\s*-\s*")  # código do banco da outra conta


class ExtratoIlegivel(Exception):
    """O PDF não é um extrato do Banco Inter, ou não deu para ler."""


@dataclass
class Lancamento:
    data: date
    tipo: str  # "Pix recebido", "Pagamento efetuado", "SIMPLES NACIONAL"…
    descricao: str  # quem pagou ou recebeu, como aparece no banco
    valor: Decimal  # negativo nas saídas
    saldo: Decimal  # saldo depois do lançamento

    @property
    def sentido(self) -> str:
        return "saida" if self.valor < 0 else "entrada"


@dataclass
class Extrato:
    arquivo: str
    inicio: date
    fim: date
    solicitado_em: datetime
    lancamentos: list[Lancamento] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _decimal(sinal: str, numero: str) -> Decimal:
    valor = Decimal(numero.replace(".", "").replace(",", "."))
    return -valor if sinal else valor


def _dividir_texto(texto: str) -> tuple[str, str]:
    m = _RE_TEXTO.match(texto)
    if not m:
        return texto.strip(), ""
    return m["tipo"].strip(), _RE_CONTA_PIX.sub("", m["descricao"]).strip()


def interpretar_texto(texto: str, arquivo: str = "") -> Extrato:
    periodo = _RE_PERIODO.search(texto)
    if not periodo or "Banco Inter" not in texto:
        raise ExtratoIlegivel("não parece um extrato em PDF do Banco Inter")

    solicitado = _RE_SOLICITADO.search(texto)
    extrato = Extrato(
        arquivo=arquivo,
        inicio=datetime.strptime(periodo[1], "%d/%m/%Y").date(),
        fim=datetime.strptime(periodo[2], "%d/%m/%Y").date(),
        solicitado_em=(
            datetime.strptime(f"{solicitado[1]} {solicitado[2]}:{solicitado[3]}", "%d/%m/%Y %H:%M")
            if solicitado else datetime.min
        ),
    )

    dia: date | None = None
    for linha in texto.splitlines():
        linha = linha.strip()
        m = _RE_DIA.match(linha)
        if m:
            mes = _MESES.get(m[2].lower())
            if not mes:
                raise ExtratoIlegivel(f"mês desconhecido no extrato: {m[2]}")
            dia = date(int(m[3]), mes, int(m[1]))
            continue
        if dia is None:
            continue  # cabeçalho, antes do primeiro dia
        m = _RE_LANCAMENTO.match(linha)
        if m:
            tipo, descricao = _dividir_texto(m["texto"])
            grupos = m.groups()
            extrato.lancamentos.append(Lancamento(
                dia, tipo, descricao, _decimal(grupos[1], grupos[2]), _decimal(grupos[3], grupos[4])
            ))
        elif "R$" in linha:
            extrato.avisos.append(f"Linha que não consegui ler: {linha}")

    _conferir_saldos(extrato)
    return extrato


def _conferir_saldos(extrato: Extrato) -> None:
    for anterior, atual in zip(extrato.lancamentos, extrato.lancamentos[1:]):
        if anterior.saldo + atual.valor != atual.saldo:
            extrato.avisos.append(
                f"O saldo não fecha em {atual.data:%d/%m/%Y}: pode faltar lançamento na leitura."
            )
            return


def ler_extrato(caminho: Path) -> Extrato:
    caminho = Path(caminho)
    try:
        paginas = extrair_paginas(caminho)
    except PdfIlegivel as e:
        raise ExtratoIlegivel(str(e)) from e
    return interpretar_texto("\n".join(paginas), caminho.name)
