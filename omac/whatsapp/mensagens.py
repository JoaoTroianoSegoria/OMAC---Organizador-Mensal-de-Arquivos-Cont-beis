"""Telefones, links do WhatsApp e o texto das mensagens."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import quote

from .. import sistema

SERVICO_PADRAO = "tratamento odontológico"


class TelefoneInvalido(ValueError):
    """O telefone não tem o tamanho de um número brasileiro com DDD."""


def normalizar_telefone(telefone: str) -> str:
    """Devolve só os dígitos, com o 55 do Brasil na frente."""
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


def primeiro_nome(nome: str) -> str:
    partes = nome.split()
    return partes[0].title() if partes else ""


def mensagem_da_nota(assistente: str, nome: str, competencia: date, servico: str = SERVICO_PADRAO) -> str:
    return (
        f"{assinatura(assistente)}Olá, {primeiro_nome(nome)}.\n"
        f"Segue a nota fiscal referente ao {servico} realizado dia {competencia:%d/%m}."
    )


def _dias(datas: list[date]) -> str:
    dias = [f"{d:%d/%m}" for d in sorted(set(datas))]
    return dias[0] if len(dias) == 1 else f"{', '.join(dias[:-1])} e {dias[-1]}"


def mensagem_das_notas(assistente: str, nome: str, notas: list[tuple[str, date]],
                       servico: str = SERVICO_PADRAO) -> str:
    """Várias notas numa mensagem só. notas = [(paciente, competência), ...]."""
    if len(notas) == 1:
        return mensagem_da_nota(assistente, nome, notas[0][1], servico)
    inicio = f"{assinatura(assistente)}Olá, {primeiro_nome(nome)}.\n"
    pacientes = {p for p, _ in notas}
    if len(pacientes) == 1:
        datas = [d for _, d in notas]
        palavra = "dia" if len(set(datas)) == 1 else "nos dias"
        return f"{inicio}Seguem as {len(notas)} notas fiscais referentes ao {servico} realizado {palavra} {_dias(datas)}."
    linhas = [f"• {p.title()}: {_dias([d for q, d in notas if q == p])}" for p in sorted(pacientes)]
    return "\n".join([f"{inicio}Seguem as {len(notas)} notas fiscais referentes ao {servico}:", *linhas])


def mensagem_de_lembrete(assistente: str, destinatario: str, contas: list[dict]) -> str:
    saudacao = f"Olá, {destinatario.strip()}." if destinatario.strip() else "Olá."
    linhas = [f"• {c['nome']}: {c['situacao']}" for c in contas]
    return "\n".join([f"{assinatura(assistente)}{saudacao}", "Lembrete de pagamento:", *linhas])
