"""As [variáveis] das mensagens: o que cada uma quer dizer, os valores de cada uma e a troca no texto.

Os textos (padrões e os da pessoa) ficam no catálogo (catalogo.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..planilha import MESES
from .mensagens import assinatura

# nome → o que é (aparece nos botões e na ajuda da tela). A ordem é a dos botões.
VARIAVEIS = {
    "nome-do-responsavel": "Nome de quem recebe a mensagem",
    "primeiro-nome-do-responsavel": "Só o primeiro nome de quem recebe",
    "nome-do-paciente": "Nome do paciente (o dependente, se houver)",
    "primeiro-nome-do-paciente": "Só o primeiro nome do paciente",
    "data-competencia": "Data de competência (30/10)",
    "mes-competencia": "Mês da competência (outubro)",
    "data-de-emissao": "Data de emissão (30/10)",
    "numero-da-nota": "Número da nota",
    "valor": "Valor da nota (R$ 180,00)",
    "assinatura": "*Assistente Fulano:* (o nome das Configurações)",
}
VARIAVEIS_DA_COBRANCA = {
    "nome-do-responsavel": "Nome de quem recebe a mensagem",
    "primeiro-nome-do-responsavel": "Só o primeiro nome de quem recebe",
    "nome-do-paciente": "Nome do paciente atendido",
    "primeiro-nome-do-paciente": "Só o primeiro nome do paciente",
    "data-do-atendimento": "Dia do atendimento (21/11)",
    "tratamento": "O tratamento da ficha (Manutenção)",
    "valor": "Valor do atendimento (R$ 180,00)",
    "chave-pix": "A chave Pix das Configurações",
    "assinatura": "*Assistente Fulano:* (o nome das Configurações)",
}
VARIAVEIS_SO_DE_VARIAS = {
    "quantidade-de-notas": "Quantas notas vão juntas",
    "lista-das-notas": "Uma linha por paciente, com as datas",
}
VARIAVEIS_DO_TRATAMENTO = {
    "nome-do-responsavel": "Nome de quem recebe a mensagem",
    "primeiro-nome-do-responsavel": "Só o primeiro nome de quem recebe",
    "nome-do-paciente": "Nome do paciente",
    "primeiro-nome-do-paciente": "Só o primeiro nome do paciente",
    "mes-atual": "O mês de hoje (novembro)",
    "assinatura": "*Assistente Fulano:* (o nome das Configurações)",
}
VARIAVEIS_DA_CONSULTA = {"dia-da-consulta": "O dia marcado (sexta-feira, 04/12)"}
VARIAVEIS_DO_PIX = {
    "valor": "Valor da manutenção (R$ 180,00)",
    "chave-pix": "A chave Pix das Configurações",
}
VARIAVEIS_DO_LEMBRETE = {
    "nome-de-quem-recebe": "Nome de quem recebe o lembrete",
    "primeiro-nome-de-quem-recebe": "Só o primeiro nome",
    "assinatura": "*Assistente Fulano:* (o nome das Configurações)",
}
VARIAVEIS_DAS_CONTAS = {"lista-das-contas": "Uma linha por conta, com o vencimento"}
VARIAVEIS_DO_LEMBRETE_LIVRE = {
    "titulo": "O que lembrar",
    "observacao": "A observação do lembrete (se tiver)",
}

_RE_VARIAVEL = re.compile(r"\[([^\[\]\n]{1,40})\]")
_MINUSCULAS = {"da", "de", "do", "das", "dos", "e"}


class ModeloInvalido(ValueError):
    """Modelo vazio ou com variável que não existe."""


@dataclass(frozen=True)
class NotaDaMensagem:
    """O que a mensagem precisa de uma nota (vem de leitor.Nota)."""

    numero: int
    paciente: str
    competencia: date
    emissao: date
    valor: Decimal


def preencher(texto: str, valores: dict[str, str]) -> str:
    """Troca cada [variável] pelo valor. O que não for variável conhecida fica como está."""
    def trocar(m: re.Match) -> str:
        nome = m.group(1).strip().lower()
        return valores[nome] if nome in valores else m.group(0)

    return _RE_VARIAVEL.sub(trocar, texto)


def desconhecidas(texto: str, conhecidas) -> list[str]:
    """As [variáveis] do texto que não estão em `conhecidas`, sem repetir."""
    vistas = []
    for m in _RE_VARIAVEL.finditer(str(texto or "")):
        nome = m.group(1).strip().lower()
        if nome not in conhecidas and nome not in vistas:
            vistas.append(nome)
    return vistas


# --- Os valores ------------------------------------------------------------------------


def nome_bonito(nome: str) -> str:
    """MARIA DA SILVA → Maria da Silva."""
    palavras = str(nome or "").split()
    return " ".join(p.lower() if i and p.lower() in _MINUSCULAS else p[:1].upper() + p[1:].lower()
                    for i, p in enumerate(palavras))


def _primeiro(nome: str) -> str:
    return nome_bonito(nome).split(" ")[0] if str(nome or "").split() else ""


def _juntar(itens: list[str]) -> str:
    itens = [i for i in itens if i]
    if len(itens) <= 1:
        return "".join(itens)
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


def _dias(datas: list[date]) -> str:
    return _juntar([f"{d:%d/%m}" for d in sorted(set(datas))])


def _meses(datas: list[date]) -> str:
    return _juntar([MESES[mes - 1].lower() for _, mes in sorted({(d.year, d.month) for d in datas})])


def _reais(valor: Decimal) -> str:
    inteiro, centavos = f"{Decimal(valor):.2f}".split(".")
    return f"R$ {int(inteiro):,}".replace(",", ".") + f",{centavos}"


def valores(assistente: str, destinatario: str, notas: list[NotaDaMensagem]) -> dict[str, str]:
    """Os valores das variáveis para uma nota ou várias (aí datas, números e nomes vão juntos)."""
    pacientes = []
    for n in notas:
        if nome_bonito(n.paciente) not in pacientes:
            pacientes.append(nome_bonito(n.paciente))
    linhas = [f"• {p}: {_dias([n.competencia for n in notas if nome_bonito(n.paciente) == p])}"
              for p in sorted(pacientes)]
    return {
        "assinatura": assinatura(assistente),
        "nome-do-responsavel": nome_bonito(destinatario),
        "primeiro-nome-do-responsavel": _primeiro(destinatario),
        "nome-do-paciente": _juntar(pacientes),
        "primeiro-nome-do-paciente": _juntar([_primeiro(p) for p in pacientes]),
        "data-competencia": _dias([n.competencia for n in notas]),
        "mes-competencia": _meses([n.competencia for n in notas]),
        "data-de-emissao": _dias([n.emissao for n in notas]),
        "numero-da-nota": _juntar([str(n.numero) for n in sorted(notas, key=lambda n: n.numero)]),
        "valor": _reais(sum((Decimal(n.valor) for n in notas), Decimal(0))),
        "quantidade-de-notas": str(len(notas)),
        "lista-das-notas": "\n".join(linhas),
    }


# --- Cobrança de um atendimento (Atendimentos → botão de cobrar) -----------------------


def valores_cobranca(assistente: str, destinatario: str, paciente: str, dia: date, tratamento: str,
                     valor_centavos: int | None, chave_pix: str) -> dict[str, str]:
    return {
        "assinatura": assinatura(assistente),
        "nome-do-responsavel": nome_bonito(destinatario),
        "primeiro-nome-do-responsavel": _primeiro(destinatario),
        "nome-do-paciente": nome_bonito(paciente),
        "primeiro-nome-do-paciente": _primeiro(paciente),
        "data-do-atendimento": f"{dia:%d/%m}",
        "tratamento": " ".join(str(tratamento or "").split()),
        "valor": _reais(Decimal(valor_centavos) / 100) if valor_centavos is not None else "",
        "chave-pix": " ".join(str(chave_pix or "").split()),
    }


def limpar(texto: str) -> str:
    """O que sobra quando um dado falta: "()" sem tratamento, ", no valor de ." sem valor,
    "Olá, ." sem nome e linhas vazias no fim (observação em branco)."""
    texto = re.sub(r"\s*\(\s*\)", "", texto)
    texto = re.sub(r",?\s*no valor de\s*(?=[.,:\n]|$)", "", texto)
    texto = re.sub(r",[ \t]*(?=[.!?])", "", texto)
    return texto.strip()


# --- Tratamentos (ortodontia) e lembretes ----------------------------------------------


DIAS_DA_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def data_da_consulta(dia: str) -> str:
    """"2026-12-04" → "sexta-feira, 04/12"."""
    d = date.fromisoformat(dia)
    return f"{DIAS_DA_SEMANA[d.weekday()]}, {d:%d/%m}"


def valores_tratamento(assistente: str, destinatario: str, paciente: str, hoje: date, consulta: str = "",
                       valor_centavos: int | None = None, chave_pix: str = "") -> dict[str, str]:
    return {
        "assinatura": assinatura(assistente),
        "nome-do-responsavel": nome_bonito(destinatario),
        "primeiro-nome-do-responsavel": _primeiro(destinatario),
        "nome-do-paciente": nome_bonito(paciente),
        "primeiro-nome-do-paciente": _primeiro(paciente),
        "mes-atual": MESES[hoje.month - 1].lower(),
        "dia-da-consulta": data_da_consulta(consulta) if consulta else "",
        "valor": _reais(Decimal(valor_centavos) / 100) if valor_centavos else "",
        "chave-pix": " ".join(str(chave_pix or "").split()),
    }


def valores_lembrete(assistente: str, destinatario: str, contas: list[dict] | None = None,
                     titulo: str = "", observacao: str = "") -> dict[str, str]:
    """O nome vai como está no contato (pode ser "Dra. Fulana")."""
    nome = " ".join(str(destinatario or "").split())
    return {
        "assinatura": assinatura(assistente),
        "nome-de-quem-recebe": nome,
        "primeiro-nome-de-quem-recebe": nome.split(" ")[0] if nome else "",
        "lista-das-contas": "\n".join(f"• {c['nome']}: {c['situacao']}" for c in contas or []),
        "titulo": str(titulo or "").strip(),
        "observacao": str(observacao or "").strip(),
    }
