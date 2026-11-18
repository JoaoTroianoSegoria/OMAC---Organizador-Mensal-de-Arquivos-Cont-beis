"""Parte da API que envia as notas ao paciente pelo WhatsApp ("Notas a enviar").

O link do WhatsApp só leva texto: o PDF vai pela área de transferência, e quem aperta
enviar é sempre a pessoa.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path

from .. import sistema
from ..contatos import contatos as ct
from ..dados import esquema
from ..nucleo import ApiBase, seguro
from ..whatsapp import mensagens as msg
from .leitor import Nota, ler_nome_arquivo


def responsavel(nota: Nota) -> str:
    """Quem recebe a nota. O nome do arquivo é o do responsável, mesmo com dependente."""
    lido = ler_nome_arquivo(nota.arquivo)
    return lido[1] if lido else nota.paciente


class EnvioNotasApi(ApiBase):
    @contextmanager
    def _enviadas(self):
        with self._armazem.editar(esquema.NOTAS_ENVIADAS) as d:
            if not d["inicio"]:
                d["inicio"] = date.today().isoformat()
            yield d

    def _nota(self, numero: int) -> Nota:
        nota = next((n for n in self._servico_notas.atual().notas if n.numero == int(numero)), None)
        if nota is None:
            raise ValueError(f"Não encontrei a nota nº {numero} na pasta.")
        return nota

    @seguro
    def notas_a_enviar(self):
        if not self._cfg["pasta_notas"]:
            return {"sem_pasta": True}
        notas = self._servico_notas.atual().notas
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
    def notas_enviadas(self):
        with self._enviadas() as d:
            return {"numeros": [int(n) for n in d["enviadas"]]}

    @seguro
    def notas_preparar_envio(self, numero: int):
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
    def notas_enviar(self, numero: int, telefone: str, mensagem: str):
        nota = self._nota(numero)
        telefone = msg.normalizar_telefone(telefone)
        nome = responsavel(nota)
        caminho = Path(self._cfg["pasta_notas"]) / nota.arquivo
        # Quem recebe a nota vira contato (ou ganha o telefone que acabou de ser usado).
        with self._armazem.editar(esquema.CONTATOS) as d:
            ct.obter(d["contatos"], nome)["telefone"] = telefone

        copiado = sistema.copiar_arquivo(caminho)
        msg.abrir_conversa(telefone, mensagem, self._cfg["whatsapp_destino"])
        if not copiado:
            sistema.mostrar_na_pasta(caminho)
        return {"pdf_copiado": copiado}

    @seguro
    def notas_marcar_enviada(self, numero: int, enviada: bool = True):
        with self._enviadas() as d:
            if enviada:
                d["enviadas"][str(int(numero))] = date.today().isoformat()
            else:
                d["enviadas"].pop(str(int(numero)), None)
        return {}
