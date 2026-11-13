"""Parte da API que cuida do WhatsApp."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from .. import config, sistema
from ..notas.leitor import Nota, ler_nome_arquivo
from ..nucleo import ApiBase, seguro
from ..planilha import MESES
from ..texto import normalizar
from . import dados as armazem
from . import lembretes as lb
from . import mensagens as msg


def responsavel(nota: Nota) -> str:
    """Quem recebe a nota. O nome do arquivo é o do responsável, mesmo com dependente."""
    lido = ler_nome_arquivo(nota.arquivo)
    return lido[1] if lido else nota.paciente


class WhatsappApi(ApiBase):
    def __init__(self):
        super().__init__()
        self._trava_dados = threading.Lock()

    @contextmanager
    def _dados(self):
        with self._trava_dados:
            caminho = config.caminho_whatsapp()
            dados = armazem.carregar(caminho)
            antes = json.dumps(dados, sort_keys=True)
            hoje = date.today()
            if not dados["inicio"]:
                dados["inicio"] = hoje.isoformat()
            # Depois do "antes": a data em que cada conta começou a ser acompanhada é gravada uma vez só.
            dados["contas"] = [lb.completar_conta(c, hoje) for c in dados["contas"]]
            yield dados
            if json.dumps(dados, sort_keys=True) != antes:
                armazem.salvar(caminho, dados)

    def _notas(self) -> list[Nota]:
        pasta = self._cfg["pasta_notas"]
        if not pasta or not Path(pasta).is_dir():
            raise ValueError("Escolha a pasta das notas primeiro.")
        return self._ler_notas(pasta).notas

    def _nota(self, numero: int) -> Nota:
        nota = next((n for n in self._notas() if n.numero == int(numero)), None)
        if nota is None:
            raise ValueError(f"Não encontrei a nota nº {numero} na pasta.")
        return nota

    def _abrir_conversa(self, telefone: str, texto: str) -> None:
        msg.abrir_conversa(telefone, texto, self._cfg["whatsapp_destino"])

    # --- Envio da nota ---------------------------------------------------------

    @seguro
    def whatsapp_a_enviar(self):
        if not self._cfg["pasta_notas"]:
            return {"sem_pasta": True}
        notas = self._notas()
        with self._dados() as d:
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
        with self._dados() as d:
            return {"numeros": [int(n) for n in d["enviadas"]]}

    @seguro
    def whatsapp_preparar_nota(self, numero: int):
        nota = self._nota(numero)
        nome = responsavel(nota)
        with self._dados() as d:
            contato = d["contatos"].get(normalizar(nome), {})
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
        with self._dados() as d:
            d["contatos"][normalizar(nome)] = {"nome": nome, "telefone": telefone}

        # O link do WhatsApp só leva texto: o PDF vai pela área de transferência.
        copiado = sistema.copiar_arquivo(caminho)
        self._abrir_conversa(telefone, mensagem)
        if not copiado:
            sistema.mostrar_na_pasta(caminho)
        return {"pdf_copiado": copiado}

    @seguro
    def whatsapp_marcar_enviada(self, numero: int, enviada: bool = True):
        with self._dados() as d:
            if enviada:
                d["enviadas"][str(int(numero))] = date.today().isoformat()
            else:
                d["enviadas"].pop(str(int(numero)), None)
        return {}

    # --- Contatos ---------------------------------------------------------------

    @seguro
    def whatsapp_contatos(self):
        with self._dados() as d:
            contatos = sorted(d["contatos"].values(), key=lambda c: normalizar(c["nome"]))
        return {"contatos": contatos}

    @seguro
    def whatsapp_salvar_contato(self, nome: str, telefone: str):
        nome = " ".join(str(nome).split())
        if not nome:
            return {"erro": "Diga o nome do contato."}
        telefone = msg.normalizar_telefone(telefone)
        with self._dados() as d:
            d["contatos"][normalizar(nome)] = {"nome": nome, "telefone": telefone}
        return self.whatsapp_contatos()

    @seguro
    def whatsapp_apagar_contato(self, nome: str):
        with self._dados() as d:
            d["contatos"].pop(normalizar(nome), None)
        return self.whatsapp_contatos()

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
        with self._dados() as d:
            return self._vista_contas(d["contas"])

    @seguro
    def whatsapp_salvar_conta(self, conta: dict, antiga: dict | None = None):
        with self._dados() as d:
            d["contas"] = lb.adicionar_conta(d["contas"], conta, antiga)
            return self._vista_contas(d["contas"])

    @seguro
    def whatsapp_apagar_conta(self, nome: str):
        with self._dados() as d:
            d["contas"] = lb.remover_conta(d["contas"], nome)
            return self._vista_contas(d["contas"])

    @seguro
    def whatsapp_marcar_paga(self, nome: str, mes: str, paga: bool = True):
        """`mes` é "AAAA-MM", o mês do vencimento."""
        with self._dados() as d:
            lb.marcar_paga(lb.buscar_conta(d["contas"], nome), str(mes)[:7], bool(paga), date.today())
            return self._vista_contas(d["contas"])

    @seguro
    def whatsapp_texto_lembrete(self, contas: list[dict]):
        """Refaz a mensagem do lembrete sem as contas que acabaram de ser marcadas como pagas."""
        return {"mensagem": msg.mensagem_de_lembrete(self._cfg["assistente_nome"], self._cfg["lembrete_nome"], contas)}

    @seguro
    def whatsapp_lembretes(self, forcar: bool = False):
        """Lembretes da primeira abertura do dia. `forcar` mostra os de hoje de novo."""
        hoje = date.today()
        with self._dados() as d:
            ultima = date.fromisoformat(d["ultima_abertura"]) if d["ultima_abertura"] else None
            if not forcar:
                if ultima == hoje:
                    return {"mostrar": False}
                d["ultima_abertura"] = hoje.isoformat()
            desde = None if forcar else ultima
            contas = lb.contas_a_avisar(d["contas"], hoje, desde)

        fechamento = lb.aviso_de_fechamento(self._cfg["lembrete_fechamento_dia"], hoje, desde)
        destinatario = self._cfg["lembrete_nome"]
        return {
            "mostrar": bool(contas or fechamento),
            "contas": contas,
            "fechamento": fechamento,
            "destinatario": destinatario,
            "mensagem": msg.mensagem_de_lembrete(self._cfg["assistente_nome"], destinatario, contas),
        }

    @seguro
    def whatsapp_enviar_lembrete(self, mensagem: str):
        if not self._cfg["lembrete_telefone"]:
            return {"sem_contato": True}
        self._abrir_conversa(msg.normalizar_telefone(self._cfg["lembrete_telefone"]), mensagem)
        return {}
