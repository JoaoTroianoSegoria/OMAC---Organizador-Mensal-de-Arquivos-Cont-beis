"""Parte da API que monta o resumo do ano.

Junta o que os outros módulos já leem (notas, extrato, ficha). Cada fonte que falhar
fica em branco no resumo, sem derrubar as outras.
"""

from __future__ import annotations

import traceback
from datetime import date

from ..atendimentos import ficha as fc
from ..dados import esquema
from ..extrato import exportar as extrato_exp
from ..nucleo import ApiBase, seguro
from . import ano as resumo


class ResumoApi(ApiBase):

    def _extrato_do_ano(self, ano: int) -> dict | None:
        """{mês: (entradas, saídas)} em centavos, só dos meses que aparecem nos extratos."""
        try:
            c = self._ler_extratos()
            if isinstance(c, dict):
                return None
            por_mes = {}
            for a, m, _ in c.meses():
                if a == ano:
                    t = extrato_exp.totais(c.do_mes(a, m))
                    por_mes[m] = (int(round(t["entradas"] * 100)), int(round(abs(t["saidas"]) * 100)))
            return por_mes
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return None

    def _ficha_do_ano(self, ano: int, hoje: date) -> dict:
        atendimentos = self._armazem.ler(esquema.ATENDIMENTOS)["atendimentos"]
        por_mes: dict[int, dict] = {}
        for a in atendimentos:
            if int(a["data"][:4]) != ano:
                continue
            m = por_mes.setdefault(int(a["data"][5:7]), {"recebido_centavos": 0, "pendente_centavos": 0, "qtd": 0})
            valor = a["valor_centavos"] or 0
            m["qtd"] += 1
            if fc.situacao(a, hoje) == fc.PAGO:
                m["recebido_centavos"] += valor
            else:
                m["pendente_centavos"] += valor
        return por_mes

    def _anos_com_dados(self, notas: list | None, hoje: date) -> list[int]:
        anos = {hoje.year} | {n.competencia.year for n in notas or []}
        anos |= {int(a["data"][:4]) for a in self._armazem.ler(esquema.ATENDIMENTOS)["atendimentos"]}
        return sorted(anos)

    @seguro
    def resumo_ano(self, ano: int):
        hoje = date.today()
        ano = int(ano)
        notas = self._servico_notas.todas()
        dados = resumo.montar(ano, hoje, notas, self._extrato_do_ano(ano), self._ficha_do_ano(ano, hoje))
        return {**dados, "anos": self._anos_com_dados(notas, hoje)}
