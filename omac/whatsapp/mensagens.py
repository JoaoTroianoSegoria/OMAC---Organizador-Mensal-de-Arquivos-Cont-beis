"""Telefones, links do WhatsApp e a assinatura. Os textos das mensagens ficam no catálogo."""

from __future__ import annotations

import re
from urllib.parse import quote

from .. import sistema

class TelefoneInvalido(ValueError):
    """O telefone não tem o tamanho de um número brasileiro com DDD."""


def normalizar_telefone(telefone: str) -> str:
    """Devolve só os dígitos, com o 55 do Brasil na frente. Fora os números, só vale o que se usa
    para escrever um telefone: espaço, parênteses, traço, ponto e o + do 55."""
    if re.search(r"[^\d\s()+.-]", telefone or ""):
        raise TelefoneInvalido("O telefone só pode ter números (e espaço, parênteses ou traço), "
                               "como (61) 90000-0000.")
    digitos = re.sub(r"\D", "", telefone or "").lstrip("0")
    if len(digitos) in (10, 11):
        digitos = f"55{digitos}"
    if len(digitos) not in (12, 13) or not digitos.startswith("55"):
        raise TelefoneInvalido("Confira o telefone: use o DDD e o número, por exemplo (61) 90000-0000.")
    return digitos


def links(telefone: str, texto: str, destino: str) -> list[str]:
    """Links para abrir a conversa, em ordem de preferência."""
    t = quote(texto, safe="")
    if destino == "web":
        return [f"https://web.whatsapp.com/send?phone={telefone}&text={t}"]
    # O wa.me é a segunda opção, para quando o aplicativo não está instalado.
    return [f"whatsapp://send?phone={telefone}&text={t}", f"https://wa.me/{telefone}?text={t}"]


def abrir_conversa(telefone: str, texto: str, destino: str) -> None:
    """Tenta cada link até um abrir. Quem aperta enviar é sempre a pessoa."""
    erro = None
    for link in links(telefone, texto, destino):
        try:
            sistema.abrir_link(link)
            return
        except OSError as e:
            erro = e
    raise ValueError("Não consegui abrir o WhatsApp.") from erro


def assinatura(assistente: str) -> str:
    assistente = assistente.strip()
    return f"*Assistente {assistente}:* " if assistente else ""
