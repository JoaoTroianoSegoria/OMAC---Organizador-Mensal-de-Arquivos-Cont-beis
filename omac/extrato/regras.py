"""Regras "quando aparecer X, colocar Y" que preenchem a coluna Operação.

Ficam em um arquivo JSON na pasta de dados do computador, porque os nomes de
fornecedores e funcionários não podem ir para o repositório. Aqui no código só
ficam as regras genéricas, iguais para qualquer conta do Inter.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..texto import normalizar
from .leitor import Lancamento

SENTIDOS = {"entrada", "saida"}

REGRAS_PADRAO = [
    {"sentido": "entrada", "quando": "Pix recebido", "operacao": "RECEBIMENTO DE PIX PACIENTE"},
    {"sentido": "entrada", "quando": "CARTAO DE CREDITO", "operacao": "ENTRADA DE PAGAMENTO CRÉDITO"},
    {"sentido": "entrada", "quando": "CARTAO DE DEBITO", "operacao": "DÉBITO RECEBIMENTO"},
    {"sentido": "saida", "quando": "SIMPLES NACIONAL", "operacao": "PAGAMENTO DE IMPOSTO (SIMPLES NACIONAL)"},
    {"sentido": "saida", "quando": "DARF NUMERADO", "operacao": "PAGAMENTO DE IMPOSTO (DARF)"},
]


class RegraInvalida(ValueError):
    """Regra incompleta, ou arquivo de regras que não dá para entender."""


def validar(regra: dict) -> dict:
    limpa = {
        "sentido": str(regra.get("sentido", "")).strip(),
        "quando": " ".join(str(regra.get("quando", "")).split()),
        "operacao": " ".join(str(regra.get("operacao", "")).split()),
    }
    if limpa["sentido"] not in SENTIDOS:
        raise RegraInvalida("Escolha se a regra vale para entrada ou saída.")
    if not limpa["quando"]:
        raise RegraInvalida("Diga o que precisa aparecer no extrato.")
    if not limpa["operacao"]:
        raise RegraInvalida("Diga o que colocar na planilha.")
    return limpa


def _mesma(a: dict, b: dict) -> bool:
    return a["sentido"] == b["sentido"] and normalizar(a["quando"]) == normalizar(b["quando"])


def adicionar(regras: list[dict], nova: dict, antiga: dict | None = None) -> list[dict]:
    """Nova regra para o mesmo texto e sentido substitui a que já existe."""
    nova = validar(nova)
    resto = [r for r in regras if not _mesma(r, nova) and not (antiga and _mesma(r, antiga))]
    return [*resto, nova]


def remover(regras: list[dict], regra: dict) -> list[dict]:
    return [r for r in regras if not _mesma(r, regra)]


def classificar(lancamento: Lancamento, regras: list[dict]) -> str:
    """Operação do lançamento, ou "" se nenhuma regra servir.

    Compara palavras inteiras (senão "CEB" casaria com "reCEBido"). Se mais de
    uma regra servir, ganha a de texto mais longo, que é a mais específica.
    """
    alvo = normalizar(f"{lancamento.tipo} {lancamento.descricao}")
    melhor, tamanho = "", 0
    for regra in regras:
        if regra["sentido"] != lancamento.sentido:
            continue
        quando = normalizar(regra["quando"])
        if len(quando) > tamanho and re.search(rf"(?<!\w){re.escape(quando)}(?!\w)", alvo):
            melhor, tamanho = regra["operacao"], len(quando)
    return melhor


def carregar(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return [dict(r) for r in REGRAS_PADRAO]
    return _ler_arquivo(caminho)


def salvar(caminho: Path, regras: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps({"regras": regras}, ensure_ascii=False, indent=2), encoding="utf-8")


def importar(regras: list[dict], arquivo: Path) -> tuple[list[dict], int]:
    """Junta as regras do arquivo às atuais; as do arquivo têm preferência."""
    novas = _ler_arquivo(arquivo)
    for nova in novas:
        regras = adicionar(regras, nova)
    return regras, len(novas)


def _ler_arquivo(caminho: Path) -> list[dict]:
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        return [validar(r) for r in dados["regras"]]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise RegraInvalida(f"Não consegui ler o arquivo de regras “{Path(caminho).name}”.") from e
