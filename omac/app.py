"""Janela do OMAC e a API que a interface (HTML/JS) chama via pywebview."""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

from . import APP_NOME, APP_NOME_COMPLETO, __version__, fechamento, sistema
from .agendamentos.api import AgendamentosApi
from .atualizacao.api import AtualizacaoApi
from .extrato import regras as rg
from .extrato.api import ExtratoApi
from .extrato.pasta import varrer as varrer_extratos
from .inicio.api import InicioApi
from .notas import exportar as exp
from .notas.api import NotasApi
from .notas.pasta import varrer
from .pagamentos.api import PagamentosApi
from .resumo.api import ResumoApi
from .whatsapp.api import WhatsappApi

PASTA_EXTRATOS_TESTE = "Extratos"


class Api(NotasApi, ExtratoApi, WhatsappApi, AgendamentosApi, PagamentosApi, ResumoApi, InicioApi,
          AtualizacaoApi):
    """Tudo o que a interface pode chamar. Módulo novo entra nesta lista de classes."""


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

    # Extrato + fechamento, se a pasta de exemplo tiver a subpasta de extratos
    pasta_extratos = Path(pasta) / PASTA_EXTRATOS_TESTE
    if pasta_extratos.is_dir():
        c = varrer_extratos(pasta_extratos)
        relatorio["lancamentos"] = len(c.lancamentos)
        relatorio["avisos_extrato"] = c.avisos
        for ano, mes, _ in c.meses():
            itens = [(l, rg.classificar(l, rg.REGRAS_PADRAO)) for l in c.do_mes(ano, mes)]
            destino = Path(saida).parent / fechamento.nome_sugerido(ano, mes)
            fechamento.gerar(destino, itens, v.do_mes(ano, mes))
            relatorio["arquivos"].append(destino.name)
    Path(saida).write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


# Roda dentro da página, no autoteste da tela.
_SONDA_TELA = """(function () {
  const scripts = Array.from(document.scripts).map((s) => s.getAttribute("src")).filter(Boolean);
  const arquivos = {};
  for (const nome of scripts) {
    const x = new XMLHttpRequest();
    x.open("GET", nome, false);
    x.send();
    arquivos[nome] = [x.status, x.getResponseHeader("content-type"), x.responseText.length];
  }
  return {
    agente: navigator.userAgent,
    modulos: typeof modulos === "undefined" ? null : Object.keys(modulos),
    erros: window.omacErrosDeTela,
    arquivos: arquivos,
    meses: document.querySelectorAll("#ext-sel-mes option").length,
    anos: document.querySelectorAll("#ext-sel-ano option").length,
    lancamentos: document.querySelectorAll("#ext-corpo tr").length,
  };
})()"""


def autoteste_tela(pasta: str, saida: str) -> int:
    """Abre a tela de verdade e vai ao extrato (usado no GitHub Actions, no Windows)."""
    import webview

    relatorio: dict = {"versao": __version__, "webview2": sistema.webview2_instalado()}
    pasta_ui = Path(sistema.recurso("omac/ui"))
    relatorio["pacote"] = {p.name: p.stat().st_size for p in sorted(pasta_ui.iterdir())}

    api = Api()
    api._cfg.update(pasta_notas=str(Path(pasta).resolve()),
                    pasta_extratos=str((Path(pasta) / PASTA_EXTRATOS_TESTE).resolve()),
                    lembrete_fechamento_dia=0, atualizacao_automatica=False)
    janela = webview.create_window("OMAC autoteste", url=str(sistema.recurso("omac/ui/index.html")),
                                   js_api=api, width=1200, height=780)
    api._janela = janela

    def tarefa():
        try:
            janela.events.loaded.wait(60)
            time.sleep(6)
            relatorio["notas"] = janela.evaluate_js(_SONDA_TELA)
            janela.evaluate_js('mostrarView("extrato")')
            time.sleep(8)
            relatorio["extrato"] = janela.evaluate_js(_SONDA_TELA)
        except Exception:  # noqa: BLE001
            relatorio["erro"] = traceback.format_exc()
        finally:
            Path(saida).write_text(json.dumps(relatorio, ensure_ascii=False), encoding="utf-8")
            janela.destroy()

    webview.start(tarefa, http_server=True)
    return 0


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--autoteste":
        return autoteste(sys.argv[2], sys.argv[3])
    if len(sys.argv) == 4 and sys.argv[1] == "--autoteste-tela":
        return autoteste_tela(sys.argv[2], sys.argv[3])

    if not sistema.webview2_instalado():
        sistema.avisar_sem_webview2()
        return 1

    import webview

    sistema.corrigir_inicio_automatico()
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
