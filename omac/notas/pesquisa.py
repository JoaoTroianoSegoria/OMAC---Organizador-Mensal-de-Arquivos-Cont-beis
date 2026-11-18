"""Pesquisa de notas: um campo só (nome, dependente, número, valor ou data) e o período.

Cada palavra digitada precisa aparecer na nota (Maria 150 = notas da Maria de R$ 150).
O período vale pela data de competência, como o relatório.
"""

from __future__ import annotations

import re
from datetime import date

from ..texto import normalizar
from .leitor import Nota, responsavel

# Até onde o texto pode ser um número, um valor ou uma data.
_RE_NUMERICO = re.compile(r"[\d.,/]+")
_RE_DATA = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?$")
_RE_MES_ANO = re.compile(r"(\d{1,2})/(\d{4})$")


def _valores(nota: Nota) -> set[str]:
    """O valor como as pessoas costumam digitar: 1500 · 1500,00 · 1.500,00 · 1500,5."""
    centavos = int(nota.valor * 100)
    reais, cent = divmod(centavos, 100)
    com_ponto = f"{reais:,}".replace(",", ".")
    formas = {f"{reais},{cent:02d}", f"{com_ponto},{cent:02d}"}
    if cent == 0:
        formas |= {str(reais), com_ponto}
    elif cent % 10 == 0:
        formas |= {f"{reais},{cent // 10}", f"{com_ponto},{cent // 10}"}
    return formas


def _bate_data(termo: str, nota: Nota) -> bool:
    datas = (nota.emissao, nota.competencia)
    if m := _RE_MES_ANO.fullmatch(termo):
        mes, ano = int(m.group(1)), int(m.group(2))
        return any(d.month == mes and d.year == ano for d in datas)
    if m := _RE_DATA.fullmatch(termo):
        dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
        ano_n = None if ano is None else int(ano) + (2000 if len(ano) == 2 else 0)
        return any(d.day == dia and d.month == mes and (ano_n is None or d.year == ano_n) for d in datas)
    return False


def _bate(termo: str, nota: Nota, nomes: str) -> bool:
    if not _RE_NUMERICO.fullmatch(termo):
        return termo in nomes
    if "/" in termo:
        return _bate_data(termo, nota)
    if termo.isdigit() and int(termo) == nota.numero:
        return True
    return termo in _valores(nota)


def termos(texto: str) -> list[str]:
    """As palavras da pesquisa, sem acento e sem "R$"."""
    texto = re.sub(r"(?i)r\$", " ", texto or "")
    return normalizar(texto).split()


def filtrar(notas: list[Nota], texto: str = "", de: date | None = None, ate: date | None = None) -> list[Nota]:
    """As notas do período (competência, com as pontas) em que aparecem todas as palavras."""
    procurados = termos(texto)
    achadas = []
    for n in notas:
        if (de and n.competencia < de) or (ate and n.competencia > ate):
            continue
        nomes = normalizar(f"{n.paciente} {responsavel(n)}")
        if all(_bate(t, n, nomes) for t in procurados):
            achadas.append(n)
    return sorted(achadas, key=lambda n: n.numero)
