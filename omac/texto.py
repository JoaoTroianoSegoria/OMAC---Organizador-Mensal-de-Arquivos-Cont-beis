"""Pequenas funções de texto usadas por mais de um módulo."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal


def normalizar(texto: str) -> str:
    """Maiúsculas, sem acento e sem espaço repetido: serve para comparar nomes."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())


class ValorInvalido(ValueError):
    """O texto não parece um valor em reais."""


def valor_em_centavos(texto) -> int | None:
    """Aceita 250 · 250,5 · 250,00 · 1.250,00 · R$ 250. Vazio quer dizer "sem valor"."""
    bruto = re.sub(r"(?i)r\$|\s", "", str(texto or ""))
    if not bruto:
        return None
    if re.fullmatch(r"\d{1,3}(\.\d{3})*(,\d{1,2})?", bruto) or re.fullmatch(r"\d+(,\d{1,2})?", bruto):
        numero = bruto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+\.\d{1,2}", bruto):  # 250.50, como vem de uma calculadora
        numero = bruto
    else:
        raise ValorInvalido("Confira o valor: use algo como 250,00.")
    return int(Decimal(numero) * 100)


def nome_limpo(texto) -> str:
    return " ".join(str(texto or "").split())
