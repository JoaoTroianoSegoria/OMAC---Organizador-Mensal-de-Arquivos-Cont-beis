"""Parte da API que cuida das notas fiscais."""

from __future__ import annotations

from pathlib import Path

from datetime import date

from .. import config, sistema
from ..nucleo import ApiBase, seguro
from . import exportar as exp
from . import pesquisa
from .leitor import FORMATO_PADRAO, SERVICO_PADRAO, FormatoInvalido, Regras, compilar_formato, ler_nome_arquivo, responsavel


class NotasApi(ApiBase):
    @seguro
    def notas_do_mes(self, ano: int, mes: int):
        pasta = self._cfg["pasta_notas"]
        if not pasta:
            return {"sem_pasta": True}
        if not Path(pasta).is_dir():
            return {"erro": f"Não encontrei a pasta “{pasta}”. Ela foi movida ou renomeada?"}

        v = self._servico_notas.ler()
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
    def notas_pesquisar(self, texto: str, escopo: str, ano: int, mes: int, de: str = "", ate: str = ""):
        """Pesquisa no mês escolhido, no ano todo (a pasta inteira) ou num período (de–até)."""
        v = self._servico_notas.ja_lida() or self._servico_notas.atual()
        if escopo == "mes":
            notas = v.do_mes(int(ano), int(mes))
            inicio = fim = None
        elif escopo == "periodo":
            inicio, fim = _data_ou_nada(de), _data_ou_nada(ate)
            if inicio and fim and inicio > fim:
                inicio, fim = fim, inicio
            notas = v.notas
        else:
            notas, inicio, fim = v.notas, None, None
        achadas = pesquisa.filtrar(notas, texto, inicio, fim)
        return {
            "notas": [_nota_para_js(n) for n in achadas],
            "total_centavos": sum(int(n.valor * 100) for n in achadas),
        }

    @seguro
    def exportar(self, ano: int, mes: int, formato: str):
        lida = self._servico_notas.ja_lida()
        if lida is None:
            return {"erro": "Atualize a lista de notas antes de exportar."}
        ano, mes = int(ano), int(mes)
        formato = "csv" if formato == "csv" else "xlsx"
        notas = lida.do_mes(ano, mes)

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

    # --- Como ler as notas (Configurações → Notas fiscais) --------------------------------

    @seguro
    def notas_testar_formato(self, formato: str):
        """Confere o formato nos nomes dos PDFs da pasta, sem abrir nenhum: quantos entendeu e exemplos."""
        try:
            compilar_formato(formato)
        except FormatoInvalido as e:
            return {"erro": str(e)}
        pasta = self._cfg["pasta_notas"]
        if not pasta or not Path(pasta).is_dir():
            return {"sem_pasta": True}
        regras = Regras(formato, self._cfg["servico_esperado"])
        nomes = sorted(p.name for p in Path(pasta).iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
        lidos = [(n, ler_nome_arquivo(n, regras)) for n in nomes]
        entendidos = [(n, x) for n, x in lidos if x]
        return {
            "total": len(nomes),
            "entendidos": len(entendidos),
            # Os mais recentes primeiro (o número da nota é a melhor ordem).
            "exemplos": [{"arquivo": n, "numero": x[0], "nome": x[1]}
                         for n, x in sorted(entendidos, key=lambda e: -e[1][0])[:3]],
            "fora": [n for n, x in lidos if not x][-5:],
        }

    @seguro
    def notas_salvar_regras(self, formato: str, servico: str):
        """Guarda o formato do nome e o serviço esperado. As notas são lidas de novo na próxima vez."""
        formato = " ".join(str(formato or "").split()) or FORMATO_PADRAO
        try:
            compilar_formato(formato)
        except FormatoInvalido as e:
            return {"erro": str(e)}
        self._cfg = config.salvar({**self._cfg, "formato_arquivo": formato,
                                   "servico_esperado": " ".join(str(servico or "").split())})
        return {"config": self._cfg}

    @seguro
    def notas_regras_padrao(self):
        return {"formato": FORMATO_PADRAO, "servico": SERVICO_PADRAO}

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
        "responsavel": responsavel(n),
        "avisos": n.avisos,
    }


def _data_ou_nada(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None
