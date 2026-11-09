"""As três mensagens que podem ser mandadas para o paciente ou para o responsável.

Com `responsavel`, a conversa é com ele e o paciente é citado pelo primeiro nome.
"""

from __future__ import annotations

from datetime import date

from ..planilha import MESES
from ..whatsapp.mensagens import assinatura, primeiro_nome

AGENDAR = "agendar"
COBRAR = "cobrar"
RETORNO = "retorno"


def reais(centavos: int) -> str:
    inteiro, resto = divmod(centavos, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def _inicio(assistente: str, nome: str, responsavel: str) -> str:
    return f"{assinatura(assistente)}Olá, {primeiro_nome(responsavel or nome)}.\n"


def _mes(hoje: date) -> str:
    return MESES[hoje.month - 1].lower()


def agendar(assistente: str, nome: str, hoje: date, responsavel: str = "") -> str:
    o_que = f"a manutenção do aparelho de {primeiro_nome(nome)}" if responsavel else "a sua manutenção do aparelho"
    return (
        f"{_inicio(assistente, nome, responsavel)}"
        f"Vamos agendar {o_que} para {_mes(hoje)}? "
        "Me diga qual dia e horário ficam melhores para você."
    )


def cobrar(assistente: str, nome: str, hoje: date, valor_centavos: int | None, chave_pix: str,
           responsavel: str = "") -> str:
    """Sem chave Pix não há o que mandar: devolve vazio para a tela pedir a chave."""
    chave = chave_pix.strip()
    if not chave:
        return ""
    de_quem = f" de {primeiro_nome(nome)}, referente a {_mes(hoje)}" if responsavel else f" de {_mes(hoje)}"
    valor = f", no valor de {reais(valor_centavos)}" if valor_centavos else ""
    return (
        f"{_inicio(assistente, nome, responsavel)}"
        f"Segue a chave Pix para o pagamento da manutenção{de_quem}{valor}:\n\n"
        f"{chave}\n\n"
        "Depois me envie o comprovante, por favor."
    )


def retorno(assistente: str, nome: str, responsavel: str = "") -> str:
    o_que = f"o retorno de {primeiro_nome(nome)}" if responsavel else "o seu retorno"
    return (
        f"{_inicio(assistente, nome, responsavel)}"
        f"Está na hora de agendar {o_que}. Me diga qual dia e horário ficam melhores para você."
    )


def todas(assistente: str, nome: str, hoje: date, valor_centavos: int | None, chave_pix: str,
          responsavel: str = "") -> dict[str, str]:
    return {
        AGENDAR: agendar(assistente, nome, hoje, responsavel),
        COBRAR: cobrar(assistente, nome, hoje, valor_centavos, chave_pix, responsavel),
        RETORNO: retorno(assistente, nome, responsavel),
    }
