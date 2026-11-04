"""Base da API que a interface chama: o que todos os módulos compartilham."""

from __future__ import annotations

import threading
import traceback
from functools import wraps
from pathlib import Path

from . import APP_NOME, APP_NOME_COMPLETO, __version__, config, sistema

CHAVES_DE_PASTA = {"pasta_notas", "pasta_extratos"}


def seguro(func):
    """Erros viram {"erro": "..."} para a interface mostrar uma mensagem amigável."""

    @wraps(func)
    def envolvida(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — a interface nunca deve ficar travada
            traceback.print_exc()
            return {"erro": str(e) or e.__class__.__name__}

    return envolvida


def caminho_unico(escolha) -> str:
    """Os diálogos do pywebview devolvem ora uma tupla, ora uma string."""
    return escolha[0] if isinstance(escolha, (list, tuple)) else escolha


class ApiBase:
    """Configurações, diálogos e abertura de arquivos.

    Cada módulo é uma classe que herda daqui. Métodos públicos ficam disponíveis
    no JS como window.pywebview.api.<nome>; os de módulo levam o nome do módulo
    como prefixo (ex.: extrato_do_mes).
    """

    def __init__(self):
        self._janela = None
        self._cfg = config.carregar()
        self._trava = threading.Lock()

    @seguro
    def estado(self):
        return {
            "versao": __version__,
            "nome": APP_NOME,
            "nome_completo": APP_NOME_COMPLETO,
            "config": self._cfg,
        }

    @seguro
    def salvar_config(self, novas: dict):
        self._cfg = config.salvar({**self._cfg, **(novas or {})})
        return self._cfg

    @seguro
    def escolher_pasta(self, chave: str = "pasta_notas"):
        import webview

        if chave not in CHAVES_DE_PASTA:
            return {"erro": f"Pasta desconhecida: {chave}"}
        inicial = self._cfg[chave] or str(Path.home())
        escolha = self._janela.create_file_dialog(webview.FileDialog.FOLDER, directory=inicial)
        if not escolha:
            return {"cancelado": True}
        pasta = caminho_unico(escolha)
        self._cfg = config.salvar({**self._cfg, chave: pasta})
        return {"pasta": pasta, "config": self._cfg}

    @seguro
    def abrir_pasta(self, chave: str = "pasta_notas"):
        if chave in CHAVES_DE_PASTA and self._cfg[chave]:
            sistema.abrir(self._cfg[chave])
        return {}

    @seguro
    def abrir(self, caminho: str):
        sistema.abrir(caminho)
        return {}

    @seguro
    def mostrar_na_pasta(self, caminho: str):
        sistema.mostrar_na_pasta(caminho)
        return {}

    def _dialogo_salvar(self, nome: str, extensao: str, descricao: str, inicial: str = "") -> Path | None:
        import webview

        escolha = self._janela.create_file_dialog(
            webview.FileDialog.SAVE,
            directory=inicial or self._cfg["pasta_saida"] or str(Path.home()),
            save_filename=nome,
            file_types=(f"{descricao} (*.{extensao})",),
        )
        if not escolha:
            return None
        destino = Path(caminho_unico(escolha))
        if destino.suffix.lower() != f".{extensao}":
            destino = destino.with_name(f"{destino.name}.{extensao}")
        return destino

    def _progresso(self, feitos: int, total: int) -> None:
        if self._janela is not None:
            self._janela.evaluate_js(f"window.omacProgresso && window.omacProgresso({feitos}, {total})")
