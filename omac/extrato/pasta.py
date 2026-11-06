"""Junta os extratos de uma pasta em uma lista só de lançamentos.

Os extratos podem se sobrepor (ex.: 04/08 a 04/09 e 01/09 a 30/09). Cada dia vem
do extrato baixado por último, porque um extrato baixado no meio do dia traz o
dia pela metade. Os dias que nenhum extrato cobre são conferidos pelo saldo.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from .leitor import Extrato, ExtratoIlegivel, Lancamento, ler_extrato


@dataclass
class Consolidado:
    extratos: list[Extrato] = field(default_factory=list)
    lancamentos: list[Lancamento] = field(default_factory=list)
    avisos: list[dict] = field(default_factory=list)  # PDFs que não deu para ler
    _fonte: dict[date, Extrato] = field(default_factory=dict)  # dia → extrato usado

    def do_mes(self, ano: int, mes: int) -> list[Lancamento]:
        return [l for l in self.lancamentos if l.data.year == ano and l.data.month == mes]

    def meses(self) -> list[tuple[int, int, int]]:
        """(ano, mês, quantidade de lançamentos) de cada mês encontrado."""
        qtd = Counter((l.data.year, l.data.month) for l in self.lancamentos)
        return [(ano, mes, q) for (ano, mes), q in sorted(qtd.items())]

    def avisos_do_mes(self, ano: int, mes: int, hoje: date | None = None) -> list[dict]:
        dias = _dias_do_mes(ano, mes, hoje or date.today())
        if not any(d in self._fonte for d in dias):
            return []

        avisos = []
        for inicio, fim in _intervalos([d for d in dias if d not in self._fonte]):
            avisos.append({"arquivo": "", "mensagem": self._mensagem_de_falta(inicio, fim)})
        avisos = [a for a in avisos if a["mensagem"]]

        usados = {id(self._fonte[d]): self._fonte[d] for d in dias if d in self._fonte}
        for e in usados.values():
            avisos.extend({"arquivo": e.arquivo, "mensagem": m} for m in e.avisos)
            baixado = e.solicitado_em.date()
            if baixado in dias and self._fonte.get(baixado) is e:
                avisos.append({
                    "arquivo": e.arquivo,
                    "mensagem": f"Foi baixado no próprio dia {baixado:%d/%m/%Y}, então esse dia pode "
                                "estar incompleto. Baixe o extrato de novo depois que o dia acabar.",
                })
        return avisos

    def _mensagem_de_falta(self, inicio: date, fim: date) -> str:
        periodo = f"{inicio:%d/%m/%Y}" if inicio == fim else f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"
        antes = next((l.saldo for l in reversed(self.lancamentos) if l.data < inicio), None)
        depois = next((l.saldo - l.valor for l in self.lancamentos if l.data > fim), None)
        if antes is None or depois is None:
            return f"Nenhum extrato da pasta cobre {periodo}. Pode faltar lançamento."
        if antes == depois:
            return ""  # o saldo não mudou: não houve movimento nesses dias
        return (f"Nenhum extrato da pasta cobre {periodo}, e o saldo mudou "
                f"{_real(depois - antes)} nesse período. Baixe o extrato desses dias.")


def _real(v: Decimal) -> str:
    inteiro, centavos = f"{abs(v):.2f}".split(".")
    return ("-" if v < 0 else "") + f"R$ {int(inteiro):,}".replace(",", ".") + f",{centavos}"


def _dias_do_mes(ano: int, mes: int, hoje: date) -> list[date]:
    dia = date(ano, mes, 1)
    dias = []
    while dia.month == mes and dia <= hoje:
        dias.append(dia)
        dia += timedelta(days=1)
    return dias


def _intervalos(dias: list[date]) -> list[tuple[date, date]]:
    """[01, 02, 03, 07] → [(01, 03), (07, 07)]"""
    grupos: list[tuple[date, date]] = []
    for d in dias:
        if grupos and grupos[-1][1] + timedelta(days=1) == d:
            grupos[-1] = (grupos[-1][0], d)
        else:
            grupos.append((d, d))
    return grupos


def consolidar(extratos: list[Extrato]) -> Consolidado:
    c = Consolidado(extratos=sorted(extratos, key=lambda e: e.solicitado_em))
    for e in c.extratos:  # o mais recente fica por último e sobrescreve
        baixado = e.solicitado_em.date()
        dia = e.inicio
        while dia <= e.fim and (dia <= baixado or e.solicitado_em == datetime.min):
            c._fonte[dia] = e
            dia += timedelta(days=1)
    for e in c.extratos:
        c.lancamentos.extend(l for l in e.lancamentos if c._fonte.get(l.data) is e)
    c.lancamentos.sort(key=lambda l: l.data)  # estável: mantém a ordem do banco dentro do dia
    return c


def varrer(pasta: Path) -> Consolidado:
    """Lê os PDFs que estão direto na pasta. Arquivo que não é extrato vira aviso."""
    extratos, avisos = [], []
    for arquivo in sorted(Path(pasta).glob("*")):
        if arquivo.suffix.lower() != ".pdf" or not arquivo.is_file():
            continue
        try:
            extratos.append(ler_extrato(arquivo))
        except ExtratoIlegivel as e:
            avisos.append({"arquivo": arquivo.name, "mensagem": f"Ficou de fora: {e}."})
        except (ValueError, ArithmeticError, OSError) as e:
            # Data ou valor impossível no PDF: perde este arquivo, não a tela inteira.
            avisos.append({"arquivo": arquivo.name, "mensagem": f"Ficou de fora: não consegui entender o PDF ({e})."})
    c = consolidar(extratos)
    c.avisos = avisos
    return c
