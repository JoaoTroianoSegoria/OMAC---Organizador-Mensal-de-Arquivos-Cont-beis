"""Parte da API que cuida das notas fiscais."""

from __future__ import annotations

from pathlib import Path

from .. import config, sistema
from ..nucleo import ApiBase, seguro
from . import exportar as exp
from .pasta import Cache, Varredura, varrer


class NotasApi(ApiBase):
    def __init__(self):
        super().__init__()
        self._varredura: Varredura | None = None
        self._pasta_lida = ""

    def _ler_notas(self, pasta: str) -> Varredura:
        with self._trava:
            self._varredura = varrer(Path(pasta), Cache(config.caminho_cache()), self._progresso)
            self._pasta_lida = pasta
        return self._varredura

    @seguro
    def notas_do_mes(self, ano: int, mes: int):
        pasta = self._cfg["pasta_notas"]
        if not pasta:
            return {"sem_pasta": True}
        if not Path(pasta).is_dir():
            return {"erro": f"Não encontrei a pasta “{pasta}”. Ela foi movida ou renomeada?"}

        v = self._ler_notas(pasta)
        notas = v.do_mes(int(ano), int(mes))
        return {
            "notas": [_nota_para_js(n) for n in notas],
            "total_centavos": sum(int(n.valor * 100) for n in notas),
            "avisos": v.avisos,
            "canceladas_movidas": v.canceladas_movidas,
            "competencias": v.competencias(),
            "qtd_pasta": len(v.notas),
        }

    @seguro
    def exportar(self, ano: int, mes: int, formato: str):
        if self._varredura is None or self._pasta_lida != self._cfg["pasta_notas"]:
            return {"erro": "Atualize a lista de notas antes de exportar."}
        ano, mes = int(ano), int(mes)
        formato = "csv" if formato == "csv" else "xlsx"
        notas = self._varredura.do_mes(ano, mes)

        destino = self._dialogo_salvar(
            exp.nome_sugerido(ano, mes, formato),
            formato,
            "Planilha do Excel" if formato == "xlsx" else "Arquivo CSV",
            self._cfg["pasta_saida"] or str(Path(self._cfg["pasta_notas"]).parent),
        )
        if destino is None:
            return {"cancelado": True}
        try:
            salvo = exp.exportar(notas, destino, ano, mes)
        except PermissionError:
            return {"erro": "Não consegui salvar: o arquivo está aberto no Excel? Feche e tente de novo."}
        self._cfg = config.salvar({**self._cfg, "pasta_saida": str(salvo.parent), "formato": formato})
        return {"caminho": str(salvo), "qtd": len(notas)}

    @seguro
    def abrir_nota(self, arquivo: str):
        caminho = Path(self._cfg["pasta_notas"]) / Path(arquivo).name
        if not caminho.is_file():
            return {"erro": f"Não encontrei o arquivo “{arquivo}”. Ele foi movido ou renomeado?"}
        sistema.abrir(caminho)
        return {}


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
