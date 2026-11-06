"""Parte da API que cuida das atualizações."""

from __future__ import annotations

import sys
import threading
from datetime import date
from pathlib import Path

from .. import config, sistema
from ..nucleo import ApiBase, seguro
from . import github as gh
from . import instalar as inst

ESPERA_PARA_FECHAR = 0.8  # segundos: dá tempo de a tela receber a resposta


class AtualizacaoApi(ApiBase):
    def __init__(self):
        super().__init__()
        self._versao_nova: gh.VersaoNova | None = None
        self._trava_atualizacao = threading.Lock()

    @seguro
    def atualizacao_disponivel_aqui(self):
        return {"disponivel": sistema.rodando_como_exe()}

    @seguro
    def atualizacao_procurar(self, pedido_na_tela: bool = False):
        """Ao abrir, respeita a configuração, e um erro de internet fica em silêncio."""
        if not sistema.rodando_como_exe():
            return {"indisponivel": True}
        if not pedido_na_tela and (not self._cfg["atualizacao_automatica"]
                                   or self._cfg["atualizacao_adiada_em"] == date.today().isoformat()):
            return {}
        try:
            self._versao_nova = gh.procurar()
        except gh.ErroDeAtualizacao as e:
            return {"erro": str(e)} if pedido_na_tela else {}
        if self._versao_nova is None:
            return {}
        return {"versao": self._versao_nova.numero, "novidades": self._versao_nova.novidades}

    @seguro
    def atualizacao_adiar(self):
        self._cfg = config.salvar({**self._cfg, "atualizacao_adiada_em": date.today().isoformat()})
        return {}

    @seguro
    def atualizacao_abrir_pagina(self):
        sistema.abrir_link(gh.PAGINA_RELEASES)
        return {}

    @seguro
    def atualizacao_instalar(self):
        # A versão vem do que o próprio Python consultou, nunca de um endereço vindo da tela.
        versao = self._versao_nova
        if versao is None:
            return {"erro": "Procure a atualização de novo."}
        if not self._trava_atualizacao.acquire(blocking=False):
            return {"erro": "A atualização já está em andamento."}
        try:
            executavel = Path(sys.executable)
            novo = inst.caminho_novo(executavel)
            inst.baixar(versao, novo, self._progresso_atualizacao)
            inst.copiar_dados()
            antigo = inst.trocar_executavel(executavel, novo)
            try:
                inst.abrir_programa(executavel)
            except OSError as e:
                inst.desfazer_troca(executavel, antigo)
                raise gh.ErroDeAtualizacao(
                    "Não consegui abrir a versão nova, então o programa continua como estava."
                ) from e
        except gh.ErroDeAtualizacao as e:
            return {"erro": str(e)}
        except OSError as e:
            return {"erro": f"Não consegui preparar a atualização ({e.strerror or e}). Nada foi trocado."}
        finally:
            self._trava_atualizacao.release()

        if self._janela is not None:
            threading.Timer(ESPERA_PARA_FECHAR, self._janela.destroy).start()
        return {"reiniciando": True}

    def _progresso_atualizacao(self, recebidos: int, total: int) -> None:
        if self._janela is not None:
            self._janela.evaluate_js(f"window.omacProgressoAtualizacao && window.omacProgressoAtualizacao({recebidos}, {total})")
