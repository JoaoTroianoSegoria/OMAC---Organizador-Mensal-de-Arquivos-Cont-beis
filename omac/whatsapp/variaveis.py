"""Mensagem da nota com variáveis: a pessoa escreve o texto do jeito dela e põe [variáveis] no meio.

Três modelos (Configurações → WhatsApp): uma nota, várias notas juntas e a cobrança de um
atendimento (1.12.0). Vazio nas Configurações quer dizer o padrão.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..planilha import MESES
from .mensagens import assinatura

NOTA, NOTAS, COBRANCA = "nota", "notas", "cobranca"
CHAVES = {NOTA: "mensagem_nota", NOTAS: "mensagem_notas", COBRANCA: "mensagem_cobranca"}

MODELO_NOTA = ("[assinatura]Olá, [primeiro-nome-do-responsavel].\n"
               "Segue a nota fiscal referente ao tratamento odontológico realizado dia [data-competencia].")
MODELO_NOTAS = ("[assinatura]Olá, [primeiro-nome-do-responsavel].\n"
                "Seguem as [quantidade-de-notas] notas fiscais referentes ao tratamento odontológico:\n"
                "[lista-das-notas]")
MODELO_COBRANCA = ("[assinatura]Olá, [primeiro-nome-do-responsavel].\n"
                   "Passando para lembrar do pagamento do atendimento de [primeiro-nome-do-paciente] "
                   "em [data-do-atendimento] ([tratamento]), no valor de [valor].\n"
                   "Segue a chave Pix: [chave-pix]\n"
                   "Depois me envie o comprovante, por favor.")
PADROES = {NOTA: MODELO_NOTA, NOTAS: MODELO_NOTAS, COBRANCA: MODELO_COBRANCA}

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


def tipo_certo(tipo: str) -> str:
    return tipo if tipo in PADROES else NOTA


def variaveis_do(tipo: str) -> dict[str, str]:
    if tipo == COBRANCA:
        return dict(VARIAVEIS_DA_COBRANCA)
    return {**VARIAVEIS, **VARIAVEIS_SO_DE_VARIAS} if tipo == NOTAS else dict(VARIAVEIS)


def modelo(cfg: dict, tipo: str) -> str:
    """O modelo das Configurações, ou o padrão."""
    return cfg.get(CHAVES[tipo]) or PADROES[tipo]


def desconhecidas(texto: str, tipo: str) -> list[str]:
    conhecidas = variaveis_do(tipo)
    vistas = []
    for m in _RE_VARIAVEL.finditer(texto):
        nome = m.group(1).strip().lower()
        if nome not in conhecidas and nome not in vistas:
            vistas.append(nome)
    return vistas


def validar(texto: str, tipo: str) -> str:
    """O modelo como vai ser guardado. Variável escrita errada não deixa salvar."""
    texto = str(texto or "").replace("\r\n", "\n").strip()
    if not texto:
        raise ModeloInvalido("A mensagem não pode ficar vazia. Para voltar ao texto de antes, use “Voltar ao padrão”.")
    erradas = desconhecidas(texto, tipo)
    if erradas:
        lista = ", ".join(f"[{v}]" for v in erradas)
        raise ModeloInvalido(f"Não conheço {lista}. Use os botões para pôr as variáveis certas.")
    return texto


def preencher(texto: str, valores: dict[str, str]) -> str:
    """Troca cada [variável] pelo valor. O que não for variável conhecida fica como está."""
    def trocar(m: re.Match) -> str:
        nome = m.group(1).strip().lower()
        return valores[nome] if nome in valores else m.group(0)

    return _RE_VARIAVEL.sub(trocar, texto)


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


def mensagem(cfg: dict, destinatario: str, notas: list) -> str:
    """A mensagem pronta: uma nota usa o modelo de uma nota; mais de uma, o de várias."""
    tipo = NOTA if len(notas) == 1 else NOTAS
    lista = [NotaDaMensagem(n.numero, n.paciente, n.competencia, n.emissao, n.valor) for n in notas]
    return preencher(modelo(cfg, tipo), valores(cfg.get("assistente_nome", ""), destinatario, lista)).strip()


# Exemplo da prévia (inventado: nenhum dado real aparece na tela de Configurações).
EXEMPLO_RESPONSAVEL = "FERNANDA COSTA"
EXEMPLO = {
    NOTA: [NotaDaMensagem(836, "LUCAS COSTA RIBEIRO", date(2026, 10, 30), date(2026, 10, 30), Decimal("180.00"))],
    NOTAS: [NotaDaMensagem(836, "LUCAS COSTA RIBEIRO", date(2026, 10, 2), date(2026, 10, 2), Decimal("180.00")),
            NotaDaMensagem(837, "LUCAS COSTA RIBEIRO", date(2026, 10, 16), date(2026, 10, 16), Decimal("180.00")),
            NotaDaMensagem(838, "SOFIA COSTA RIBEIRO", date(2026, 10, 16), date(2026, 10, 17), Decimal("250.00"))],
}


def previa(texto: str, tipo: str, assistente: str) -> dict:
    if tipo == COBRANCA:
        exemplo = valores_cobranca(assistente, EXEMPLO_RESPONSAVEL, "LUCAS COSTA RIBEIRO", date(2026, 10, 30),
                                   "Manutenção", 18000, "chave@exemplo.com")
        return {"texto": _limpar(preencher(str(texto or ""), exemplo)), "desconhecidas": desconhecidas(str(texto or ""), tipo)}
    return {"texto": preencher(str(texto or ""), valores(assistente, EXEMPLO_RESPONSAVEL, EXEMPLO[tipo])),
            "desconhecidas": desconhecidas(str(texto or ""), tipo)}


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


def _limpar(texto: str) -> str:
    """O que sobra quando um dado falta: "()" sem tratamento, ", no valor de ." sem valor."""
    texto = re.sub(r"\s*\(\s*\)", "", texto)
    texto = re.sub(r",?\s*no valor de\s*(?=[.,\n]|$)", "", texto)
    return texto.strip()


def mensagem_cobranca(cfg: dict, destinatario: str, paciente: str, dia: date, tratamento: str,
                      valor_centavos: int | None) -> str:
    v = valores_cobranca(cfg.get("assistente_nome", ""), destinatario, paciente, dia, tratamento, valor_centavos,
                         cfg.get("chave_pix", ""))
    return _limpar(preencher(modelo(cfg, COBRANCA), v))
