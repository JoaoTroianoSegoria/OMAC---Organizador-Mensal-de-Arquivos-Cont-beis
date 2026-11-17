"""Parte da API que cuida do WhatsApp."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from .. import sistema
from ..contatos import contatos as ct
from ..dados import esquema
from ..inicio.registro import widget
from ..notas.leitor import Nota, ler_nome_arquivo
from ..nucleo import ApiBase, seguro
from ..planilha import MESES
from ..texto import normalizar
from . import lembretes as lb
from . import mensagens as msg


def responsavel(nota: Nota) -> str:
    """Quem recebe a nota. O nome do arquivo é o do responsável, mesmo com dependente."""
    lido = ler_nome_arquivo(nota.arquivo)
    return lido[1] if lido else nota.paciente


class WhatsappApi(ApiBase):
    @contextmanager
    def _contas(self):
        """lembretes.json, com cada conta completa (pagas e desde quando é acompanhada)."""
        with self._armazem.editar(esquema.LEMBRETES) as d:
            hoje = date.today()
            d["contas"] = [lb.completar_conta(c, hoje) for c in d["contas"]]
            yield d

    @contextmanager
    def _enviadas(self):
        with self._armazem.editar(esquema.NOTAS_ENVIADAS) as d:
            if not d["inicio"]:
                d["inicio"] = date.today().isoformat()
            yield d

    def _notas(self) -> list[Nota]:
        return self._servico_notas.atual().notas

    def _nota(self, numero: int) -> Nota:
        nota = next((n for n in self._notas() if n.numero == int(numero)), None)
        if nota is None:
            raise ValueError(f"Não encontrei a nota nº {numero} na pasta.")
        return nota

    def _destinatario(self) -> dict | None:
        """O contato que recebe os lembretes de contas."""
        destino = self._armazem.ler(esquema.LEMBRETES)["destinatario"]
        contatos = self._armazem.ler(esquema.CONTATOS)["contatos"]
        return next((c for c in contatos if c["id"] == destino), None) if destino else None

    def _abrir_conversa(self, telefone: str, texto: str) -> None:
        msg.abrir_conversa(telefone, texto, self._cfg["whatsapp_destino"])

    # --- Envio da nota ---------------------------------------------------------

    @seguro
    def whatsapp_a_enviar(self):
        if not self._cfg["pasta_notas"]:
            return {"sem_pasta": True}
        notas = self._notas()
        with self._enviadas() as d:
            inicio, enviadas = d["inicio"], d["enviadas"]
        pendentes = [n for n in notas if n.emissao.isoformat() >= inicio and str(n.numero) not in enviadas]
        pendentes.sort(key=lambda n: n.numero)
        return {
            "inicio": inicio,
            "notas": [{
                "numero": n.numero,
                "responsavel": responsavel(n),
                "dependente": n.paciente if n.dependente else "",
                "valor_centavos": int(n.valor * 100),
                "emissao": n.emissao.isoformat(),
                "competencia": n.competencia.isoformat(),
            } for n in pendentes],
        }

    @seguro
    def whatsapp_enviadas(self):
        with self._enviadas() as d:
            return {"numeros": [int(n) for n in d["enviadas"]]}

    @seguro
    def whatsapp_preparar_nota(self, numero: int):
        nota = self._nota(numero)
        nome = responsavel(nota)
        contato = ct.por_nome(self._lista_de_contatos(), nome) or {}
        return {
            "numero": nota.numero,
            "nome": nome,
            "telefone": contato.get("telefone", ""),
            "mensagem": msg.mensagem_da_nota(self._cfg["assistente_nome"], nome, nota.competencia),
        }

    @seguro
    def whatsapp_enviar_nota(self, numero: int, telefone: str, mensagem: str):
        nota = self._nota(numero)
        telefone = msg.normalizar_telefone(telefone)
        nome = responsavel(nota)
        caminho = Path(self._cfg["pasta_notas"]) / nota.arquivo
        # Quem recebe a nota vira contato (ou ganha o telefone que acabou de ser usado).
        with self._armazem.editar(esquema.CONTATOS) as d:
            contatos = d["contatos"]
            ct.obter(contatos, nome)["telefone"] = telefone

        # O link do WhatsApp só leva texto: o PDF vai pela área de transferência.
        copiado = sistema.copiar_arquivo(caminho)
        self._abrir_conversa(telefone, mensagem)
        if not copiado:
            sistema.mostrar_na_pasta(caminho)
        return {"pdf_copiado": copiado}

    @seguro
    def whatsapp_marcar_enviada(self, numero: int, enviada: bool = True):
        with self._enviadas() as d:
            if enviada:
                d["enviadas"][str(int(numero))] = date.today().isoformat()
            else:
                d["enviadas"].pop(str(int(numero)), None)
        return {}

    # --- Contas e lembretes -----------------------------------------------------

    def _vista_contas(self, contas: list[dict]) -> dict:
        hoje = date.today()
        anterior = hoje.replace(day=1) - timedelta(days=1)
        vista = []
        for c in sorted(contas, key=lambda c: (c["dia"], normalizar(c["nome"]))):
            vencimento = lb.vencimento_no_mes(c, hoje.year, hoje.month)
            vista.append({
                **c,
                "este_mes": lb.situacao_no_mes(c, hoje.year, hoje.month, hoje),
                "mes_passado": lb.situacao_no_mes(c, anterior.year, anterior.month, hoje),
                "vencimento": vencimento.isoformat(),
                "venceu": vencimento < hoje,
            })
        return {
            "contas": vista,
            "mes": f"{hoje:%Y-%m}",
            "nome_mes": MESES[hoje.month - 1],
            "nome_mes_passado": MESES[anterior.month - 1],
        }

    @seguro
    def whatsapp_contas(self):
        with self._contas() as d:
            return self._vista_contas(d["contas"])

    @seguro
    def whatsapp_salvar_conta(self, conta: dict, antiga: dict | None = None):
        with self._contas() as d:
            d["contas"] = lb.adicionar_conta(d["contas"], conta, antiga)
            return self._vista_contas(d["contas"])

    @seguro
    def whatsapp_apagar_conta(self, nome: str):
        with self._contas() as d:
            d["contas"] = lb.remover_conta(d["contas"], nome)
            return self._vista_contas(d["contas"])

    @seguro
    def whatsapp_marcar_paga(self, nome: str, mes: str, paga: bool = True):
        """`mes` é "AAAA-MM", o mês do vencimento."""
        with self._contas() as d:
            lb.marcar_paga(lb.buscar_conta(d["contas"], nome), str(mes)[:7], bool(paga), date.today())
            return self._vista_contas(d["contas"])

    @seguro
    def whatsapp_texto_lembrete(self, contas: list[dict]):
        """Refaz a mensagem do lembrete sem as contas que acabaram de ser marcadas como pagas."""
        destino = self._destinatario()
        return {"mensagem": msg.mensagem_de_lembrete(self._cfg["assistente_nome"], destino["nome"] if destino else "", contas)}

    @seguro
    def whatsapp_lembretes(self, forcar: bool = False):
        """Lembretes da primeira abertura do dia. `forcar` mostra os de hoje de novo."""
        hoje = date.today()
        with self._contas() as d:
            ultima = date.fromisoformat(d["ultima_abertura"]) if d["ultima_abertura"] else None
            if not forcar:
                if ultima == hoje:
                    return {"mostrar": False}
                d["ultima_abertura"] = hoje.isoformat()
            desde = None if forcar else ultima
            contas = lb.contas_a_avisar(d["contas"], hoje, desde)

        fechamento = lb.aviso_de_fechamento(self._cfg["lembrete_fechamento_dia"], hoje, desde)
        destino = self._destinatario()
        destinatario = destino["nome"] if destino else ""
        return {
            "mostrar": bool(contas or fechamento),
            "contas": contas,
            "fechamento": fechamento,
            "destinatario": destinatario,
            "mensagem": msg.mensagem_de_lembrete(self._cfg["assistente_nome"], destinatario, contas),
        }

    @seguro
    def whatsapp_enviar_lembrete(self, mensagem: str):
        destino = self._destinatario()
        if not destino or not destino["telefone"]:
            return {"sem_contato": True, "nome": destino["nome"] if destino else ""}
        self._abrir_conversa(destino["telefone"], mensagem)
        return {}

    # --- Quem recebe os lembretes (Configurações) --------------------------------------------

    @seguro
    def whatsapp_destinatario(self):
        destino = self._destinatario()
        return {"contato": destino, "nomes": sorted(self._nomes_dos_contatos().values(), key=normalizar)}

    @seguro
    def whatsapp_definir_destinatario(self, nome: str):
        """Escolhe o contato pelo nome; "" desliga. Um nome que não existe vira contato novo."""
        nome = " ".join(str(nome or "").split())
        contato_id = ""
        if nome:
            with self._armazem.editar(esquema.CONTATOS) as d:
                contatos = d["contatos"]
                contato_id = ct.obter(contatos, nome)["id"]
        with self._armazem.editar(esquema.LEMBRETES) as d:
            d["destinatario"] = contato_id
        return self.whatsapp_destinatario()

    # --- Widget do Início --------------------------------------------------------------------

    @widget("lembretes", "Lembretes", ordem=20)
    def _widget_lembretes(self, hoje: date) -> dict:
        with self._contas() as d:
            contas = d["contas"]
        anterior = hoje.replace(day=1) - timedelta(days=1)
        abertas = []
        for c in contas:
            if lb.situacao_no_mes(c, hoje.year, hoje.month, hoje) == lb.PAGA:
                continue
            vencimento = lb.vencimento_no_mes(c, hoje.year, hoje.month)
            abertas.append({"nome": c["nome"], "mes": f"{hoje:%Y-%m}", "vencimento": vencimento.isoformat(),
                            "venceu": vencimento < hoje, "perto": vencimento <= hoje + timedelta(days=1)})
        abertas.sort(key=lambda c: c["vencimento"])
        notas = self.whatsapp_a_enviar()
        return {
            "abertas": abertas,
            "total": len(contas),
            "nao_pagas_mes_passado": [c["nome"] for c in contas
                                      if lb.situacao_no_mes(c, anterior.year, anterior.month, hoje) == lb.NAO_PAGA],
            "notas_enviar": {"sem_pasta": True} if notas.get("sem_pasta") else (
                {"erro": notas["erro"]} if "erro" in notas else {"qtd": len(notas["notas"])}),
        }
