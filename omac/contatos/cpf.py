"""CPF de um contato: aceitar como a pessoa escrever, conferir os dígitos e mostrar no padrão.

Fica guardado só com os 11 números, no computador (contatos.json), e aparece como
000.000.000-00. O CPF que está nas notas já emitidas vira sugestão: só entra no
contato quando alguém confirma.
"""

from __future__ import annotations

import re

from ..notas.leitor import responsavel
from ..texto import mesma_pessoa, normalizar


class CpfInvalido(ValueError):
    """Não tem 11 números, ou os dígitos verificadores não batem."""


def digitos(texto) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def confere(numeros: str) -> bool:
    """A conta dos dois dígitos verificadores. Todos iguais (111.111.111-11) não vale."""
    if not re.fullmatch(r"\d{11}", numeros) or len(set(numeros)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(numeros[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = soma * 10 % 11 % 10
        if digito != int(numeros[tamanho]):
            return False
    return True


def limpar(texto, de_quem: str = "") -> str:
    """Os 11 números, de qualquer jeito que vier escrito. Vazio continua vazio."""
    if not str(texto or "").strip():
        return ""
    numeros = digitos(texto)
    sufixo = f" {de_quem}" if de_quem else ""
    if len(numeros) != 11:
        raise CpfInvalido(f"O CPF{sufixo} precisa ter 11 números (tem {len(numeros)}).")
    if not confere(numeros):
        raise CpfInvalido(f"O CPF{sufixo} não confere. Veja se algum número foi digitado errado.")
    return numeros


def formatar(numeros: str) -> str:
    n = digitos(numeros)
    return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}" if len(n) == 11 else str(numeros or "")


# --- Sugestão a partir das notas -------------------------------------------------------


def _nomes_da_nota(nota) -> list[str]:
    return [n for n in (getattr(nota, "tomador", ""), responsavel(nota)) if n]


def sugestao(nome: str, notas: list) -> dict | None:
    """O CPF da nota mais recente em que essa pessoa é o tomador: {"cpf", "numero"}.

    Vale o nome igual (do arquivo ou do tomador) e, se não houver, um sobrenome a mais
    ou a menos. Nota sem CPF válido do tomador (CNPJ, campo vazio) não conta.
    """
    chave = normalizar(nome)
    iguais, parecidas = [], []
    for nota in notas or []:
        numeros = getattr(nota, "cpf_tomador", "")
        if not numeros or not confere(numeros) or getattr(nota, "cancelada", False):
            continue
        if getattr(nota, "dependente", False) and normalizar(nota.paciente) == chave:
            continue  # a pessoa é o dependente: o CPF da nota é de outra pessoa
        nomes = _nomes_da_nota(nota)
        if any(normalizar(n) == chave for n in nomes):
            iguais.append(nota)
        elif any(mesma_pessoa(n, nome) for n in nomes):
            parecidas.append(nota)
    achadas = iguais or parecidas
    if not achadas:
        return None
    # Pessoas diferentes com nomes parecidos dariam CPFs diferentes: aí não sugere nada.
    if not iguais and len({n.cpf_tomador for n in parecidas}) > 1:
        return None
    nota = max(achadas, key=lambda n: (n.emissao, n.numero))
    return {"cpf": nota.cpf_tomador, "numero": nota.numero}
