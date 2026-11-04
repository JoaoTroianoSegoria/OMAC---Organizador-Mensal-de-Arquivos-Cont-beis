"""Pequenas funções de texto usadas por mais de um módulo."""

from __future__ import annotations

import unicodedata


def normalizar(texto: str) -> str:
    """Maiúsculas, sem acento e sem espaço repetido: serve para comparar nomes."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())
