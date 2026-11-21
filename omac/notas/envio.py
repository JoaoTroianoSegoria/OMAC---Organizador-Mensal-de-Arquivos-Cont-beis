"""Parte da API que envia as notas ao paciente pelo WhatsApp: uma por vez ("Notas a enviar")
ou várias juntas (as escolhidas no Relatório mensal).

O link do WhatsApp só leva texto: os PDFs vão pela área de transferência, e quem aperta
enviar é sempre a pessoa.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from .. import config, sistema
from ..contatos import contatos as ct
from ..dados import esquema
from ..nucleo import ApiBase, seguro
from ..texto import normalizar
from ..whatsapp import mensagens as msg
from ..whatsapp import variaveis as vr
from .leitor import Nota, responsavel


class EnvioNotasApi(ApiBase):
    @contextmanager
    def _enviadas(self):
        with self._armazem.editar(esquema.NOTAS_ENVIADAS) as d:
            if not d["inicio"]:
                d["inicio"] = date.today().isoformat()
            yield d

    def _nota(self, numero: int) -> Nota:
        nota = next((n for n in self._servico_notas.atual().notas if n.numero == int(numero)), None)
        if nota is None:
            raise ValueError(f"Não encontrei a nota nº {numero} na pasta.")
        return nota

    @seguro
    def notas_a_enviar(self):
        if not self._cfg["pasta_notas"]:
            return {"sem_pasta": True}
        notas = self._servico_notas.atual().notas
        with self._enviadas() as d:
            inicio, enviadas = d["inicio"], d["enviadas"]
        pendentes = [n for n in notas if n.emissao.isoformat() >= inicio and str(n.numero) not in enviadas]
        pendentes.sort(key=lambda n: n.numero)
        return {
            "inicio": inicio,
            "notas": [{
                "numero": n.numero,
                "responsavel": responsavel(n),
                "dependente": n.paciente if n.dependente else "",
                "valor_centavos": int(n.valor * 100),
                "emissao": n.emissao.isoformat(),
                "competencia": n.competencia.isoformat(),
            } for n in pendentes],
        }

    @seguro
    def notas_enviadas(self):
        with self._enviadas() as d:
            return {"numeros": [int(n) for n in d["enviadas"]]}

    @seguro
    def notas_preparar_envio(self, numero: int):
        nota = self._nota(numero)
        nome = responsavel(nota)
        contato = ct.por_nome(self._lista_de_contatos(), nome) or {}
        return {
            "numero": nota.numero,
            "nome": nome,
            "telefone": contato.get("telefone", ""),
            "mensagem": vr.mensagem(self._cfg, nome, [nota]),
        }

    @seguro
    def notas_enviar(self, numero: int, telefone: str, mensagem: str):
        nota = self._nota(numero)
        telefone = msg.normalizar_telefone(telefone)
        nome = responsavel(nota)
        caminho = Path(self._cfg["pasta_notas"]) / nota.arquivo
        # Quem recebe a nota vira contato (ou ganha o telefone que acabou de ser usado).
        with self._armazem.editar(esquema.CONTATOS) as d:
            ct.obter(d["contatos"], nome)["telefone"] = telefone

        copiado = sistema.copiar_arquivo(caminho)
        msg.abrir_conversa(telefone, mensagem, self._cfg["whatsapp_destino"])
        if not copiado:
            sistema.mostrar_na_pasta(caminho)
        return {"pdf_copiado": copiado}

    @seguro
    def notas_marcar_enviada(self, numero: int, enviada: bool = True):
        with self._enviadas() as d:
            if enviada:
                d["enviadas"][str(int(numero))] = date.today().isoformat()
            else:
                d["enviadas"].pop(str(int(numero)), None)
        return {}

    # --- Várias notas de uma vez --------------------------------------------------------

    def _notas_do_lote(self, numeros: list) -> list[Nota]:
        numeros = sorted({int(n) for n in numeros or []})
        if not numeros:
            raise ValueError("Escolha pelo menos uma nota.")
        return [self._nota(n) for n in numeros]

    def _colar_disponivel(self) -> bool:
        return self._cfg["whatsapp_destino"] == "app" and sistema.colar_sozinho_disponivel()

    @seguro
    def notas_preparar_lote(self, numeros: list, contato_id: str = "", nome: str = ""):
        """As notas escolhidas e para quem mandar: o contato de quem recebe (se for uma pessoa só,
        já sugerido), o escolhido na lista de contatos (com cada responsável) ou um nome novo."""
        notas = self._notas_do_lote(numeros)
        contatos = self._lista_de_contatos()
        nomes = {normalizar(responsavel(n)): responsavel(n) for n in notas}
        mesma_pessoa = len(nomes) == 1
        nome_unico = " ".join((nome or "").split()) or (next(iter(nomes.values())) if mesma_pessoa else "")
        if contato_id:
            contato = ct.buscar(contatos, contato_id)
        else:
            contato = ct.por_nome(contatos, nome_unico) if nome_unico else None

        if contato:
            destinos = [{**d, "mensagem": vr.mensagem(self._cfg, d["nome"], notas)}
                        for d in ct.destinos(contatos, contato)]
            escolhido = ct.destino_escolhido(contatos, contato)["contato_id"]
        elif nome_unico:
            # Ainda não é contato: vira contato quando a mensagem for enviada.
            destinos = [{"contato_id": "", "nome": nome_unico, "telefone": "", "papel": "",
                         "mensagem": vr.mensagem(self._cfg, nome_unico, notas)}]
            escolhido = ""
        else:
            destinos, escolhido = [], ""
        return {
            "notas": [{
                "numero": n.numero,
                "paciente": n.paciente,
                "responsavel": responsavel(n),
                "valor_centavos": int(n.valor * 100),
                "competencia": n.competencia.isoformat(),
            } for n in notas],
            "total_centavos": sum(int(n.valor * 100) for n in notas),
            "mesma_pessoa": mesma_pessoa,
            "nome": contato["nome"] if contato else nome_unico,
            "contato_id": contato["id"] if contato else "",
            "destinos": destinos,
            "escolhido": escolhido,
            "contatos": sorted(({"id": c["id"], "nome": c["nome"], "telefone": c["telefone"]} for c in contatos),
                               key=lambda c: normalizar(c["nome"])),
            "colar_disponivel": self._colar_disponivel(),
            "colar_sozinho": self._cfg["colar_sozinho"],
        }

    @seguro
    def notas_enviar_lote(self, numeros: list, contato_id: str, destino_id: str, nome: str,
                          telefone: str, mensagem: str, colar: bool = False):
        """Copia todos os PDFs juntos, abre a conversa e (se pedido) tenta colar sozinho."""
        telefone = msg.normalizar_telefone(telefone)
        notas = self._notas_do_lote(numeros)
        pasta = Path(self._cfg["pasta_notas"])
        caminhos = [pasta / n.arquivo for n in notas]
        faltando = [n.numero for n, c in zip(notas, caminhos) if not c.is_file()]
        if faltando:
            return {"erro": f"Não encontrei o PDF da nota nº {faltando[0]}. Ele foi movido ou renomeado?"}

        with self._armazem.editar(esquema.CONTATOS) as d:
            contatos = d["contatos"]
            if contato_id:
                principal = ct.buscar(contatos, contato_id)
                destino_id = destino_id or principal["id"]
                if destino_id != principal["id"] and destino_id not in {
                        r["contato_id"] for r in principal["responsaveis"]}:
                    return {"erro": "Escolha para quem vai a mensagem."}
                ct.buscar(contatos, destino_id)["telefone"] = telefone
                principal["envia_para"] = "" if destino_id == principal["id"] else destino_id
            else:
                if not (nome or "").strip():
                    return {"erro": "Escolha para quem vai a mensagem."}
                ct.obter(contatos, nome)["telefone"] = telefone

        colar = bool(colar) and self._colar_disponivel()
        if colar != self._cfg["colar_sozinho"] and self._colar_disponivel():
            self._cfg = config.salvar({**self._cfg, "colar_sozinho": colar})

        copiado = sistema.copiar_arquivos(caminhos)
        msg.abrir_conversa(telefone, mensagem, self._cfg["whatsapp_destino"])
        if not copiado:
            sistema.mostrar_na_pasta(caminhos[0])
        colando = colar and copiado
        if colando:
            threading.Thread(target=self._colar_e_avisar, daemon=True).start()
        return {"pdf_copiado": copiado, "colando": colando, "qtd": len(notas)}

    # --- Os modelos da mensagem (Configurações → WhatsApp) -------------------------------

    def _vista_mensagens(self) -> dict:
        return {tipo: {"modelo": vr.modelo(self._cfg, tipo), "padrao": vr.PADROES[tipo],
                       "variaveis": [{"nome": k, "descricao": v} for k, v in vr.variaveis_do(tipo).items()]}
                for tipo in (vr.NOTA, vr.NOTAS)}

    @seguro
    def mensagens_modelos(self):
        return self._vista_mensagens()

    @seguro
    def mensagens_previa(self, tipo: str, texto: str):
        """Como a mensagem fica com uma nota de exemplo (inventada), e as variáveis que não existem."""
        tipo = vr.NOTAS if tipo == vr.NOTAS else vr.NOTA
        return vr.previa(texto, tipo, self._cfg["assistente_nome"])

    @seguro
    def mensagens_salvar(self, tipo: str, texto: str):
        """Guarda o modelo. Igual ao padrão (ou "voltar ao padrão") guarda vazio: segue o padrão."""
        tipo = vr.NOTAS if tipo == vr.NOTAS else vr.NOTA
        texto = vr.validar(texto, tipo)
        chave = "mensagem_notas" if tipo == vr.NOTAS else "mensagem_nota"
        self._cfg = config.salvar({**self._cfg, chave: "" if texto == vr.PADROES[tipo] else texto})
        return {**self._vista_mensagens(), "config": self._cfg}

    @seguro
    def mensagens_padrao(self, tipo: str):
        tipo = vr.NOTAS if tipo == vr.NOTAS else vr.NOTA
        chave = "mensagem_notas" if tipo == vr.NOTAS else "mensagem_nota"
        self._cfg = config.salvar({**self._cfg, chave: ""})
        return {**self._vista_mensagens(), "config": self._cfg}

    def _colar_e_avisar(self) -> None:
        colou = sistema.colar_quando_abrir()
        if self._janela is not None:
            self._janela.evaluate_js(f"window.omacColagem && window.omacColagem({str(colou).lower()})")

    @seguro
    def notas_marcar_enviadas(self, numeros: list, enviadas: bool = True):
        hoje = date.today().isoformat()
        with self._enviadas() as d:
            for n in {int(x) for x in numeros or []}:
                if enviadas:
                    d["enviadas"][str(n)] = hoje
                else:
                    d["enviadas"].pop(str(n), None)
        return {}
