"""Serviço único de notas: lê a pasta (com o cache-notas.json) e guarda a última leitura.

A tela de Notas fiscais pede uma leitura nova; os outros módulos (envio, atendimentos,
resumo, Início) aproveitam a última, se for da mesma pasta.
"""

from __future__ import annotations

import os
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable

from .. import config
from .leitor import PADRAO, Regras
from .pasta import Cache, Varredura, varrer


class SemPasta(ValueError):
    """A pasta das notas não foi escolhida ou não existe mais."""


class ServicoNotas:
    def __init__(self, pasta: Callable[[], str], progresso: Callable[[int, int], None] | None = None,
                 regras: Callable[[], Regras] = lambda: PADRAO):
        self._pasta = pasta
        self._progresso = progresso
        self._regras = regras
        self._trava = threading.Lock()
        self._ultima: Varredura | None = None
        self._pasta_lida = ""
        self._regras_lidas = ""
        self._impressao: tuple = ()
        self.lida_em: datetime | None = None
        self.novas: list = []  # notas que apareceram desde a leitura anterior da mesma pasta

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
        regras = self._regras()
        with self._trava:
            antes = self._ultima if self._pasta_lida == str(pasta) else None
            # Antes de ler: um PDF que chegue durante a leitura muda a impressão e é lido na próxima.
            impressao = _impressao(pasta)
            self._ultima = varrer(pasta, Cache(config.caminho_cache(), regras), self._progresso, regras=regras)
            self._pasta_lida = str(pasta)
            self._regras_lidas = regras.assinatura()
            # As canceladas que a leitura levou para a subpasta não são mudança de quem usa.
            self._impressao = _impressao(pasta) if self._ultima.canceladas_movidas else impressao
            self.lida_em = datetime.now()
            ja = {n.numero for n in antes.notas} if antes else None
            self.novas = [] if ja is None else [n for n in self._ultima.notas if n.numero not in ja]
        return self._ultima

    def mudou(self) -> bool:
        """A pasta já lida ganhou, perdeu ou mudou algum PDF? Só olha nome, tamanho e data
        dos arquivos (milésimos de segundo): não abre nenhum. Sem leitura feita, nada a conferir."""
        if self._ultima is None:
            return False
        try:
            pasta = self.pasta()
        except SemPasta:
            return False
        if str(pasta) != self._pasta_lida or self._regras().assinatura() != self._regras_lidas:
            return True
        return _impressao(pasta) != self._impressao

    def atual(self) -> Varredura:
        """A última leitura da pasta escolhida, ou uma nova."""
        pasta = str(self.pasta())
        if self._ultima is not None and self._pasta_lida == pasta and self._regras_lidas == self._regras().assinatura():
            return self._ultima
        return self.ler()

    def ja_lida(self) -> Varredura | None:
        """Só a leitura já feita da pasta atual, sem ler nada (para exportar o que está na tela)."""
        if self._ultima is None or self._pasta_lida != self._pasta():
            return None
        return self._ultima if self._regras_lidas == self._regras().assinatura() else None

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


def _impressao(pasta: Path) -> tuple:
    """Os PDFs da pasta (sem as subpastas, como a leitura): nome, tamanho e data de cada um."""
    itens = []
    try:
        with os.scandir(pasta) as entradas:
            for e in entradas:
                if e.name.lower().endswith(".pdf") and e.is_file():
                    st = e.stat()
                    itens.append((e.name, st.st_size, st.st_mtime_ns))
    except OSError:
        return ()
    return tuple(sorted(itens))
