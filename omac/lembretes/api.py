"""Parte da API que cuida dos Lembretes: contas a pagar, lembretes livres e comandos."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta

from ..contatos import contatos as ct
from ..dados import esquema
from ..inicio.registro import widget
from ..nucleo import ApiBase, seguro
from ..planilha import MESES
from ..texto import normalizar
from ..whatsapp import catalogo as cat
from ..whatsapp import mensagens as msg
from . import comandos as cm
from . import contas as lb
from . import livres as lv


class LembretesApi(ApiBase):
    @contextmanager
    def _contas(self):
        """lembretes.json, com cada conta completa (pagas e desde quando é acompanhada)."""
        with self._armazem.editar(esquema.LEMBRETES) as d:
            hoje = date.today()
            d["contas"] = [lb.completar_conta(c, hoje) for c in d["contas"]]
            yield d

    def _destinatario(self) -> dict | None:
        """O contato que recebe os lembretes de contas."""
        destino = self._armazem.ler(esquema.LEMBRETES)["destinatario"]
        contatos = self._armazem.ler(esquema.CONTATOS)["contatos"]
        return next((c for c in contatos if c["id"] == destino), None) if destino else None

    def _nome_do_destinatario(self) -> str:
        destino = self._destinatario()
        return destino["nome"] if destino else ""

    def _destinatario_de(self, contato_id: str = "") -> dict | None:
        """Quem recebe: o contato escolhido (se ainda existir) ou quem recebe os lembretes de contas."""
        if contato_id:
            contatos = self._armazem.ler(esquema.CONTATOS)["contatos"]
            escolhido = next((c for c in contatos if c["id"] == contato_id), None)
            if escolhido:
                return escolhido
        return self._destinatario()

    # --- Contas ------------------------------------------------------------------------------

    def _vista_contas(self, contas: list[dict]) -> dict:
        hoje = date.today()
        anterior = hoje.replace(day=1) - timedelta(days=1)
        vista = []
        for c in sorted(contas, key=lambda c: (c["dia"], normalizar(c["nome"]))):
            vencimento = lb.vencimento_no_mes(c, hoje.year, hoje.month)
            este_mes = lb.situacao_no_mes(c, hoje.year, hoje.month, hoje)
            mes_passado = lb.situacao_no_mes(c, anterior.year, anterior.month, hoje)
            vista.append({
                **c,
                "este_mes": este_mes,
                "mes_passado": mes_passado,
                "vencimento": vencimento.isoformat(),
                "venceu": vencimento < hoje,
                # Tem o que lembrar: a deste mês em aberto ou a do mês passado sem pagar.
                "em_aberto": este_mes == lb.EM_ABERTO or mes_passado == lb.NAO_PAGA,
            })
        return {
            "contas": vista,
            "mes": f"{hoje:%Y-%m}",
            "nome_mes": MESES[hoje.month - 1],
            "nome_mes_passado": MESES[anterior.month - 1],
            "destinatario": self._nome_do_destinatario(),
        }

    @seguro
    def lembretes_contas(self):
        with self._contas() as d:
            return self._vista_contas(d["contas"])

    @seguro
    def lembretes_salvar_conta(self, conta: dict, antiga: dict | None = None):
        with self._contas() as d:
            d["contas"] = lb.adicionar_conta(d["contas"], conta, antiga)
            return self._vista_contas(d["contas"])

    @seguro
    def lembretes_apagar_conta(self, nome: str):
        with self._contas() as d:
            d["contas"] = lb.remover_conta(d["contas"], nome)
            return self._vista_contas(d["contas"])

    @seguro
    def lembretes_marcar_paga(self, nome: str, mes: str, paga: bool = True):
        """`mes` é "AAAA-MM", o mês do vencimento."""
        with self._contas() as d:
            lb.marcar_paga(lb.buscar_conta(d["contas"], nome), str(mes)[:7], bool(paga), date.today())
            return self._vista_contas(d["contas"])

    @seguro
    def lembretes_preparar_contas(self, nome: str | None = None):
        """A mensagem para mandar agora, de uma conta (`nome`) ou de todas as em aberto.

        Vale a qualquer momento, inclusive depois do vencimento ("venceu dia X"). Não mexe
        no aviso automático da primeira abertura do dia.
        """
        with self._contas() as d:
            if nome is not None:
                lb.buscar_conta(d["contas"], nome)
            itens = lb.contas_em_aberto(d["contas"], date.today(), nome)
        destino = self._destinatario()
        destinatario = destino["nome"] if destino else ""
        return {
            "contas": itens,
            "destinatario": destinatario,
            "telefone": destino["telefone"] if destino else "",
            "mensagem": cat.lembrete_contas(self._cfg, destinatario, itens) if itens else "",
        }

    @seguro
    def lembretes_texto(self, contas: list[dict]):
        """Refaz a mensagem do lembrete sem as contas que acabaram de ser marcadas como pagas."""
        return {"mensagem": cat.lembrete_contas(self._cfg, self._nome_do_destinatario(), contas)}

    @seguro
    def lembretes_do_dia(self, forcar: bool = False):
        """O que mostrar ao abrir o app. Contas e fechamento: só na primeira abertura do dia
        (`forcar` mostra os de hoje de novo). Lembretes que repetem: toda vez, até serem feitos."""
        hoje = date.today()
        with self._contas() as d:
            ultima = date.fromisoformat(d["ultima_abertura"]) if d["ultima_abertura"] else None
            primeira = forcar or ultima != hoje
            if not forcar and primeira:
                d["ultima_abertura"] = hoje.isoformat()
            desde = None if forcar else ultima
            contas = lb.contas_a_avisar(d["contas"], hoje, desde) if primeira else []
            livres = [self._livre_para_tela(x, hoje) for x in lv.a_lembrar_ao_abrir(d["livres"], hoje)]

        fechamento = lb.aviso_de_fechamento(self._cfg["lembrete_fechamento_dia"], hoje, desde) if primeira else ""
        destinatario = self._nome_do_destinatario()
        return {
            "mostrar": bool(contas or fechamento or livres),
            "contas": contas,
            "livres": livres,
            "fechamento": fechamento,
            "destinatario": destinatario,
            "mensagem": cat.lembrete_contas(self._cfg, destinatario, contas),
        }

    @seguro
    def lembretes_enviar(self, mensagem: str, contato_id: str = ""):
        """Abre a conversa com quem recebe os lembretes (ou com `contato_id`, o de um lembrete)."""
        destino = self._destinatario_de(contato_id)
        if not destino or not destino["telefone"]:
            return {"sem_contato": True, "nome": destino["nome"] if destino else ""}
        msg.abrir_conversa(destino["telefone"], mensagem, self._cfg["whatsapp_destino"])
        return {}

    # --- Quem recebe os lembretes (Configurações) --------------------------------------------

    @seguro
    def lembretes_destinatario(self):
        return {"contato": self._destinatario(),
                "nomes": sorted(self._nomes_dos_contatos().values(), key=normalizar)}

    @seguro
    def lembretes_definir_destinatario(self, nome: str):
        """Escolhe o contato pelo nome; "" desliga. Um nome que não existe vira contato novo."""
        nome = " ".join(str(nome or "").split())
        contato_id = ""
        if nome:
            with self._armazem.editar(esquema.CONTATOS) as d:
                contato_id = ct.obter(d["contatos"], nome)["id"]
        with self._armazem.editar(esquema.LEMBRETES) as d:
            d["destinatario"] = contato_id
        return self.lembretes_destinatario()

    # --- Lembretes livres ------------------------------------------------------------------------

    def _livre_para_tela(self, item: dict, hoje: date) -> dict:
        proxima = lv.proxima(item, hoje)
        escolhido = self._destinatario_de(item["destinatario"]) if item["destinatario"] else None
        return {**item, "quando": lv.quando(item), "proxima": proxima.isoformat() if proxima else "",
                "destinatario_nome": escolhido["nome"] if escolhido else ""}

    def _vista_livres(self, livres: list[dict]) -> dict:
        hoje = date.today()
        return {"em_aberto": [self._livre_para_tela(x, hoje) for x in lv.em_aberto(livres, hoje)],
                "programados": [self._livre_para_tela(x, hoje) for x in lv.programados(livres, hoje)],
                "feitos": [self._livre_para_tela(x, hoje) for x in lv.feitos(livres)],
                "padrao": self._nome_do_destinatario(),
                "nomes": sorted(self._nomes_dos_contatos().values(), key=normalizar)}

    def _mudar_livres(self, mudar) -> dict:
        with self._armazem.editar(esquema.LEMBRETES) as d:
            extra = mudar(d["livres"]) or {}
            return {**self._vista_livres(d["livres"]), **extra}

    @seguro
    def lembretes_livres(self):
        return self._vista_livres(self._armazem.ler(esquema.LEMBRETES)["livres"])

    @seguro
    def lembretes_salvar_livre(self, dados: dict, lembrete_id: str | None = None):
        """`dados["destinatario"]`: o nome de quem recebe este lembrete ("" = quem recebe os das contas).
        Um nome que não existe vira contato novo, como em Configurações."""
        hoje = date.today()
        lv.salvar([], dados, None, hoje)  # valida antes de criar um contato à toa
        destinatario = None
        if "destinatario" in dados:
            destinatario = ""
            nome = " ".join(str(dados.get("destinatario") or "").split())
            padrao = self._destinatario()
            if nome and not (padrao and normalizar(padrao["nome"]) == normalizar(nome)):
                with self._armazem.editar(esquema.CONTATOS) as d:
                    destinatario = ct.obter(d["contatos"], nome, "", hoje)["id"]
        return self._mudar_livres(
            lambda livres: {"salvo": lv.salvar(livres, dados, lembrete_id, hoje, destinatario)})

    @seguro
    def lembretes_preparar_livre(self, lembrete_id: str):
        """A mensagem de um lembrete para mandar pelo WhatsApp (com o botão, como nas contas)."""
        item = lv.buscar(self._armazem.ler(esquema.LEMBRETES)["livres"], lembrete_id)
        destino = self._destinatario_de(item["destinatario"])
        nome = destino["nome"] if destino else ""
        return {
            "titulo": item["titulo"],
            "contato_id": destino["id"] if destino else "",
            "destinatario": nome,
            "telefone": destino["telefone"] if destino else "",
            "mensagem": cat.lembrete_livre(self._cfg, nome, item["titulo"], item["observacao"]),
        }

    @seguro
    def lembretes_marcar_feito(self, lembrete_id: str, feito: bool = True):
        return self._mudar_livres(lambda livres: lv.marcar_feito(lv.buscar(livres, lembrete_id), bool(feito), date.today()))

    @seguro
    def lembretes_apagar_livre(self, lembrete_id: str):
        def apagar(livres):
            item = lv.buscar(livres, lembrete_id)
            posicao = livres.index(item)
            livres.remove(item)
            return {"apagado": item, "posicao": posicao}

        return self._mudar_livres(apagar)

    @seguro
    def lembretes_restaurar_livre(self, lembrete: dict, posicao: int | None = None):
        return self._mudar_livres(lambda livres: lv.restaurar(livres, lembrete, posicao))

    # --- Comandos ----------------------------------------------------------------------------------

    def _mudar_comandos(self, mudar) -> dict:
        with self._armazem.editar(esquema.COMANDOS) as d:
            extra = mudar(d["categorias"]) or {}
            return {"categorias": d["categorias"], **extra}

    @seguro
    def comandos_listar(self):
        return {"categorias": self._armazem.ler(esquema.COMANDOS)["categorias"]}

    @seguro
    def comandos_salvar_categoria(self, nome: str, categoria_id: str | None = None):
        return self._mudar_comandos(lambda cats: {"salva": cm.salvar_categoria(cats, nome, categoria_id)})

    @seguro
    def comandos_apagar_categoria(self, categoria_id: str):
        def apagar(cats):
            categoria = cm.buscar_categoria(cats, categoria_id)
            posicao = cats.index(categoria)
            cats.remove(categoria)
            return {"apagada": categoria, "posicao": posicao}

        return self._mudar_comandos(apagar)

    @seguro
    def comandos_restaurar_categoria(self, categoria: dict, posicao: int | None = None):
        return self._mudar_comandos(lambda cats: cm.inserir(cats, cm.completar(categoria), posicao))

    @seguro
    def comandos_mover_categoria(self, categoria_id: str, passo: int):
        return self._mudar_comandos(lambda cats: cm.mover(cats, categoria_id, int(passo)))

    @seguro
    def comandos_salvar(self, categoria_id: str, dados: dict, comando_id: str | None = None):
        return self._mudar_comandos(
            lambda cats: {"salvo": cm.salvar_comando(cm.buscar_categoria(cats, categoria_id), dados, comando_id)})

    @seguro
    def comandos_apagar(self, categoria_id: str, comando_id: str):
        def apagar(cats):
            categoria = cm.buscar_categoria(cats, categoria_id)
            comando = cm.buscar_comando(categoria, comando_id)
            posicao = categoria["comandos"].index(comando)
            categoria["comandos"].remove(comando)
            return {"apagado": comando, "posicao": posicao}

        return self._mudar_comandos(apagar)

    @seguro
    def comandos_restaurar(self, categoria_id: str, comando: dict, posicao: int | None = None):
        return self._mudar_comandos(
            lambda cats: cm.inserir(cm.buscar_categoria(cats, categoria_id)["comandos"], comando, posicao))

    @seguro
    def comandos_mover(self, categoria_id: str, comando_id: str, passo: int):
        return self._mudar_comandos(
            lambda cats: cm.mover(cm.buscar_categoria(cats, categoria_id)["comandos"], comando_id, int(passo)))

    # --- Widget do Início --------------------------------------------------------------------------

    @widget("lembretes", "Lembretes", ordem=20)
    def _widget_lembretes(self, hoje: date) -> dict:
        with self._contas() as d:
            contas = d["contas"]
            livres = lv.em_aberto(d["livres"], hoje)
        anterior = hoje.replace(day=1) - timedelta(days=1)
        abertas = []
        for c in contas:
            if lb.situacao_no_mes(c, hoje.year, hoje.month, hoje) == lb.PAGA:
                continue
            vencimento = lb.vencimento_no_mes(c, hoje.year, hoje.month)
            abertas.append({"nome": c["nome"], "mes": f"{hoje:%Y-%m}", "vencimento": vencimento.isoformat(),
                            "venceu": vencimento < hoje, "perto": vencimento <= hoje + timedelta(days=1)})
        abertas.sort(key=lambda c: c["vencimento"])
        notas = self.notas_a_enviar()
        return {
            "abertas": abertas,
            "total": len(contas),
            "nao_pagas_mes_passado": [c["nome"] for c in contas
                                      if lb.situacao_no_mes(c, anterior.year, anterior.month, hoje) == lb.NAO_PAGA],
            "notas_enviar": {"sem_pasta": True} if notas.get("sem_pasta") else (
                {"erro": notas["erro"]} if "erro" in notas else {"qtd": len(notas["notas"])}),
            "livres": [{"id": x["id"], "titulo": x["titulo"], "observacao": x["observacao"], "quando": lv.quando(x)}
                       for x in livres],
        }
