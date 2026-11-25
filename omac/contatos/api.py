"""Parte da API que cuida dos contatos (e da janela de contato, que também liga a ortodontia)."""

from __future__ import annotations

from datetime import date

from .. import config, sistema
from ..dados import esquema
from ..inicio.registro import widget
from ..nucleo import ApiBase, seguro
from ..texto import normalizar
from ..tratamentos import orto
from ..whatsapp.mensagens import abrir_conversa, normalizar_telefone
from . import contatos as ct
from . import cpf as cpfs


class ContatosApi(ApiBase):
    # --- Para os outros módulos --------------------------------------------------------

    def _lista_de_contatos(self) -> list[dict]:
        return self._armazem.ler(esquema.CONTATOS)["contatos"]

    def _nomes_dos_contatos(self) -> dict[str, str]:
        return ct.nomes(self._lista_de_contatos())

    # --- Lista ---------------------------------------------------------------------------

    def _vista_contatos(self) -> dict:
        dados = self._armazem.ler(esquema.CONTATOS)
        contatos = dados["contatos"]
        nomes = ct.nomes(contatos)
        tratamentos = {t["contato_id"]: t for t in self._armazem.ler(esquema.TRATAMENTOS)["tratamentos"]}
        qtd_atendimentos: dict[str, int] = {}
        for a in self._armazem.ler(esquema.ATENDIMENTOS)["atendimentos"]:
            qtd_atendimentos[a["contato_id"]] = qtd_atendimentos.get(a["contato_id"], 0) + 1
        destinatario = self._armazem.ler(esquema.LEMBRETES)["destinatario"]
        por_id = {c["id"]: c for c in contatos}

        lista = []
        for c in sorted(contatos, key=lambda c: normalizar(c["nome"])):
            t = tratamentos.get(c["id"])
            lista.append({
                **c,
                "responsaveis": [{**r, "nome": nomes.get(r["contato_id"], "?"),
                                  "telefone": por_id.get(r["contato_id"], {}).get("telefone", ""),
                                  "cpf": por_id.get(r["contato_id"], {}).get("cpf", ""),
                                  "papel_texto": ct.PAPEIS.get(r["papel"], "responsável")}
                                 for r in c["responsaveis"] if r["contato_id"] in nomes],
                "dependentes": [d["nome"] for d in ct.dependentes(contatos, c["id"])],
                "tratamento": None if t is None else {
                    "id": t["id"], "situacao": orto.situacao(t), "valor_centavos": t["valor_centavos"],
                    "alta_inicio": t["alta_inicio"], "alta_fim": t["alta_fim"]},
                "atendimentos": qtd_atendimentos.get(c["id"], 0),
                "recebe_lembretes": c["id"] == destinatario,
            })
        conferir = []
        for item in ct.a_conferir_validos(dados["a_conferir"], contatos):
            if item["tipo"] == ct.PARECIDOS:
                conferir.append({**item, "nomes": [nomes[i] for i in item["ids"]],
                                 "telefones": [por_id[i]["telefone"] for i in item["ids"]]})
            else:
                conferir.append({**item, "nome": nomes[item["id"]], "atual": por_id[item["id"]]["telefone"]})
        return {"contatos": lista, "a_conferir": conferir}

    @seguro
    def contatos_listar(self):
        return self._vista_contatos()

    # --- Salvar (com a ortodontia) --------------------------------------------------------

    @seguro
    def contatos_salvar(self, dados: dict, contato_id: str | None = None):
        """`dados`: nome, telefone, responsaveis e, se `orto`, valor e situação da manutenção.

        Desligar a ortodontia de quem tinha tira o paciente de Tratamentos (dá para desfazer).
        """
        hoje = date.today()
        tratamento_apagado = None
        with self._armazem.editar(esquema.CONTATOS) as d, self._armazem.editar(esquema.TRATAMENTOS) as t:
            contatos = d["contatos"]
            tratamentos = t["tratamentos"]
            # Valida a ortodontia antes de gravar o contato: um erro não deixa nada pela metade.
            if dados.get("orto"):
                orto.validar(dados, None, hoje)
            contato = ct.salvar(contatos, dados, contato_id, hoje)
            atual = orto.do_contato(tratamentos, contato["id"])
            if dados.get("orto"):
                orto.salvar(tratamentos, contato["id"], dados, hoje)
            elif atual is not None:
                tratamentos.remove(atual)
                tratamento_apagado = atual
        return {**self._vista_contatos(), "salvo": contato, "tratamento_apagado": tratamento_apagado}

    @seguro
    def contatos_restaurar_tratamento(self, tratamento: dict):
        with self._armazem.editar(esquema.TRATAMENTOS) as t:
            tratamentos = t["tratamentos"]
            orto.restaurar(tratamentos, tratamento)
        return self._vista_contatos()

    # --- Apagar e desfazer ------------------------------------------------------------------

    @seguro
    def contatos_apagar(self, contato_id: str):
        atendimentos = [a for a in self._armazem.ler(esquema.ATENDIMENTOS)["atendimentos"]
                        if a["contato_id"] == contato_id]
        if atendimentos:
            n = len(atendimentos)
            return {"erro": f"Esse contato tem {n} {'atendimento' if n == 1 else 'atendimentos'} na ficha de "
                            "Atendimentos, então não pode ser apagado. Para corrigir o nome, use o lápis."}
        with self._armazem.editar(esquema.CONTATOS) as d, self._armazem.editar(esquema.TRATAMENTOS) as t, \
                self._armazem.editar(esquema.LEMBRETES) as lb:
            contatos = d["contatos"]
            contato = ct.buscar(contatos, contato_id)
            contatos.remove(contato)
            pacote = {
                "contato": contato,
                "vinculos": ct.tirar_vinculos(contatos, contato_id),
                "tratamento": next((x for x in t["tratamentos"] if x["contato_id"] == contato_id), None),
                "recebia_lembretes": lb["destinatario"] == contato_id,
            }
            t["tratamentos"] = [x for x in t["tratamentos"] if x["contato_id"] != contato_id]
            if pacote["recebia_lembretes"]:
                lb["destinatario"] = ""
        return {**self._vista_contatos(), "apagado": pacote}

    @seguro
    def contatos_restaurar(self, pacote: dict):
        contato = ct.completar(pacote["contato"])
        with self._armazem.editar(esquema.CONTATOS) as d, self._armazem.editar(esquema.TRATAMENTOS) as t, \
                self._armazem.editar(esquema.LEMBRETES) as lb:
            contatos = d["contatos"]
            if any(c["id"] == contato["id"] for c in contatos):
                return self._vista_contatos()
            ct.conferir_nome(contatos, contato["nome"])
            contatos.append(contato)
            ct.devolver_vinculos(contatos, pacote.get("vinculos") or [])
            if pacote.get("tratamento"):
                tratamentos = t["tratamentos"]
                orto.restaurar(tratamentos, pacote["tratamento"])
            if pacote.get("recebia_lembretes") and not lb["destinatario"]:
                lb["destinatario"] = contato["id"]
        return self._vista_contatos()

    # --- Conferir contatos -----------------------------------------------------------------

    @seguro
    def contatos_juntar(self, manter_id: str, tirar_id: str):
        """Os dois são a mesma pessoa: tudo o que era de `tirar_id` passa para `manter_id`."""
        if manter_id == tirar_id:
            return {"erro": "Escolha dois contatos diferentes."}
        with self._armazem.editar(esquema.CONTATOS) as d, self._armazem.editar(esquema.TRATAMENTOS) as t, \
                self._armazem.editar(esquema.ATENDIMENTOS) as at, self._armazem.editar(esquema.LEMBRETES) as lb:
            contatos = d["contatos"]
            manter, tirar = ct.buscar(contatos, manter_id), ct.buscar(contatos, tirar_id)
            dono = {x["contato_id"] for x in t["tratamentos"]}
            if manter_id in dono and tirar_id in dono:
                return {"erro": f"“{manter['nome']}” e “{tirar['nome']}” estão os dois em Tratamentos. "
                                "Tire um deles da ortodontia antes de juntar."}
            ct.juntar(manter, tirar)
            contatos.remove(tirar)
            ct.trocar_id(contatos, tirar_id, manter_id)
            for x in t["tratamentos"]:
                if x["contato_id"] == tirar_id:
                    x["contato_id"] = manter_id
            for a in at["atendimentos"]:
                if a["contato_id"] == tirar_id:
                    a["contato_id"] = manter_id
            if lb["destinatario"] == tirar_id:
                lb["destinatario"] = manter_id
            for x in lb["livres"]:
                if x.get("destinatario") == tirar_id:
                    x["destinatario"] = manter_id
            d["a_conferir"] = ct.a_conferir_validos(d["a_conferir"], contatos)
        return {**self._vista_contatos(), "juntados": [manter["nome"], tirar["nome"]]}

    @seguro
    def contatos_sao_diferentes(self, ids: list[str]):
        with self._armazem.editar(esquema.CONTATOS) as d:
            d["a_conferir"] = [i for i in d["a_conferir"]
                               if not (i.get("tipo") == ct.PARECIDOS and sorted(i.get("ids", [])) == sorted(ids))]
        return self._vista_contatos()

    @seguro
    def contatos_escolher_telefone(self, contato_id: str, telefone: str):
        with self._armazem.editar(esquema.CONTATOS) as d:
            contatos = d["contatos"]
            ct.buscar(contatos, contato_id)["telefone"] = ct.telefone(telefone)
            d["a_conferir"] = [i for i in d["a_conferir"]
                               if not (i.get("tipo") == ct.TELEFONE and i.get("id") == contato_id)]
        return self._vista_contatos()

    # --- Mensagem pelo WhatsApp para o paciente ou um responsável ------------------------------

    def _mensagem_para(self, paciente_id: str, destino_id: str, telefone: str, mensagem: str) -> dict | None:
        """Guarda o telefone em quem recebe, lembra a escolha (envia_para) e abre a conversa.
        Usado por Tratamentos e pela cobrança de Atendimentos. Devolve um erro, ou None."""
        telefone = normalizar_telefone(telefone)
        with self._armazem.editar(esquema.CONTATOS) as d:
            contatos = d["contatos"]
            paciente = ct.buscar(contatos, paciente_id)
            if destino_id != paciente["id"] and destino_id not in {r["contato_id"] for r in paciente["responsaveis"]}:
                return {"erro": "Escolha para quem vai a mensagem."}
            ct.buscar(contatos, destino_id)["telefone"] = telefone
            paciente["envia_para"] = "" if destino_id == paciente["id"] else destino_id
        abrir_conversa(telefone, mensagem, self._cfg["whatsapp_destino"])
        return None

    # --- CPF e a janela "Emitir nota" -------------------------------------------------------

    def _notas_lidas(self) -> list:
        """As notas da pasta (do cache), para sugerir o CPF. Sem pasta, nenhuma."""
        v = self._servico_notas.ou_nada()
        return v.notas if v is not None else []

    def _sugestao_cpf(self, pessoa: dict, notas: list) -> dict | None:
        s = cpfs.sugestao(pessoa["nome"], notas)
        if s is None or s["cpf"] == pessoa["cpf"]:
            return None
        return {"cpf": cpfs.formatar(s["cpf"]), "numero": s["numero"]}

    def _vista_cpf(self, contato_id: str) -> dict:
        contatos = self._lista_de_contatos()
        contato = ct.buscar(contatos, contato_id)
        notas = self._notas_lidas()
        pessoas = []
        for d in ct.destinos(contatos, contato):
            pessoa = ct.buscar(contatos, d["contato_id"])
            pessoas.append({"contato_id": pessoa["id"], "nome": pessoa["nome"], "papel": d["papel"],
                            "cpf": cpfs.formatar(pessoa["cpf"]) if pessoa["cpf"] else "",
                            "nascimento": pessoa.get("nascimento", ""),
                            "sugestao": self._sugestao_cpf(pessoa, notas)})
        tem = {p["contato_id"] for p in pessoas if p["cpf"] or p["sugestao"]}
        return {"id": contato["id"], "nome": contato["nome"], "pessoas": pessoas,
                "escolhido": ct.escolha_da_nota(contatos, contato, lambda i: i in tem),
                "site": self._cfg.get("site_nota", ""),
                "categoria": self._cfg.get("emissao_categoria", ""),
                "proximo_numero": self._servico_notas.proximo_numero()}

    @seguro
    def contatos_cpf(self, contato_id: str):
        """Para a janela "Emitir nota": o paciente, os responsáveis e o CPF de cada um."""
        return self._vista_cpf(contato_id)

    @seguro
    def contatos_salvar_cpf(self, contato_id: str, pessoa_id: str, cpf: str):
        """Guarda o CPF de uma pessoa (o paciente ou um responsável). Vazio apaga."""
        with self._armazem.editar(esquema.CONTATOS) as d:
            contatos = d["contatos"]
            contato = ct.buscar(contatos, contato_id)
            pessoa = ct.buscar(contatos, pessoa_id)
            pessoa["cpf"] = ct.cpf(cpf)
            if pessoa["cpf"]:
                contato["nota_para"] = pessoa_id
        return self._vista_cpf(contato_id)

    @seguro
    def contatos_salvar_nascimento(self, contato_id: str, pessoa_id: str, data: str):
        """Data de nascimento de uma pessoa da janela Emitir (o dependente, quase sempre). Vazio apaga."""
        with self._armazem.editar(esquema.CONTATOS) as d:
            contatos = d["contatos"]
            ct.buscar(contatos, contato_id)
            ct.buscar(contatos, pessoa_id)["nascimento"] = ct.nascimento(data)
        return self._vista_cpf(contato_id)

    @seguro
    def contatos_categoria_emissao(self, categoria_id: str):
        """Qual categoria de Comandos aparece ao lado, na janela Emitir (fica guardada)."""
        self._cfg = config.salvar({**self._cfg, "emissao_categoria": str(categoria_id or "")})
        return {}

    @seguro
    def contatos_nota_para(self, contato_id: str, pessoa_id: str):
        """Lembra de quem é o CPF da nota desse paciente, para a próxima vez já vir escolhido."""
        with self._armazem.editar(esquema.CONTATOS) as d:
            contatos = d["contatos"]
            contato = ct.buscar(contatos, contato_id)
            if pessoa_id in {x["contato_id"] for x in ct.destinos(contatos, contato)}:
                contato["nota_para"] = pessoa_id
        return {}

    @seguro
    def abrir_site_nota(self):
        site = self._cfg.get("site_nota", "").strip()
        if not site:
            return {"erro": "Coloque o endereço do site da nota em Configurações → Notas fiscais."}
        if not site.lower().startswith(("http://", "https://")):
            site = "https://" + site
        try:
            sistema.abrir_link(site)
        except OSError:
            return {"erro": "Não consegui abrir o site. Confira o endereço em Configurações → Notas fiscais."}
        return {}

    @seguro
    def contatos_sugestao_cpf(self, nome: str):
        """O CPF achado nas notas para esse nome (a janela de contato oferece usar)."""
        s = cpfs.sugestao(nome, self._notas_lidas()) if nome.strip() else None
        return {"sugestao": {"cpf": cpfs.formatar(s["cpf"]), "numero": s["numero"]} if s else None}

    # --- Widget do Início --------------------------------------------------------------------

    @widget("contatos", "Contatos", ordem=60)
    def _widget_contatos(self, hoje: date) -> dict:
        dados = self._armazem.ler(esquema.CONTATOS)
        contatos = dados["contatos"]
        return {
            "total": len(contatos),
            "sem_telefone": sum(not c["telefone"] for c in contatos),
            "a_conferir": len(ct.a_conferir_validos(dados["a_conferir"], contatos)),
            "novos_no_mes": sum(c["criado_em"][:7] == hoje.isoformat()[:7] for c in contatos),
        }
