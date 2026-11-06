"""As três mensagens que podem ser mandadas para o paciente."""

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


def _inicio(assistente: str, nome: str) -> str:
    return f"{assinatura(assistente)}Olá, {primeiro_nome(nome)}.\n"


def agendar(assistente: str, nome: str, hoje: date) -> str:
    return (
        f"{_inicio(assistente, nome)}"
        f"Vamos agendar a sua manutenção do aparelho de {MESES[hoje.month - 1].lower()}? "
        "Me diga qual dia e horário ficam melhores para você."
    )


def cobrar(assistente: str, nome: str, hoje: date, valor_centavos: int | None, chave_pix: str) -> str:
    """Sem chave Pix não há o que mandar: devolve vazio para a tela pedir a chave."""
    chave = chave_pix.strip()
    if not chave:
        return ""
    valor = f", no valor de {reais(valor_centavos)}" if valor_centavos else ""
    return (
        f"{_inicio(assistente, nome)}"
        f"Segue a chave Pix para o pagamento da manutenção de {MESES[hoje.month - 1].lower()}{valor}:\n\n"
        f"{chave}\n\n"
        "Depois me envie o comprovante, por favor."
    )


def retorno(assistente: str, nome: str) -> str:
    return (
        f"{_inicio(assistente, nome)}"
        "Está na hora de agendar o seu retorno. Me diga qual dia e horário ficam melhores para você."
    )


def todas(assistente: str, nome: str, hoje: date, valor_centavos: int | None, chave_pix: str) -> dict[str, str]:
    return {
        AGENDAR: agendar(assistente, nome, hoje),
        COBRAR: cobrar(assistente, nome, hoje, valor_centavos, chave_pix),
        RETORNO: retorno(assistente, nome),
    }
