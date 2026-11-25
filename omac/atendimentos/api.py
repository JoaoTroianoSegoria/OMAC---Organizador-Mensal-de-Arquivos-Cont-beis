"""Parte da API que cuida da ficha de atendimentos (antes "Pagamentos")."""

from __future__ import annotations

from datetime import date, timedelta

from .. import config
from ..contatos import contatos as ct
from ..dados import esquema
from ..inicio.registro import widget
from ..nucleo import ApiBase, seguro
from ..texto import normalizar
from ..tratamentos import orto
from ..whatsapp import catalogo as cat
from . import exportar as exp
from . import ficha as fc
from . import listas as lst


class AtendimentosApi(ApiBase):
    def _atendimentos(self) -> list[dict]:
        return self._armazem.ler(esquema.ATENDIMENTOS)["atendimentos"]

    def _vista_ficha(self, atendimentos: list[dict], ano: int, mes: int, notas: list | None,
                     da_lista=None) -> list[dict]:
        """Os atendimentos do mês prontos para a tela. As notas são ligadas olhando o mês inteiro
        (todas as listas), como antes das listas; `da_lista(a)` escolhe quais vão para a tela."""
        hoje = date.today()
        nomes = ct.nomes(self._armazem.ler(esquema.CONTATOS)["contatos"])
        do_mes = fc.do_mes(atendimentos, ano, mes)
        ligadas = fc.ligar_notas(do_mes, {a["id"]: nomes.get(a["contato_id"], "") for a in do_mes},
                                 notas) if notas else {}
        valores = {n.numero: int(round(n.valor * 100)) for n in notas or []}
        lista = []
        for a in do_mes:
            if da_lista and not da_lista(a):
                continue
            nome = nomes.get(a["contato_id"], "(contato apagado)")
            numero = ligadas.get(a["id"])
            lista.append({
                **a,
                "nome": nome,
                "situacao": fc.situacao(a, hoje),
                "forma_texto": fc.forma_por_extenso(a),
                "nota_numero": numero,
                "nota_valor_centavos": valores.get(numero),
                "nota_situacao": fc.situacao_da_nota(a, numero),
            })
        lista.sort(key=lambda a: (a["data"], normalizar(a["nome"])))
        return lista

    def _lista_ficha(self, ano: int, mes: int, lista_id: str = "") -> dict:
        dados = self._armazem.ler(esquema.ATENDIMENTOS)
        atendimentos = dados["atendimentos"]
        listas = lst.todas(dados)
        lista_id = lst.certa(lista_id, listas)
        notas = self._servico_notas.do_mes(ano, mes)
        lista = self._vista_ficha(atendimentos, ano, mes, notas, lambda a: lst.da(a, listas) == lista_id)
        do_mes = fc.do_mes(atendimentos, ano, mes)
        contatos = self._armazem.ler(esquema.CONTATOS)["contatos"]
        nomes = ct.nomes(contatos)
        tratamentos = self._armazem.ler(esquema.TRATAMENTOS)["tratamentos"]
        return {
            "ano": ano,
            "mes": mes,
            "lista_id": lista_id,
            "listas": [{**item, "qtd": len(lst.filtrar(do_mes, listas, item["id"])),
                        "total": len(lst.filtrar(atendimentos, listas, item["id"]))} for item in listas],
            "atendimentos": lista,
            "totais": fc.totais(lista),
            "meses": fc.meses(lst.filtrar(atendimentos, listas, lista_id)),
            "nomes": sorted(nomes.values(), key=normalizar),
            # Paciente de orto em tratamento escolhido no campo já vem com a manutenção e o valor.
            "orto": {nomes[t["contato_id"]]: t["valor_centavos"] for t in tratamentos
                     if t["contato_id"] in nomes and orto.situacao(t) == orto.ATIVO},
            "notas_lidas": notas is not None,
            "sem_nota_por_padrao": sorted(fc.SEM_NOTA_POR_PADRAO),
        }

    def _editar_ficha(self, mudar) -> None:
        with self._armazem.editar(esquema.ATENDIMENTOS) as d:
            atendimentos = d["atendimentos"]
            mudar(atendimentos)

    @seguro
    def atendimentos_listar(self, ano: int, mes: int, lista_id: str = ""):
        return self._lista_ficha(int(ano), int(mes), lista_id)

    # --- Listas (Brasília, São Paulo…) -----------------------------------------------------

    def _mudar_listas(self, mudar) -> str:
        with self._armazem.editar(esquema.ATENDIMENTOS) as d:
            return mudar(d)

    @seguro
    def atendimentos_lista_criar(self, nome: str, ano: int, mes: int):
        nova = self._mudar_listas(lambda d: lst.criar(d, nome)["id"])
        return self._lista_ficha(int(ano), int(mes), nova)

    @seguro
    def atendimentos_lista_renomear(self, lista_id: str, nome: str, ano: int, mes: int):
        self._mudar_listas(lambda d: lst.renomear(d, lista_id, nome))
        return self._lista_ficha(int(ano), int(mes), lista_id)

    @seguro
    def atendimentos_lista_apagar(self, lista_id: str, ano: int, mes: int):
        self._mudar_listas(lambda d: lst.apagar(d, lista_id))
        return self._lista_ficha(int(ano), int(mes))

    @seguro
    def atendimentos_salvar(self, dados: dict, atendimento_id: str | None = None):
        """O paciente é escolhido pelo nome: um nome que não existe vira contato novo.

        Devolve a lista do mês do atendimento salvo, que pode ser outro mês.
        """
        hoje = date.today()
        if not " ".join(str(dados.get("nome") or "").split()):
            return {"erro": "Diga o nome do paciente."}
        fc.validar(dados)  # antes de criar um contato para um atendimento que nem vai ser salvo
        salvo = {}
        with self._armazem.editar(esquema.CONTATOS) as d:
            contatos = d["contatos"]
            contato = ct.obter(contatos, dados.get("nome"), "", hoje)

        with self._armazem.editar(esquema.ATENDIMENTOS) as d:
            atendimentos, listas = d["atendimentos"], lst.todas(d)
            if atendimento_id:
                atendimento = fc.alterar(atendimentos, atendimento_id, contato["id"], dados, hoje)
            else:
                atendimento = fc.adicionar(atendimentos, contato["id"], dados, hoje)
            # Sem "lista_id" (uma tela antiga), o alterado fica onde estava e o novo vai para a primeira.
            if "lista_id" in dados or not atendimento_id:
                atendimento["lista_id"] = lst.certa(dados.get("lista_id"), listas)
            salvo.update(atendimento, lista_id=lst.da(atendimento, listas))
        marcado = self._atendido_pela_ficha(contato["id"], salvo, hoje)
        return {**self._lista_ficha(int(salvo["data"][:4]), int(salvo["data"][5:7]), salvo["lista_id"]),
                "atendido_marcado": contato["nome"] if marcado else ""}

    def _atendido_pela_ficha(self, contato_id: str, atendimento: dict, hoje: date) -> bool:
        """Atendimento de manutenção de quem está em Tratamentos: marca o Atendido do mês, com o dia
        do atendimento. Só marca (nunca desmarca) e não mexe em mês já marcado."""
        if "MANUTENCAO" not in normalizar(atendimento.get("tratamento") or ""):
            return False
        dia = atendimento["data"]
        if dia > hoje.isoformat():
            return False
        with self._armazem.editar(esquema.TRATAMENTOS) as d:
            t = orto.do_contato(d["tratamentos"], contato_id)
            if t is None or orto.situacao(t) == orto.FINALIZADO or dia[:7] in t["atendidos"]:
                return False
            t["atendidos"] = {**t["atendidos"], dia[:7]: dia}
        return True

    # --- Cobrar pelo WhatsApp (só quem ainda não pagou) -------------------------------------

    @seguro
    def atendimentos_preparar_cobranca(self, atendimento_id: str):
        """O paciente e cada responsável, com a mensagem de cobrança de cada um."""
        a = fc.buscar(self._armazem.ler(esquema.ATENDIMENTOS)["atendimentos"], atendimento_id)
        contatos = self._lista_de_contatos()
        paciente = ct.buscar(contatos, a["contato_id"])
        dia = date.fromisoformat(a["data"])
        destinos = [{**d, "mensagem": cat.cobranca(self._cfg, d["nome"], d["papel"], paciente["nome"], dia,
                                                    a.get("tratamento", ""), a.get("valor_centavos"))}
                    for d in ct.destinos(contatos, paciente)]
        precisa_pix = any(cat.usa(self._cfg, cat.COBRANCA, v, "chave-pix") for v in (cat.PACIENTE, cat.RESPONSAVEL))
        return {"id": a["id"], "nome": paciente["nome"], "data": a["data"], "tratamento": a.get("tratamento", ""),
                "valor_centavos": a.get("valor_centavos"), "destinos": destinos,
                "escolhido": ct.destino_escolhido(contatos, paciente)["contato_id"],
                "sem_pix": precisa_pix and not self._cfg.get("chave_pix", "").strip()}

    @seguro
    def atendimentos_cobrar(self, atendimento_id: str, destino_id: str, telefone: str, mensagem: str):
        a = fc.buscar(self._armazem.ler(esquema.ATENDIMENTOS)["atendimentos"], atendimento_id)
        return self._mensagem_para(a["contato_id"], destino_id, telefone, mensagem) or {}

    @seguro
    def atendimentos_marcar_pago(self, atendimento_id: str, pago: bool, ano: int, mes: int, lista_id: str = ""):
        self._editar_ficha(lambda lista: fc.marcar_pago(fc.buscar(lista, atendimento_id), bool(pago), date.today()))
        return self._lista_ficha(int(ano), int(mes), lista_id)

    @seguro
    def atendimentos_apagar(self, atendimento_id: str, ano: int, mes: int, lista_id: str = ""):
        apagado = {}

        def mudar(lista):
            a = fc.buscar(lista, atendimento_id)
            lista.remove(a)
            apagado.update(a)

        self._editar_ficha(mudar)
        nome = self._nomes_dos_contatos().get(apagado["contato_id"], "")
        return {**self._lista_ficha(int(ano), int(mes), lista_id), "apagado": apagado, "apagado_nome": nome}

    @seguro
    def atendimentos_restaurar(self, atendimento: dict, ano: int, mes: int, lista_id: str = ""):
        self._editar_ficha(lambda lista: fc.restaurar(lista, atendimento))
        return self._lista_ficha(int(ano), int(mes), lista_id)

    @seguro
    def atendimentos_exportar(self, ano: int, mes: int, lista_id: str = ""):
        """A planilha (para imprimir) é da lista aberta. Com mais de uma lista, o nome dela vai no
        nome do arquivo e no alto da folha impressa."""
        ano, mes = int(ano), int(mes)
        dados = self._armazem.ler(esquema.ATENDIMENTOS)
        listas = lst.todas(dados)
        lista_id = lst.certa(lista_id, listas)
        lista = self._vista_ficha(dados["atendimentos"], ano, mes, self._servico_notas.do_mes(ano, mes),
                                  lambda a: lst.da(a, listas) == lista_id)
        nome_lista = lst.nome_de(listas, lista_id) if len(listas) > 1 else ""
        destino = self._dialogo_salvar(exp.nome_sugerido(ano, mes, nome_lista), "xlsx", "Planilha do Excel")
        if destino is None:
            return {"cancelado": True}
        try:
            salvo = exp.exportar(lista, destino, ano, mes, nome_lista)
        except PermissionError:
            return {"erro": "Não consegui salvar: o arquivo está aberto no Excel? Feche e tente de novo."}
        self._cfg = config.salvar({**self._cfg, "pasta_saida": str(salvo.parent)})
        return {"caminho": str(salvo), "qtd": len(lista)}

    # --- Widget do Início --------------------------------------------------------------------

    @widget("atendimentos", "Atendimentos do mês", ordem=40)
    def _widget_atendimentos(self, hoje: date) -> dict:
        anterior = hoje.replace(day=1) - timedelta(days=1)
        atendimentos = self._atendimentos()
        lista = self._vista_ficha(atendimentos, hoje.year, hoje.month, self._servico_notas.do_mes(hoje.year, hoje.month))
        mes_passado = [a for a in fc.do_mes(atendimentos, anterior.year, anterior.month)
                       if fc.situacao(a, hoje) == fc.NAO_PAGO]
        return {**fc.totais(lista), "qtd": len(lista), "nao_pagos_mes_passado": len(mes_passado)}
