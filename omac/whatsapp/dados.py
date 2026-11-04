"""Contatos, notas enviadas e contas: ficam só em um JSON neste computador."""

from __future__ import annotations

import json
import os
from pathlib import Path

PADRAO = {
    "inicio": "",  # dia em que o módulo começou a ser usado: notas antigas não entram em "A enviar"
    "ultima_abertura": "",
    "contatos": {},  # nome normalizado → {"nome", "telefone"}
    "enviadas": {},  # número da nota → data do envio
    "contas": [],  # {"nome", "dia"}
}


class DadosIlegiveis(ValueError):
    """O arquivo existe, mas não dá para entender. Nunca é sobrescrito em silêncio."""


def carregar(caminho: Path) -> dict:
    dados = json.loads(json.dumps(PADRAO))
    if not caminho.exists():
        return dados
    try:
        lidos = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(lidos, dict):
            raise ValueError
    except (OSError, ValueError) as e:
        raise DadosIlegiveis(f"Não consegui ler “{caminho.name}”. Os contatos estão nesse arquivo.") from e
    dados.update(lidos)
    return dados


def salvar(caminho: Path, dados: dict) -> None:
    # Escreve em outro arquivo e troca: uma queda de energia não corrompe os contatos.
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(f"{caminho.name}.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporario, caminho)
