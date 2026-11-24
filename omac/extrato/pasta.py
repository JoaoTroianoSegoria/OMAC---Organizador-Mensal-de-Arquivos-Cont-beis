"""Junta os extratos de uma pasta em uma lista só de lançamentos.

Os extratos podem se sobrepor (ex.: 04/08 a 04/09 e 01/09 a 30/09). Cada dia vem
do extrato baixado por último, porque um extrato baixado no meio do dia traz o
dia pela metade. Os dias que nenhum extrato cobre são conferidos pelo saldo.
"""

from __future__ import annotations

import copy
import json
import threading
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


# Leitura de cada PDF guardada na memória enquanto o app está aberto: o Início e o Relatório
# pedem os extratos a cada visita, e ler os PDFs de novo era o que fazia o Início demorar.
# Muda o tamanho ou a data do arquivo: lê de novo. Quem usa recebe uma cópia (nada vaza entre leituras).
# Desde a 1.11.0 a leitura também fica num arquivo (`cache`), para a primeira abertura do dia
# não precisar abrir os PDFs. Ele é descartável: estragado, de outra versão ou apagado, lê tudo.
_MEMORIA: dict[str, tuple[tuple[int, int], Extrato]] = {}
_TRAVA = threading.Lock()  # a leitura ao abrir o app (em segundo plano) e a da tela não se atropelam
_CACHE_LIDO: set[str] = set()
_CHAVES_SALVAS: dict[str, list[str]] = {}  # cache → PDFs que estão nele
VERSAO_CACHE = 1  # mude quando a leitura do extrato mudar: o cache antigo é ignorado


def _para_dict(e: Extrato) -> dict:
    return {
        "arquivo": e.arquivo, "inicio": e.inicio.isoformat(), "fim": e.fim.isoformat(),
        "solicitado_em": e.solicitado_em.isoformat(), "avisos": list(e.avisos),
        "lancamentos": [[l.data.isoformat(), l.tipo, l.descricao, str(l.valor), str(l.saldo)] for l in e.lancamentos],
    }


def _de_dict(d: dict) -> Extrato:
    return Extrato(
        arquivo=d["arquivo"], inicio=date.fromisoformat(d["inicio"]), fim=date.fromisoformat(d["fim"]),
        solicitado_em=datetime.fromisoformat(d["solicitado_em"]), avisos=list(d["avisos"]),
        lancamentos=[Lancamento(date.fromisoformat(dt), tipo, desc, Decimal(v), Decimal(s))
                     for dt, tipo, desc, v, s in d["lancamentos"]],
    )


def _carregar_cache(cache: Path) -> None:
    """Põe na memória o que o arquivo tem (uma vez por arquivo de cache)."""
    if str(cache) in _CACHE_LIDO:
        return
    _CACHE_LIDO.add(str(cache))
    try:
        dados = json.loads(cache.read_text(encoding="utf-8"))
        if dados.get("versao") != VERSAO_CACHE:
            return
        for chave, item in dados.get("itens", {}).items():
            _MEMORIA.setdefault(chave, (tuple(item["marca"]), _de_dict(item["extrato"])))
        _CHAVES_SALVAS[str(cache)] = sorted(dados.get("itens", {}))
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
        pass  # sem cache ou estragado: lê os PDFs


def _salvar_cache(cache: Path, chaves: list[str]) -> None:
    """Guarda só os PDFs que estão na pasta agora (o que saiu da pasta sai do cache)."""
    itens = {c: {"marca": list(_MEMORIA[c][0]), "extrato": _para_dict(_MEMORIA[c][1])} for c in chaves if c in _MEMORIA}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(".tmp")
        tmp.write_text(json.dumps({"versao": VERSAO_CACHE, "itens": itens}), encoding="utf-8")
        tmp.replace(cache)
        _CHAVES_SALVAS[str(cache)] = sorted(itens)
    except OSError:
        pass  # sem cache em disco o app funciona igual, só abre mais devagar


def _ler_guardado(arquivo: Path) -> tuple[Extrato, bool]:
    """O extrato (uma cópia) e se precisou abrir o PDF."""
    st = arquivo.stat()
    marca = (st.st_size, st.st_mtime_ns)
    chave = str(arquivo.resolve())
    guardado = _MEMORIA.get(chave)
    lido = guardado is None or guardado[0] != marca
    if lido:
        guardado = (marca, ler_extrato(arquivo))
        _MEMORIA[chave] = guardado
    return copy.deepcopy(guardado[1]), lido


def varrer(pasta: Path, cache: Path | None = None) -> Consolidado:
    """Lê os PDFs que estão direto na pasta. Arquivo que não é extrato vira aviso."""
    with _TRAVA:
        if cache is not None:
            _carregar_cache(cache)
        extratos, avisos, chaves, leu_algum = [], [], [], False
        for arquivo in sorted(Path(pasta).glob("*")):
            if arquivo.suffix.lower() != ".pdf" or not arquivo.is_file():
                continue
            try:
                extrato, lido = _ler_guardado(arquivo)
                extratos.append(extrato)
                chaves.append(str(arquivo.resolve()))
                leu_algum |= lido
            except ExtratoIlegivel as e:
                avisos.append({"arquivo": arquivo.name, "mensagem": f"Ficou de fora: {e}."})
            except (ValueError, ArithmeticError, OSError) as e:
                # Data ou valor impossível no PDF: perde este arquivo, não a tela inteira.
                avisos.append({"arquivo": arquivo.name, "mensagem": f"Ficou de fora: não consegui entender o PDF ({e})."})
        if cache is not None and (leu_algum or _CHAVES_SALVAS.get(str(cache)) != sorted(chaves)):
            _salvar_cache(cache, chaves)
    c = consolidar(extratos)
    c.avisos = avisos
    return c
