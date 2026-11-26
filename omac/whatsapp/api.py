"""Parte da API que cuida dos textos das mensagens (Configurações → Mensagens)."""

from __future__ import annotations

from .. import config
from ..nucleo import ApiBase, seguro
from . import catalogo as cat


class MensagensApi(ApiBase):
    def _vista_mensagens(self) -> dict:
        return {"grupos": cat.vista(self._cfg), "config": self._cfg}

    @seguro
    def mensagens_modelos(self):
        return self._vista_mensagens()

    @seguro
    def mensagens_previa(self, tipo: str, versao: str, texto: str):
        """Como a mensagem fica com um exemplo inventado, e as variáveis que não existem."""
        return cat.previa(tipo, versao, texto, self._cfg["assistente_nome"])

    @seguro
    def mensagens_salvar(self, tipo: str, versao: str, texto: str):
        """Guarda o texto. Igual ao padrão guarda vazio: segue o padrão."""
        self._cfg = config.salvar({**self._cfg, "mensagens": cat.com_texto(self._cfg, tipo, versao, texto)})
        return self._vista_mensagens()

    @seguro
    def mensagens_padrao(self, tipo: str, versao: str):
        self._cfg = config.salvar({**self._cfg, "mensagens": cat.com_texto(self._cfg, tipo, versao, None)})
        return self._vista_mensagens()
