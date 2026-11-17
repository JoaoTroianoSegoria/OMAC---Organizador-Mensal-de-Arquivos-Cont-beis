"""Parte da API que cuida dos tratamentos de ortodontia (antes "Agendamentos").

O nome e o telefone vêm do contato; aqui ficam só a manutenção, a situação, o confere,
o atendido de cada mês e o histórico. Criar, alterar e apagar é pela janela de contato.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..contatos import contatos as ct
from ..dados import esquema
from ..inicio.registro import widget
from ..nucleo import ApiBase, seguro
from ..texto import normalizar
from ..whatsapp.mensagens import abrir_conversa, normalizar_telefone
from . import mensagens as msg
from . import orto


class TratamentosApi(ApiBase):
    def _tratamentos_e_contatos(self) -> tuple[list[dict], dict[str, dict]]:
        tratamentos = self._armazem.ler(esquema.TRATAMENTOS)["tratamentos"]
        contatos = {c["id"]: c for c in self._armazem.ler(esquema.CONTATOS)["contatos"]}
        # Um tratamento sem contato (arquivo mexido à mão) não pode derrubar a tela.
        return [t for t in tratamentos if t["contato_id"] in contatos], contatos

    def _vista_tratamentos(self) -> dict:
        hoje = date.today()
        tratamentos, contatos = self._tratamentos_e_contatos()
        lista_contatos = list(contatos.values())

        def vista(t: dict) -> dict:
            c = contatos[t["contato_id"]]
            return {**t, "nome": c["nome"], "telefone": c["telefone"], "situacao": orto.situacao(t),
                    "destino": ct.destino_escolhido(lista_contatos, c)}

        ordenados = sorted(tratamentos, key=lambda t: normalizar(contatos[t["contato_id"]]["nome"]))
        na_situacao = lambda s: [t for t in ordenados if orto.situacao(t) == s]  # noqa: E731
        return {
            "ano": hoje.year,
            "mes": hoje.month,
            "ativos": [{**vista(t), "agendado": orto.agendado_no_mes(t, hoje), "atendido": orto.atendido_no_mes(t, hoje)}
                       for t in na_situacao(orto.ATIVO)],
            # A alta que acaba primeiro aparece primeiro.
            "altas": [{**vista(t), "terminou": orto.alta_terminou(t, hoje)}
                      for t in sorted(na_situacao(orto.ALTA), key=lambda t: t["alta_fim"])],
            "finalizados": [vista(t) for t in na_situacao(orto.FINALIZADO)],
        }

    def _mudar_tratamento(self, tratamento_id: str, mudar) -> dict:
        with self._armazem.editar(esquema.TRATAMENTOS) as d:
            mudar(orto.buscar(d["tratamentos"], tratamento_id))
        return self._vista_tratamentos()

    @seguro
    def tratamentos_listar(self):
        return self._vista_tratamentos()

    @seguro
    def tratamentos_voltar_ao_tratamento(self, tratamento_id: str):
        return self._mudar_tratamento(tratamento_id, orto.voltar_ao_tratamento)

    @seguro
    def tratamentos_marcar(self, tratamento_id: str, agendado: bool):
        return self._mudar_tratamento(tratamento_id, lambda t: orto.marcar_agendado(t, bool(agendado), date.today()))

    @seguro
    def tratamentos_marcar_atendido(self, tratamento_id: str, mes: str, atendido: bool):
        """`mes` é "AAAA-MM". Devolve a lista e o histórico, que mudam juntos."""
        return self._mudar_tratamento(
            tratamento_id, lambda t: orto.marcar_atendido(t, str(mes)[:7], bool(atendido), date.today()))

    @seguro
    def tratamentos_historico(self, ano: int, mes: int, quantos: int = 6):
        """Os `quantos` meses que terminam em (ano, mês): uma coluna por mês, uma linha por paciente."""
        hoje = date.today()
        meses = orto.meses_ate(int(ano), int(mes), max(1, min(int(quantos), 12)))
        tratamentos, contatos = self._tratamentos_e_contatos()
        linhas = []
        for t in sorted(tratamentos, key=lambda t: normalizar(contatos[t["contato_id"]]["nome"])):
            celulas = [orto.situacao_no_mes(t, a, m, hoje) for a, m in meses]
            if any(celulas):  # quem não era paciente em nenhum desses meses fica de fora
                linhas.append({"id": t["id"], "nome": contatos[t["contato_id"]]["nome"],
                               "situacao": orto.situacao(t), "meses": celulas})
        colunas = []
        for i, (a, m) in enumerate(meses):
            do_mes = [linha["meses"][i] for linha in linhas]
            colunas.append({"ano": a, "mes": m, "chave": orto.chave_do_mes(a, m),
                            "veio": do_mes.count(orto.VEIO),
                            "esperados": sum(c in (orto.VEIO, orto.NAO_VEIO, orto.FALTA_VIR) for c in do_mes)})
        return {"meses": colunas, "pacientes": linhas, "hoje": orto.chave_do_mes(hoje.year, hoje.month)}

    @seguro
    def tratamentos_historico_paciente(self, tratamento_id: str):
        tratamentos, contatos = self._tratamentos_e_contatos()
        t = orto.buscar(tratamentos, tratamento_id)
        return {"id": t["id"], "nome": contatos[t["contato_id"]]["nome"],
                **orto.historico_do_paciente(t, date.today())}

    # --- Mensagens -------------------------------------------------------------------------

    @seguro
    def tratamentos_preparar_mensagens(self, tratamento_id: str):
        """Uma lista de destinos (o paciente e cada responsável), cada um com as três mensagens."""
        tratamentos, contatos = self._tratamentos_e_contatos()
        t = orto.buscar(tratamentos, tratamento_id)
        paciente = contatos[t["contato_id"]]
        hoje = date.today()
        destinos = []
        for d in ct.destinos(list(contatos.values()), paciente):
            responsavel = d["nome"] if d["papel"] else ""
            destinos.append({**d, "mensagens": msg.todas(self._cfg["assistente_nome"], paciente["nome"], hoje,
                                                         t["valor_centavos"], self._cfg["chave_pix"], responsavel)})
        return {"id": t["id"], "nome": paciente["nome"], "destinos": destinos,
                "escolhido": ct.destino_escolhido(list(contatos.values()), paciente)["contato_id"]}

    @seguro
    def tratamentos_enviar(self, tratamento_id: str, destino_id: str, telefone: str, mensagem: str):
        """Guarda o telefone no contato que recebe e lembra a escolha para a próxima vez."""
        telefone = normalizar_telefone(telefone)
        tratamentos, _ = self._tratamentos_e_contatos()
        t = orto.buscar(tratamentos, tratamento_id)
        with self._armazem.editar(esquema.CONTATOS) as d:
            contatos = d["contatos"]
            paciente = ct.buscar(contatos, t["contato_id"])
            if destino_id != paciente["id"] and destino_id not in {r["contato_id"] for r in paciente["responsaveis"]}:
                return {"erro": "Escolha para quem vai a mensagem."}
            ct.buscar(contatos, destino_id)["telefone"] = telefone
            paciente["envia_para"] = "" if destino_id == paciente["id"] else destino_id
        lista = self._vista_tratamentos()
        abrir_conversa(telefone, mensagem, self._cfg["whatsapp_destino"])
        return lista

    # --- Widget do Início --------------------------------------------------------------------

    @widget("tratamentos", "Tratamentos", ordem=30)
    def _widget_tratamentos(self, hoje: date) -> dict:
        anterior = hoje.replace(day=1) - timedelta(days=1)
        tratamentos, contatos = self._tratamentos_e_contatos()
        ativos = [t for t in tratamentos if orto.situacao(t) == orto.ATIVO]
        altas = [t for t in tratamentos if orto.situacao(t) == orto.ALTA]
        semana = (hoje + timedelta(days=7)).isoformat()
        return {
            "ativos": len(ativos),
            "agendados": sum(orto.agendado_no_mes(t, hoje) for t in ativos),
            "atendidos": sum(orto.atendido_no_mes(t, hoje) for t in ativos),
            "altas_terminadas": sum(orto.alta_terminou(t, hoje) for t in altas),
            "altas_acabando": [{"nome": contatos[t["contato_id"]]["nome"], "alta_fim": t["alta_fim"]}
                               for t in sorted(altas, key=lambda t: t["alta_fim"])
                               if hoje.isoformat() <= t["alta_fim"] <= semana],
            "nao_vieram_mes_passado": sum(orto.situacao_no_mes(t, anterior.year, anterior.month, hoje) == orto.NAO_VEIO
                                          for t in tratamentos),
        }
