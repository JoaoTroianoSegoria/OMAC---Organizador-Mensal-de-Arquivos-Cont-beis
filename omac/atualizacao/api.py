"""Parte da API que avisa quando há uma versão nova."""

from __future__ import annotations

from datetime import date

from .. import config, sistema
from ..nucleo import ApiBase, seguro
from . import github as gh


class AtualizacaoApi(ApiBase):
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
            versao = gh.procurar()
        except gh.ErroDeAtualizacao as e:
            return {"erro": str(e)} if pedido_na_tela else {}
        if versao is None:
            return {}
        return {"versao": versao.numero, "novidades": versao.novidades}

    @seguro
    def atualizacao_adiar(self):
        self._cfg = config.salvar({**self._cfg, "atualizacao_adiada_em": date.today().isoformat()})
        return {}

    @seguro
    def atualizacao_abrir_pagina(self):
        sistema.abrir_link(gh.PAGINA_RELEASES)
        return {}
