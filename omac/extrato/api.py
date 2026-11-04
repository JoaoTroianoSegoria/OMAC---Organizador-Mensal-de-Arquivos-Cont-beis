"""Parte da API que cuida do extrato bancário."""

from __future__ import annotations

from pathlib import Path

from .. import config, fechamento
from ..nucleo import ApiBase, caminho_unico, seguro
from . import exportar as exp
from . import regras as rg
from .pasta import Consolidado, varrer


class ExtratoApi(ApiBase):
    def _regras(self) -> list[dict]:
        return rg.carregar(config.caminho_regras())

    def _ler_extratos(self) -> Consolidado | dict:
        pasta = self._cfg["pasta_extratos"]
        if not pasta:
            return {"sem_pasta": True}
        if not Path(pasta).is_dir():
            return {"erro": f"Não encontrei a pasta “{pasta}”. Ela foi movida ou renomeada?"}
        return varrer(Path(pasta))

    @seguro
    def extrato_do_mes(self, ano: int, mes: int):
        c = self._ler_extratos()
        if isinstance(c, dict):
            return c
        ano, mes = int(ano), int(mes)
        regras = self._regras()
        lancamentos = c.do_mes(ano, mes)
        linhas = [_lancamento_para_js(l, rg.classificar(l, regras)) for l in lancamentos]
        totais = exp.totais(lancamentos)
        return {
            "lancamentos": linhas,
            "entradas_centavos": _centavos(totais["entradas"]),
            "saidas_centavos": _centavos(totais["saidas"]),
            "saldo_final_centavos": _centavos(lancamentos[-1].saldo) if lancamentos else None,
            "a_preencher": sum(1 for l in linhas if not l["operacao"]),
            "avisos": c.avisos + c.avisos_do_mes(ano, mes),
            "meses": c.meses(),
            "qtd_pasta": len(c.lancamentos),
            "qtd_extratos": len(c.extratos),
            "regras": regras,
        }

    @seguro
    def extrato_salvar_regra(self, nova: dict, antiga: dict | None = None):
        regras = rg.adicionar(self._regras(), nova, antiga)
        rg.salvar(config.caminho_regras(), regras)
        return {"regras": regras}

    @seguro
    def extrato_apagar_regra(self, regra: dict):
        regras = rg.remover(self._regras(), regra)
        rg.salvar(config.caminho_regras(), regras)
        return {"regras": regras}

    @seguro
    def extrato_importar_regras(self):
        import webview

        escolha = self._janela.create_file_dialog(
            webview.FileDialog.OPEN,
            directory=str(Path.home()),
            file_types=("Regras do OMAC (*.json)",),
        )
        if not escolha:
            return {"cancelado": True}
        regras, qtd = rg.importar(self._regras(), Path(caminho_unico(escolha)))
        rg.salvar(config.caminho_regras(), regras)
        return {"regras": regras, "qtd": qtd}

    @seguro
    def extrato_exportar_regras(self):
        destino = self._dialogo_salvar("Regras do OMAC.json", "json", "Regras do OMAC")
        if destino is None:
            return {"cancelado": True}
        rg.salvar(destino, self._regras())
        return {"caminho": str(destino)}

    @seguro
    def extrato_exportar(self, ano: int, mes: int):
        c = self._ler_extratos()
        if isinstance(c, dict):
            return c
        ano, mes = int(ano), int(mes)
        regras = self._regras()
        itens = [(l, rg.classificar(l, regras)) for l in c.do_mes(ano, mes)]
        if not itens:
            return {"erro": "Não há lançamentos neste mês para exportar."}

        pasta_notas = self._cfg["pasta_notas"]
        notas = None
        if pasta_notas and Path(pasta_notas).is_dir():
            notas = self._ler_notas(pasta_notas).do_mes(ano, mes)

        destino = self._dialogo_salvar(
            fechamento.nome_sugerido(ano, mes), "xlsx", "Planilha do Excel",
            self._cfg["pasta_saida"] or str(Path(self._cfg["pasta_extratos"]).parent),
        )
        if destino is None:
            return {"cancelado": True}
        try:
            salvo = fechamento.gerar(destino, itens, notas)
        except PermissionError:
            return {"erro": "Não consegui salvar: o arquivo está aberto no Excel? Feche e tente de novo."}
        self._cfg = config.salvar({**self._cfg, "pasta_saida": str(salvo.parent)})
        return {
            "caminho": str(salvo),
            "com_notas": notas is not None,
            "a_preencher": sum(1 for _, op in itens if not op),
        }


def _centavos(valor) -> int:
    return int(valor * 100)


def _lancamento_para_js(l, operacao: str) -> dict:
    return {
        "data": l.data.isoformat(),
        "tipo": l.tipo,
        "descricao": l.descricao,
        "valor_centavos": _centavos(l.valor),
        "saldo_centavos": _centavos(l.saldo),
        "sentido": l.sentido,
        "operacao": operacao,
    }
