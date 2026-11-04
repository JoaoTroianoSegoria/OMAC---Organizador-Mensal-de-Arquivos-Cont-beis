"""Janela do OMAC e a API que a interface (HTML/JS) chama via pywebview."""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from functools import wraps
from pathlib import Path

from . import APP_NOME, APP_NOME_COMPLETO, __version__, config, sistema
from .notas import exportar as exp
from .notas.pasta import Cache, Varredura, varrer


def _seguro(func):
    """Erros viram {"erro": "..."} para a interface mostrar uma mensagem amigável."""

    @wraps(func)
    def envolvida(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — a interface nunca deve ficar travada
            traceback.print_exc()
            return {"erro": str(e) or e.__class__.__name__}

    return envolvida


class Api:
    """Métodos públicos ficam disponíveis no JS como window.pywebview.api.<nome>."""

    def __init__(self):
        self._janela = None
        self._cfg = config.carregar()
        self._varredura: Varredura | None = None
        self._trava = threading.Lock()

    # --- Configurações -----------------------------------------------------

    @_seguro
    def estado(self):
        return {
            "versao": __version__,
            "nome": APP_NOME,
            "nome_completo": APP_NOME_COMPLETO,
            "config": self._cfg,
        }

    @_seguro
    def salvar_config(self, novas: dict):
        self._cfg = config.salvar({**self._cfg, **(novas or {})})
        return self._cfg

    @_seguro
    def escolher_pasta(self):
        import webview

        inicial = self._cfg["pasta_notas"] or str(Path.home())
        escolha = self._janela.create_file_dialog(webview.FileDialog.FOLDER, directory=inicial)
        if not escolha:
            return {"cancelado": True}
        pasta = escolha[0] if isinstance(escolha, (list, tuple)) else escolha
        self._varredura = None
        self._cfg = config.salvar({**self._cfg, "pasta_notas": pasta})
        return {"pasta": pasta, "config": self._cfg}

    # --- Notas ---------------------------------------------------------------

    @_seguro
    def notas_do_mes(self, ano: int, mes: int):
        pasta = self._cfg["pasta_notas"]
        if not pasta:
            return {"sem_pasta": True}
        if not Path(pasta).is_dir():
            return {"erro": f"Não encontrei a pasta “{pasta}”. Ela foi movida ou renomeada?"}

        with self._trava:
            self._varredura = varrer(Path(pasta), Cache(config.caminho_cache()), self._progresso)
        v = self._varredura
        notas = v.do_mes(int(ano), int(mes))
        return {
            "notas": [_nota_para_js(n) for n in notas],
            "total_centavos": sum(int(n.valor * 100) for n in notas),
            "avisos": v.avisos,
            "canceladas_movidas": v.canceladas_movidas,
            "competencias": v.competencias(),
            "qtd_pasta": len(v.notas),
        }

    @_seguro
    def exportar(self, ano: int, mes: int, formato: str):
        import webview

        if self._varredura is None:
            return {"erro": "Atualize a lista de notas antes de exportar."}
        ano, mes = int(ano), int(mes)
        formato = "csv" if formato == "csv" else "xlsx"
        notas = self._varredura.do_mes(ano, mes)

        pasta_inicial = self._cfg["pasta_saida"] or str(Path(self._cfg["pasta_notas"]).parent)
        tipos = ("Planilha do Excel (*.xlsx)",) if formato == "xlsx" else ("Arquivo CSV (*.csv)",)
        escolha = self._janela.create_file_dialog(
            webview.FileDialog.SAVE,
            directory=pasta_inicial,
            save_filename=exp.nome_sugerido(ano, mes, formato),
            file_types=tipos,
        )
        if not escolha:
            return {"cancelado": True}
        destino = Path(escolha[0] if isinstance(escolha, (list, tuple)) else escolha)
        if destino.suffix.lower() != f".{formato}":
            destino = destino.with_name(destino.name + f".{formato}")

        try:
            salvo = exp.exportar(notas, destino, ano, mes)
        except PermissionError:
            return {"erro": "Não consegui salvar: o arquivo está aberto no Excel? Feche e tente de novo."}
        self._cfg = config.salvar({**self._cfg, "pasta_saida": str(salvo.parent), "formato": formato})
        return {"caminho": str(salvo), "qtd": len(notas)}

    @_seguro
    def abrir(self, caminho: str):
        sistema.abrir(caminho)
        return {}

    @_seguro
    def mostrar_na_pasta(self, caminho: str):
        sistema.mostrar_na_pasta(caminho)
        return {}

    @_seguro
    def abrir_nota(self, arquivo: str):
        pasta = Path(self._cfg["pasta_notas"])
        caminho = pasta / Path(arquivo).name
        if not caminho.is_file():
            return {"erro": f"Não encontrei o arquivo “{arquivo}”. Ele foi movido ou renomeado?"}
        sistema.abrir(caminho)
        return {}

    @_seguro
    def abrir_pasta_notas(self):
        if self._cfg["pasta_notas"]:
            sistema.abrir(self._cfg["pasta_notas"])
        return {}

    def _progresso(self, feitos: int, total: int) -> None:
        if self._janela is not None:
            self._janela.evaluate_js(f"window.omacProgresso && window.omacProgresso({feitos}, {total})")


def _nota_para_js(n) -> dict:
    return {
        "numero": n.numero,
        "paciente": n.paciente,
        "valor_centavos": int(n.valor * 100),
        "emissao": n.emissao.isoformat(),
        "competencia": n.competencia.isoformat(),
        "arquivo": n.arquivo,
        "dependente": n.dependente,
        "avisos": n.avisos,
    }


def autoteste(pasta: str, saida: str) -> int:
    """Lê uma pasta e gera as planilhas sem abrir janela (usado no GitHub Actions).

    O .exe não tem console, então qualquer erro vai para o JSON de saída: uma
    exceção sem tratamento abriria uma caixa de diálogo e travaria o CI.
    """
    try:
        return _autoteste(pasta, saida)
    except Exception:  # noqa: BLE001
        Path(saida).write_text(json.dumps({"erro": traceback.format_exc()}), encoding="utf-8")
        return 1


def _autoteste(pasta: str, saida: str) -> int:
    v = varrer(Path(pasta))
    relatorio = {"versao": __version__, "notas": len(v.notas), "avisos": v.avisos,
                 "canceladas_movidas": v.canceladas_movidas, "arquivos": []}
    for ano, mes, _ in v.competencias():
        notas = v.do_mes(ano, mes)
        for formato in ("xlsx", "csv"):
            destino = Path(saida).parent / exp.nome_sugerido(ano, mes, formato)
            exp.exportar(notas, destino, ano, mes)
            relatorio["arquivos"].append(destino.name)
    Path(saida).write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--autoteste":
        return autoteste(sys.argv[2], sys.argv[3])

    if not sistema.webview2_instalado():
        sistema.avisar_sem_webview2()
        return 1

    import webview

    api = Api()
    cfg = api._cfg
    escuro = cfg["tema"] == "escuro"
    janela = webview.create_window(
        f"{APP_NOME} — {APP_NOME_COMPLETO}",
        url=str(sistema.recurso("omac/ui/index.html")),
        js_api=api,
        width=1200,
        height=780,
        min_size=(760, 560),
        background_color="#0E1522" if escuro else "#EEF2F7",
    )
    api._janela = janela
    webview.start(http_server=True, debug=bool(os.environ.get("OMAC_DEBUG")))
    return 0
