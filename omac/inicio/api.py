"""Parte da API que monta a tela inicial.

É a única parte que junta todos os módulos: cada cartão lê o que o módulo dele já
sabe. Um cartão que falhar mostra o erro sozinho, sem derrubar os outros.
"""

from __future__ import annotations

import traceback
from datetime import date, timedelta

from ..agendamentos import pacientes as pc
from ..nucleo import ApiBase, seguro
from ..pagamentos import ficha as fc
from ..planilha import MESES
from ..resumo import ano as resumo
from ..whatsapp import lembretes as lb


def _mes_anterior(hoje: date) -> date:
    return hoje.replace(day=1) - timedelta(days=1)


class InicioApi(ApiBase):
    def _cartao_contas(self, hoje: date) -> dict:
        with self._dados() as d:
            contas = d["contas"]
        anterior = _mes_anterior(hoje)
        abertas = []
        for c in contas:
            if lb.situacao_no_mes(c, hoje.year, hoje.month, hoje) == lb.PAGA:
                continue
            vencimento = lb.vencimento_no_mes(c, hoje.year, hoje.month)
            abertas.append({
                "nome": c["nome"],
                "mes": f"{hoje:%Y-%m}",
                "vencimento": vencimento.isoformat(),
                "venceu": vencimento < hoje,
                "perto": vencimento <= hoje + timedelta(days=1),
            })
        abertas.sort(key=lambda c: c["vencimento"])
        return {
            "abertas": abertas,
            "total": len(contas),
            "nao_pagas_mes_passado": [c["nome"] for c in contas
                                      if lb.situacao_no_mes(c, anterior.year, anterior.month, hoje) == lb.NAO_PAGA],
        }

    def _cartao_ficha(self, hoje: date) -> dict:
        anterior = _mes_anterior(hoje)
        with self._ficha() as d:
            lista = self._vista_ficha(d, hoje.year, hoje.month, self._notas_do_mes(hoje.year, hoje.month))
            mes_passado = [a for a in fc.do_mes(d["atendimentos"], anterior.year, anterior.month)
                           if fc.situacao(a, hoje) == fc.NAO_PAGO]
        return {**fc.totais(lista), "qtd": len(lista), "nao_pagos_mes_passado": len(mes_passado)}

    def _cartao_orto(self, hoje: date) -> dict:
        anterior = _mes_anterior(hoje)
        with self._agenda() as d:
            pacientes = list(d["pacientes"])
        ativos = [p for p in pacientes if pc.situacao(p) == pc.ATIVO]
        altas = [p for p in pacientes if pc.situacao(p) == pc.ALTA]
        semana = (hoje + timedelta(days=7)).isoformat()
        return {
            "ativos": len(ativos),
            "agendados": sum(pc.agendado_no_mes(p, hoje) for p in ativos),
            "atendidos": sum(pc.atendido_no_mes(p, hoje) for p in ativos),
            "altas_terminadas": sum(pc.alta_terminou(p, hoje) for p in altas),
            "altas_acabando": [{"nome": p["nome"], "alta_fim": p["alta_fim"]} for p in sorted(altas, key=lambda p: p["alta_fim"])
                               if hoje.isoformat() <= p["alta_fim"] <= semana],
            "nao_vieram_mes_passado": sum(pc.situacao_no_mes(p, anterior.year, anterior.month, hoje) == pc.NAO_VEIO
                                          for p in pacientes),
        }

    def _cartao_notas_enviar(self) -> dict:
        r = self.whatsapp_a_enviar()
        if r.get("sem_pasta"):
            return {"sem_pasta": True}
        if "erro" in r:
            return {"erro": r["erro"]}
        return {"qtd": len(r["notas"])}

    def _cartao_fechamento(self, hoje: date) -> dict:
        anterior = _mes_anterior(hoje)
        notas = self._notas_do_mes(anterior.year, anterior.month)
        lancamentos = None
        c = self._ler_extratos()
        if not isinstance(c, dict):
            lancamentos = len(c.do_mes(anterior.year, anterior.month))
        return {
            "ano": anterior.year,
            "mes": anterior.month,
            "nome_mes": MESES[anterior.month - 1],
            "notas": None if notas is None else len(notas),
            "lancamentos": lancamentos,
            "dia_lembrete": self._cfg["lembrete_fechamento_dia"],
        }

    def _cartao_resumo(self, hoje: date) -> dict:
        dados = resumo.montar(hoje.year, hoje, self._todas_as_notas(), None, {})
        return {k: dados[k] for k in ("ano", "faturamento_centavos", "media_centavos", "melhor", "notas_lidas")} | {
            "meses": [{"mes": m["mes"], "nome": m["nome"], "faturamento_centavos": m["faturamento_centavos"]}
                      for m in dados["meses"]],
        }

    @seguro
    def inicio_painel(self):
        hoje = date.today()
        cartoes = {
            "contas": lambda: self._cartao_contas(hoje),
            "ficha": lambda: self._cartao_ficha(hoje),
            "orto": lambda: self._cartao_orto(hoje),
            "notas_enviar": self._cartao_notas_enviar,
            "fechamento": lambda: self._cartao_fechamento(hoje),
            "resumo": lambda: self._cartao_resumo(hoje),
        }
        painel = {"hoje": hoje.isoformat()}
        for nome, montar in cartoes.items():
            try:
                painel[nome] = montar()
            except Exception as e:  # noqa: BLE001 — um cartão com problema não apaga os outros
                traceback.print_exc()
                painel[nome] = {"erro": str(e) or e.__class__.__name__}
        return painel
