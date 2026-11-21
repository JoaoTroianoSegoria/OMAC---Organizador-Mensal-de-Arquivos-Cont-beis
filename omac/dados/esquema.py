"""Os arquivos de dados do OMAC: nome, versão atual e conteúdo de um arquivo novo.

Regras (valem para qualquer arquivo novo):
- todo arquivo tem "versao"; mudar o formato = subir a versão + um passo em migracoes.py;
- campo novo com valor padrão não precisa de migração (o padrão completa o que faltar);
- ligação entre arquivos é sempre por id; o nome de uma pessoa só existe em contatos.json;
- um assunto por arquivo, e nada é regravado na virada do mês (a situação sai das datas).
"""

from __future__ import annotations

import copy

CONTATOS = "contatos.json"
TRATAMENTOS = "tratamentos.json"
ATENDIMENTOS = "atendimentos.json"
LEMBRETES = "lembretes.json"
NOTAS_ENVIADAS = "notas-enviadas.json"
COMANDOS = "comandos.json"
MODELOS = "modelos.json"

CONFIG = "config.json"
REGRAS = "regras-extrato.json"
CACHE_NOTAS = "cache-notas.json"

ARQUIVOS: dict[str, dict] = {
    # {"id", "nome", "telefone", "cpf", "responsaveis": [{"contato_id", "papel"}], "envia_para", "nota_para",
    #  "criado_em", "nascimento"}. O CPF fica só com os 11 números; "nota_para" é de quem foi o último CPF
    #  usado na nota; "nascimento" é AAAA-MM-DD ("" = não informado).
    # "a_conferir": nomes parecidos ou telefones diferentes que a migração não juntou sozinha.
    CONTATOS: {"versao": 1, "conteudo": "Os contatos", "padrao": {"contatos": [], "a_conferir": []}},
    # Ortodontia: {"id", "contato_id", "valor_centavos", situação, altas, atendidos, "criado_em"...}
    TRATAMENTOS: {"versao": 1, "conteudo": "Os pacientes de ortodontia", "padrao": {"tratamentos": []}},
    # Ficha: {"id", "contato_id", "tratamento", "data", "valor_centavos", "forma", "parcelas", "pago_em", "nota"}
    ATENDIMENTOS: {"versao": 1, "conteudo": "Os atendimentos da ficha", "padrao": {"atendimentos": []}},
    LEMBRETES: {"versao": 1, "conteudo": "As contas e os lembretes",
                "padrao": {"ultima_abertura": "", "destinatario": "", "contas": [], "livres": []}},
    NOTAS_ENVIADAS: {"versao": 1, "conteudo": "As notas já enviadas", "padrao": {"inicio": "", "enviadas": {}}},
    COMANDOS: {"versao": 1, "conteudo": "Os comandos", "padrao": {"categorias": []}},
    # Os arquivos ficam em modelos/<arquivo> (ver omac/modelos/modelos.py).
    MODELOS: {"versao": 1, "conteudo": "Os modelos", "padrao": {"modelos": []}},
}

# Campos de cada item das listas, com o valor padrão: {arquivo: {lista: campos}}. Quem foi
# gravado antes de um campo existir ganha o padrão ao ler (armazem.py), sem migração.
ITENS: dict[str, dict[str, dict]] = {
    CONTATOS: {"contatos": {"telefone": "", "cpf": "", "responsaveis": [], "envia_para": "", "nota_para": "",
                            "criado_em": "", "nascimento": ""}},
    TRATAMENTOS: {"tratamentos": {
        "valor_centavos": None, "agendado_em": "", "finalizado_em": "", "alta_inicio": "", "alta_fim": "",
        "atendidos": {},  # "AAAA-MM" → dia em que foi marcado como atendido
        "altas": [],  # altas que já acabaram: [{"inicio", "fim"}], para o histórico
        "criado_em": "",  # primeiro mês do histórico
    }},
    ATENDIMENTOS: {"atendimentos": {"tratamento": "", "valor_centavos": None, "forma": "", "parcelas": 1,
                                    "pago_em": "", "nota": ""}},
    # Contas: {"nome", "dia", "pagas": {"AAAA-MM": dia}, "criada_em"} (criada_em é preenchida em contas.py).
    # Livres: {"id", "titulo", "observacao", "criado_em", "feito_em"} ("" = em aberto) e a repetição:
    # "repetir" (nao | dia | semana | mes | data), "dia_semana" (0 = segunda), "dia_mes", "data",
    # "desde" (de quando contam as vezes) e "destinatario" (contato_id; "" = quem recebe os das contas).
    LEMBRETES: {"contas": {"pagas": {}}, "livres": {
        "observacao": "", "criado_em": "", "feito_em": "", "repetir": "nao", "dia_semana": 0, "dia_mes": 1,
        "data": "", "desde": "", "destinatario": ""}},
    # Categorias: {"id", "nome", "comandos": [{"id", "nome", "texto"}]}.
    COMANDOS: {"categorias": {"comandos": []}},
    # Modelos: {"id", "titulo", "arquivo", "nome_original", "criado_em"}.
    MODELOS: {"modelos": {"nome_original": "", "criado_em": ""}},
}


def completar_item(arquivo: str, item: dict, lista: str | None = None) -> dict:
    """O item com os campos que faltarem (cópia: o padrão nunca é alterado por um item).

    `lista` só é preciso quando o arquivo tem mais de uma lista.
    """
    listas = ITENS[arquivo]
    padrao = listas[lista] if lista else next(iter(listas.values()))
    return {**copy.deepcopy(padrao), **item}


# O que vai no backup. O cache das notas fica de fora: ele é refeito lendo os PDFs.
DO_BACKUP = [CONFIG, *ARQUIVOS, REGRAS]
