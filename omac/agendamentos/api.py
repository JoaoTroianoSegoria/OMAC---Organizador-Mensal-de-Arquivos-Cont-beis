"""Parte da API que cuida dos agendamentos."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from datetime import date

from .. import config
from ..armazem import carregar_json, salvar_json
from ..nucleo import ApiBase, seguro
from ..texto import normalizar
from ..whatsapp.mensagens import abrir_conversa, normalizar_telefone
from . import mensagens as msg
from . import pacientes as pc

PADRAO = {"pacientes": []}


class AgendamentosApi(ApiBase):
    def __init__(self):
        super().__init__()
        self._trava_agenda = threading.Lock()

    @contextmanager
    def _agenda(self):
        with self._trava_agenda:
            caminho = config.caminho_agendamentos()
            dados = carregar_json(caminho, PADRAO, "Os pacientes")
            dados["pacientes"] = [pc.completar(p) for p in dados["pacientes"]]
            antes = json.dumps(dados, sort_keys=True)
            yield dados
            if json.dumps(dados, sort_keys=True) != antes:
                salvar_json(caminho, dados)

    def _lista(self, dados: dict) -> dict:
        hoje = date.today()
        ordenados = sorted(dados["pacientes"], key=lambda p: normalizar(p["nome"]))

        def vista(p: dict) -> dict:
            return {**p, "situacao": pc.situacao(p), "destino": pc.destino(p)}

        na_situacao = lambda s: [p for p in ordenados if pc.situacao(p) == s]  # noqa: E731
        return {
            "ano": hoje.year,
            "mes": hoje.month,
            "ativos": [{**vista(p), "agendado": pc.agendado_no_mes(p, hoje)} for p in na_situacao(pc.ATIVO)],
            # A alta que acaba primeiro aparece primeiro.
            "altas": [{**vista(p), "terminou": pc.alta_terminou(p, hoje)}
                      for p in sorted(na_situacao(pc.ALTA), key=lambda p: p["alta_fim"])],
            "finalizados": [vista(p) for p in na_situacao(pc.FINALIZADO)],
        }

    @seguro
    def agendamentos_listar(self):
        with self._agenda() as d:
            return self._lista(d)

    @seguro
    def agendamentos_salvar(self, dados: dict, paciente_id: str | None = None):
        with self._agenda() as d:
            if paciente_id:
                pc.alterar(d["pacientes"], paciente_id, dados, date.today())
            else:
                pc.adicionar(d["pacientes"], dados)
            return self._lista(d)

    @seguro
    def agendamentos_voltar_ao_tratamento(self, paciente_id: str):
        with self._agenda() as d:
            pc.voltar_ao_tratamento(pc.buscar(d["pacientes"], paciente_id))
            return self._lista(d)

    @seguro
    def agendamentos_apagar(self, paciente_id: str):
        with self._agenda() as d:
            paciente = pc.buscar(d["pacientes"], paciente_id)
            d["pacientes"].remove(paciente)
            return {**self._lista(d), "apagado": paciente}

    @seguro
    def agendamentos_restaurar(self, paciente: dict):
        with self._agenda() as d:
            pc.restaurar(d["pacientes"], paciente)
            return self._lista(d)

    @seguro
    def agendamentos_marcar(self, paciente_id: str, agendado: bool):
        with self._agenda() as d:
            pc.marcar_agendado(pc.buscar(d["pacientes"], paciente_id), bool(agendado), date.today())
            return self._lista(d)

    @seguro
    def agendamentos_preparar_mensagens(self, paciente_id: str):
        with self._agenda() as d:
            p = pc.buscar(d["pacientes"], paciente_id)
        destino = pc.destino(p)
        return {
            "id": p["id"],
            "nome": p["nome"],
            "destino": destino,
            "mensagens": msg.todas(self._cfg["assistente_nome"], p["nome"], date.today(),
                                   p["valor_centavos"], self._cfg["chave_pix"],
                                   destino["nome"] if destino["papel"] else ""),
        }

    @seguro
    def agendamentos_enviar(self, paciente_id: str, telefone: str, mensagem: str):
        telefone = normalizar_telefone(telefone)
        with self._agenda() as d:
            pc.guardar_telefone(pc.buscar(d["pacientes"], paciente_id), telefone)
            lista = self._lista(d)
        abrir_conversa(telefone, mensagem, self._cfg["whatsapp_destino"])
        return lista
