"""O armazém: o único lugar que lê e grava os arquivos de dados dos módulos.

- Cada arquivo fica em memória e só é lido de novo se mudar no disco (data e tamanho),
  por exemplo depois de restaurar um backup.
- Ao ler, o arquivo passa pelas migrações (migracoes.atualizar) e ganha os campos padrão,
  inclusive em cada item das listas (esquema.ITENS).
- `editar` grava só se algo mudou, sempre de forma atômica (arquivo.salvar_json).
- Uma trava só para todos os arquivos: duas telas nunca gravam ao mesmo tempo.
"""

from __future__ import annotations

import copy
import json
import threading
from contextlib import contextmanager
from pathlib import Path

from . import esquema, migracoes
from .arquivo import DadosIlegiveis, ler_json, salvar_json


class Armazem:
    def __init__(self, pasta: Path):
        self.pasta = Path(pasta)
        self._trava = threading.RLock()
        self._memoria: dict[str, tuple[tuple, dict]] = {}
        # Se a migração falhar, nada é gravado até o problema ser resolvido.
        self.bloqueio = ""

    def caminho(self, nome: str) -> Path:
        return self.pasta / nome

    def _marca(self, caminho: Path) -> tuple:
        try:
            st = caminho.stat()
        except FileNotFoundError:
            return ()
        return (st.st_mtime_ns, st.st_size)

    def _carregar(self, nome: str) -> dict:
        info = esquema.ARQUIVOS[nome]
        caminho = self.caminho(nome)
        marca = self._marca(caminho)
        guardado = self._memoria.get(nome)
        if guardado and guardado[0] == marca:
            return guardado[1]
        lidos = ler_json(caminho, info["conteudo"])
        dados = copy.deepcopy(info["padrao"])
        if lidos is not None:
            dados.update(migracoes.atualizar(nome, lidos))
        if nome in esquema.ITENS:
            chave = esquema.ITENS[nome][0]
            dados[chave] = [esquema.completar_item(nome, item) for item in dados[chave]]
        dados["versao"] = info["versao"]
        self._memoria[nome] = (marca, dados)
        return dados

    def ler(self, nome: str) -> dict:
        """Uma cópia: quem lê pode mexer à vontade sem mudar o que está guardado."""
        with self._trava:
            return copy.deepcopy(self._carregar(nome))

    @contextmanager
    def editar(self, nome: str):
        with self._trava:
            if self.bloqueio:
                raise DadosIlegiveis(self.bloqueio)
            dados = copy.deepcopy(self._carregar(nome))
            antes = json.dumps(dados, sort_keys=True)
            yield dados
            if json.dumps(dados, sort_keys=True) != antes:
                caminho = self.caminho(nome)
                salvar_json(caminho, dados)
                self._memoria[nome] = (self._marca(caminho), copy.deepcopy(dados))

    def esquecer(self) -> None:
        """Depois de trocar os arquivos por fora (restaurar backup), lê tudo de novo."""
        with self._trava:
            self._memoria.clear()
