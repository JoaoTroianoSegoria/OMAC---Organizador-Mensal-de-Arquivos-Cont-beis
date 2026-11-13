"""Parte da API que cuida da ficha de pagamentos."""

from __future__ import annotations

import json
import threading
import traceback
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from .. import config
from ..armazem import DadosIlegiveis, carregar_json, salvar_json
from ..nucleo import ApiBase, seguro
from . import exportar as exp
from . import ficha as fc

PADRAO = {"atendimentos": []}


class PagamentosApi(ApiBase):
    def __init__(self):
        super().__init__()
        self._trava_ficha = threading.Lock()

    @contextmanager
    def _ficha(self):
        with self._trava_ficha:
            caminho = config.caminho_pagamentos()
            dados = carregar_json(caminho, PADRAO, "Os atendimentos da ficha")
            dados["atendimentos"] = [fc.completar(a) for a in dados["atendimentos"]]
            antes = json.dumps(dados, sort_keys=True)
            yield dados
            if json.dumps(dados, sort_keys=True) != antes:
                salvar_json(caminho, dados)

    def _notas_do_mes(self, ano: int, mes: int) -> list | None:
        """Notas com competência no mês, ou None se a pasta das notas não puder ser lida."""
        pasta = self._cfg["pasta_notas"]
        if not pasta or not Path(pasta).is_dir():
            return None
        try:
            # A tela de notas já leu a pasta ao abrir o app: aproveita a mesma leitura.
            v = self._varredura if getattr(self, "_varredura", None) is not None and self._pasta_lida == pasta \
                else self._ler_notas(pasta)
            return v.do_mes(ano, mes)
        except Exception:  # noqa: BLE001 — sem notas a ficha continua funcionando
            traceback.print_exc()
            return None

    def _pacientes_orto(self) -> list[dict]:
        try:
            return carregar_json(config.caminho_agendamentos(), {"pacientes": []}, "Os pacientes")["pacientes"]
        except DadosIlegiveis:
            return []

    def _vista_ficha(self, dados: dict, ano: int, mes: int, notas: list | None) -> list[dict]:
        hoje = date.today()
        lista = []
        for a in fc.do_mes(dados["atendimentos"], ano, mes):
            numero = fc.nota_do_atendimento(a, notas) if notas else None
            lista.append({
                **a,
                "situacao": fc.situacao(a, hoje),
                "forma_texto": fc.forma_por_extenso(a),
                "nota_numero": numero,
                "nota": bool(numero or a["nota_manual"]),
            })
        return lista

    def _lista_ficha(self, dados: dict, ano: int, mes: int) -> dict:
        notas = self._notas_do_mes(ano, mes)
        lista = self._vista_ficha(dados, ano, mes, notas)
        orto = self._pacientes_orto()
        return {
            "ano": ano,
            "mes": mes,
            "atendimentos": lista,
            "totais": fc.totais(lista),
            "meses": fc.meses(dados["atendimentos"]),
            "nomes": fc.nomes_salvos(dados["atendimentos"], orto),
            # Paciente de orto escolhido no campo já vem com a manutenção e o valor.
            "orto": {p["nome"]: p.get("valor_centavos") for p in orto},
            "notas_lidas": notas is not None,
        }

    @seguro
    def pagamentos_listar(self, ano: int, mes: int):
        with self._ficha() as d:
            return self._lista_ficha(d, int(ano), int(mes))

    @seguro
    def pagamentos_salvar(self, dados: dict, atendimento_id: str | None = None):
        """Devolve a lista do mês do atendimento salvo, que pode ser outro mês."""
        with self._ficha() as d:
            if atendimento_id:
                a = fc.alterar(d["atendimentos"], atendimento_id, dados, date.today())
            else:
                a = fc.adicionar(d["atendimentos"], dados, date.today())
            return self._lista_ficha(d, int(a["data"][:4]), int(a["data"][5:7]))

    @seguro
    def pagamentos_marcar_pago(self, atendimento_id: str, pago: bool, ano: int, mes: int):
        with self._ficha() as d:
            fc.marcar_pago(fc.buscar(d["atendimentos"], atendimento_id), bool(pago), date.today())
            return self._lista_ficha(d, int(ano), int(mes))

    @seguro
    def pagamentos_apagar(self, atendimento_id: str, ano: int, mes: int):
        with self._ficha() as d:
            a = fc.buscar(d["atendimentos"], atendimento_id)
            d["atendimentos"].remove(a)
            return {**self._lista_ficha(d, int(ano), int(mes)), "apagado": a}

    @seguro
    def pagamentos_restaurar(self, atendimento: dict, ano: int, mes: int):
        with self._ficha() as d:
            fc.restaurar(d["atendimentos"], atendimento)
            return self._lista_ficha(d, int(ano), int(mes))

    @seguro
    def pagamentos_exportar(self, ano: int, mes: int):
        ano, mes = int(ano), int(mes)
        with self._ficha() as d:
            lista = self._vista_ficha(d, ano, mes, self._notas_do_mes(ano, mes))
        destino = self._dialogo_salvar(exp.nome_sugerido(ano, mes), "xlsx", "Planilha do Excel")
        if destino is None:
            return {"cancelado": True}
        try:
            salvo = exp.exportar(lista, destino, ano, mes)
        except PermissionError:
            return {"erro": "Não consegui salvar: o arquivo está aberto no Excel? Feche e tente de novo."}
        self._cfg = config.salvar({**self._cfg, "pasta_saida": str(salvo.parent)})
        return {"caminho": str(salvo), "qtd": len(lista)}
