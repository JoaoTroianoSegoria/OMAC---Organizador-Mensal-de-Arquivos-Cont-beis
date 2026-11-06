"""Leitura e gravação dos arquivos JSON com os dados do usuário."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path


class DadosIlegiveis(ValueError):
    """O arquivo existe, mas não dá para entender. Nunca é sobrescrito em silêncio."""


def carregar_json(caminho: Path, padrao: dict, conteudo: str) -> dict:
    """`padrao` completa o que faltar; `conteudo` diz na mensagem de erro o que está no arquivo."""
    dados = copy.deepcopy(padrao)
    if not caminho.exists():
        return dados
    try:
        lidos = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(lidos, dict):
            raise ValueError
    except (OSError, ValueError) as e:
        raise DadosIlegiveis(f"Não consegui ler “{caminho.name}”. {conteudo} estão nesse arquivo.") from e
    dados.update(lidos)
    return dados


def salvar_json(caminho: Path, dados: dict) -> None:
    # Escreve em outro arquivo e troca: uma queda de energia não corrompe o que já estava salvo.
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(f"{caminho.name}.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporario, caminho)
