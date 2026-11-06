"""Contatos, notas enviadas e contas: ficam só em um JSON neste computador."""

from __future__ import annotations

from pathlib import Path

from ..armazem import DadosIlegiveis, carregar_json, salvar_json

__all__ = ["DadosIlegiveis", "carregar", "salvar"]

PADRAO = {
    "inicio": "",  # dia em que o módulo começou a ser usado: notas antigas não entram em "A enviar"
    "ultima_abertura": "",
    "contatos": {},  # nome normalizado → {"nome", "telefone"}
    "enviadas": {},  # número da nota → data do envio
    "contas": [],  # {"nome", "dia"}
}


def carregar(caminho: Path) -> dict:
    return carregar_json(caminho, PADRAO, "Os contatos")


def salvar(caminho: Path, dados: dict) -> None:
    salvar_json(caminho, dados)
