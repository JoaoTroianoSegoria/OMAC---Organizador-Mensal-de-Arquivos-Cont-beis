"""Parte da API que cuida das notas fiscais."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from .. import config, sistema
from ..contatos import cpf as cpfs
from ..nucleo import ApiBase, seguro
from ..texto import mesma_pessoa, normalizar
from . import exportar as exp
from . import pesquisa
from .leitor import (FORMATO_PADRAO, SERVICO_PADRAO, FormatoInvalido, Regras, compilar_formato, ler_nome_arquivo,
                     nome_certo, problema_no_nome, responsavel)


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
            "notas": self._notas_para_js(notas),
            "total_centavos": sum(int(n.valor * 100) for n in notas),
            "avisos": v.avisos,
            "canceladas_movidas": v.canceladas_movidas,
            "competencias": v.competencias(),
            "qtd_pasta": len(v.notas),
            **self._leitura_das_notas(),
        }

    @seguro
    def notas_conferir(self):
        """Chamado quando o OMAC volta para a frente: só diz se a pasta mudou (não lê nada)."""
        return {"mudou": self._servico_notas.mudou()}

    def _leitura_das_notas(self) -> dict:
        s = self._servico_notas
        contatos = self._lista_de_contatos() if s.novas else []
        return {
            "lida_em": s.lida_em.strftime("%H:%M") if s.lida_em else "",
            "novas": [{"numero": n.numero, "paciente": n.paciente, "renomear": self._renomear(n, contatos)}
                      for n in s.novas],
        }

    def _notas_para_js(self, notas) -> list[dict]:
        contatos = self._lista_de_contatos()  # uma leitura só, para todas as notas com o nome errado
        return [{**_nota_para_js(n), "renomear": self._renomear(n, contatos)} for n in notas]

    # --- Nome do arquivo errado (o site baixa o PDF com um nome só de números) ------------

    @staticmethod
    def _nome_de_quem_recebe(nota, contatos: list[dict]) -> str:
        """O nome do arquivo é o de quem recebe a nota (o tomador). Do contato, se achar (pelo
        CPF ou pelo nome), para sair escrito como nos Contatos; senão, como está no PDF."""
        if nota.cpf_tomador:
            achado = next((c for c in contatos if c.get("cpf") and cpfs.digitos(c["cpf"]) == nota.cpf_tomador), None)
            if achado:
                return achado["nome"]
        nome = nota.tomador or nota.paciente
        if nome and nome != "(sem nome)":
            iguais = [c for c in contatos if normalizar(c["nome"]) == normalizar(nome)]
            parecidos = iguais or [c for c in contatos if mesma_pessoa(c["nome"], nome)]
            if len(parecidos) == 1:
                return parecidos[0]["nome"]
            return nome
        return ""

    def _renomear(self, nota, contatos: list[dict]) -> dict | None:
        """Sugestão de nome certo para o PDF, ou None se o nome dele já está certo."""
        regras = self._regras_notas()
        motivo = problema_no_nome(nota, regras)
        if not motivo:
            return None
        nome = self._nome_de_quem_recebe(nota, contatos)
        if not nome:
            return None
        return {"motivo": motivo, "de": nota.arquivo, "nome": nome, "para": nome_certo(nota, nome, regras)}

    @seguro
    def notas_renomear(self, arquivo: str, novo: str):
        """Renomeia o PDF de uma nota na pasta, sem passar por cima de outro arquivo.
        Depois a tela lê a pasta de novo (só esse PDF é lido; os outros vêm do cache)."""
        pasta = self._servico_notas.pasta()
        origem = pasta / Path(arquivo).name
        if not origem.is_file():
            return {"erro": f"Não encontrei o arquivo “{arquivo}”. Ele foi movido ou renomeado?"}
        novo = " ".join(str(novo or "").split())
        if novo.lower().endswith(".pdf"):
            novo = novo[:-4].rstrip()
        if not novo or any(c in novo for c in '<>:"/\\|?*') or novo.strip(". ") != novo:
            return {"erro": 'O nome não pode ficar vazio, terminar com ponto nem ter / \\ : * ? " < > |'}
        novo += ".pdf"
        nota = next((n for n in (self._servico_notas.todas() or []) if n.arquivo == origem.name), None)
        lido = ler_nome_arquivo(novo, self._regras_notas())
        if lido is None:
            return {"erro": "Esse nome não segue o formato das Configurações → Notas fiscais. "
                            "O OMAC não conseguiria ler o número e o nome dele."}
        if nota is not None and lido[0] != nota.numero:
            return {"erro": f"O número no nome ({lido[0]}) é diferente do número da nota ({nota.numero})."}
        destino = pasta / novo
        if destino.name == origem.name:
            return {"arquivo": novo}
        # Mesmo nome com outras maiúsculas é o próprio arquivo (o Windows não diferencia).
        if destino.exists() and not (destino.name.lower() == origem.name.lower() and destino.samefile(origem)):
            return {"erro": f"Já existe um arquivo com o nome “{novo}” na pasta. Nada foi mudado."}
        try:
            os.rename(origem, destino)
        except PermissionError:
            return {"erro": "Não consegui renomear: o PDF está aberto em outro programa? Feche e tente de novo."}
        except OSError as e:
            return {"erro": f"Não consegui renomear o arquivo ({e.strerror or e})."}
        return {"arquivo": novo}

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
            "notas": self._notas_para_js(achadas),
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
