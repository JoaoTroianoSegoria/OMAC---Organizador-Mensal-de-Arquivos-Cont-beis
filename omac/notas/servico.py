"""Serviço único de notas: lê a pasta (com o cache-notas.json) e guarda a última leitura.

A tela de Notas fiscais pede uma leitura nova; os outros módulos (envio, atendimentos,
resumo, Início) aproveitam a última, se for da mesma pasta.
"""

from __future__ import annotations

import threading
import traceback
from pathlib import Path
from typing import Callable

from .. import config
from .pasta import Cache, Varredura, varrer


class SemPasta(ValueError):
    """A pasta das notas não foi escolhida ou não existe mais."""


class ServicoNotas:
    def __init__(self, pasta: Callable[[], str], progresso: Callable[[int, int], None] | None = None):
        self._pasta = pasta
        self._progresso = progresso
        self._trava = threading.Lock()
        self._ultima: Varredura | None = None
        self._pasta_lida = ""

    def pasta(self) -> Path:
        pasta = self._pasta()
        if not pasta:
            raise SemPasta("Escolha a pasta das notas primeiro.")
        if not Path(pasta).is_dir():
            raise SemPasta(f"Não encontrei a pasta “{pasta}”. Ela foi movida ou renomeada?")
        return Path(pasta)

    def ler(self) -> Varredura:
        """Lê a pasta de novo (as notas já lidas vêm do cache)."""
        pasta = self.pasta()
        with self._trava:
            self._ultima = varrer(pasta, Cache(config.caminho_cache()), self._progresso)
            self._pasta_lida = str(pasta)
        return self._ultima

    def atual(self) -> Varredura:
        """A última leitura da pasta escolhida, ou uma nova."""
        pasta = str(self.pasta())
        if self._ultima is not None and self._pasta_lida == pasta:
            return self._ultima
        return self.ler()

    def ja_lida(self) -> Varredura | None:
        """Só a leitura já feita da pasta atual, sem ler nada (para exportar o que está na tela)."""
        return self._ultima if self._ultima is not None and self._pasta_lida == self._pasta() else None

    def ou_nada(self) -> Varredura | None:
        """Para quem continua funcionando sem notas: None se a pasta não puder ser lida."""
        try:
            return self.atual()
        except SemPasta:
            return None
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            return None

    def do_mes(self, ano: int, mes: int) -> list | None:
        v = self.ou_nada()
        return None if v is None else v.do_mes(ano, mes)

    def todas(self) -> list | None:
        v = self.ou_nada()
        return None if v is None else v.notas
