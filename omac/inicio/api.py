"""Parte da API que monta o Início.

O Início não conhece os módulos: percorre o registro de widgets (registro.py), e cada
módulo marca com `@widget` o método que monta os dados do seu. Um widget que falhar
mostra o erro sozinho, sem derrubar os outros.
"""

from __future__ import annotations

import traceback
from datetime import date, timedelta

from ..backup import backup as bk
from ..nucleo import ApiBase, seguro
from ..planilha import MESES
from ..resumo import ano as resumo
from . import registro
from .registro import widget


class InicioApi(ApiBase):
    @widget("hoje", "Hoje", ordem=10, largo=True)
    def _widget_hoje(self, hoje: date) -> dict:
        """O resto do "Hoje" sai dos outros widgets; aqui fica o aviso do backup."""
        cfg = self._cfg
        dias = bk.dias_desde(cfg, hoje)
        return {"backup": {
            "pasta": bool(cfg["backup_pasta"]),
            "automatico": cfg["backup_automatico"],
            "dias": dias,
            "erro": cfg["backup_erro"],
            # Sem backup há mais de um mês (ou nunca): vale lembrar, mesmo sem o automático.
            "atrasado": dias is None or dias > 31,
        }}

    @widget("relatorio", "Relatório mensal", ordem=50)
    def _widget_relatorio(self, hoje: date) -> dict:
        anterior = hoje.replace(day=1) - timedelta(days=1)
        notas = self._servico_notas.do_mes(anterior.year, anterior.month)
        c = self._ler_extratos()
        return {
            "ano": anterior.year,
            "mes": anterior.month,
            "nome_mes": MESES[anterior.month - 1],
            "notas": None if notas is None else len(notas),
            "lancamentos": None if isinstance(c, dict) else len(c.do_mes(anterior.year, anterior.month)),
            "dia_lembrete": self._cfg["lembrete_fechamento_dia"],
        }

    @widget("resumo", "Resumo do ano", ordem=70, largo=True)
    def _widget_resumo(self, hoje: date) -> dict:
        dados = resumo.montar(hoje.year, hoje, self._servico_notas.todas(), None, {})
        return {k: dados[k] for k in ("ano", "faturamento_centavos", "media_centavos", "melhor", "notas_lidas")} | {
            "meses": [{"mes": m["mes"], "nome": m["nome"], "faturamento_centavos": m["faturamento_centavos"]}
                      for m in dados["meses"]],
        }

    @seguro
    def inicio_painel(self):
        hoje = date.today()
        widgets = {}
        for w in registro.em_ordem():
            try:
                widgets[w.id] = getattr(self, w.metodo)(hoje)
            except Exception as e:  # noqa: BLE001 — um widget com problema não apaga os outros
                traceback.print_exc()
                widgets[w.id] = {"erro": str(e) or e.__class__.__name__}
        return {"data": hoje.isoformat(), "cartoes": registro.cartoes(self._cfg["inicio_cartoes"]),
                "titulos": {w.id: w.titulo for w in registro.em_ordem()}, "widgets": widgets}
