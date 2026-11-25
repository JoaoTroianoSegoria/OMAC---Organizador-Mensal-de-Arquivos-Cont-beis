"""Todas as mensagens do WhatsApp que dá para mudar (Configurações → Mensagens).

Cada tipo tem um texto para a conversa com o próprio contato (o paciente, ou quem está na nota) e
outro para a conversa com um responsável dele. Os lembretes têm um texto só. A pessoa escreve do
jeito dela e põe [variáveis] no meio; texto vazio nas Configurações quer dizer o padrão.

Guardado em cfg["mensagens"] = {"agendar": {"paciente": "...", "responsavel": ""}, ...}.
Mensagem nova entra em TIPOS (com padrões, variáveis e exemplo) e aparece sozinha na tela.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from . import variaveis as vr

PACIENTE, RESPONSAVEL, UNICO = "paciente", "responsavel", "unico"
ROTULOS_PACIENTE = {PACIENTE: "Para o paciente", RESPONSAVEL: "Para o responsável"}
ROTULOS_NOTA = {PACIENTE: "Para quem está na nota", RESPONSAVEL: "Para um responsável"}

# Tipos
AGENDAR, CONFIRMAR, PIX_MANUTENCAO, RETORNO = "agendar", "confirmar", "pix_manutencao", "retorno"
COBRANCA, NOTA, NOTAS = "cobranca", "nota", "notas"
LEMBRETE_CONTAS, LEMBRETE_LIVRE = "lembrete_contas", "lembrete_livre"


@dataclass(frozen=True)
class Tipo:
    chave: str
    grupo: str  # a tela de onde a mensagem sai
    titulo: str
    dica: str
    padroes: dict[str, str]  # versão → texto padrão
    variaveis: dict[str, str]
    rotulos: dict[str, str] = field(default_factory=dict)  # versão → nome da aba


def _ola(quem: str) -> str:
    return f"[assinatura]Olá, [primeiro-nome-do-{quem}].\n"


_FIM_AGENDAR = " Me diga qual dia e horário ficam melhores para você."
_FIM_PIX = ":\n\n[chave-pix]\n\nDepois me envie o comprovante, por favor."

TIPOS = [
    Tipo(AGENDAR, "Tratamentos", "Agendar manutenção",
         "Tratamentos → botão do WhatsApp, quando o dia da consulta ainda não foi marcado.",
         {PACIENTE: _ola("paciente") + "Vamos agendar a sua manutenção do aparelho para [mes-atual]?" + _FIM_AGENDAR,
          RESPONSAVEL: _ola("responsavel") + "Vamos agendar a manutenção do aparelho de [primeiro-nome-do-paciente] "
                                             "para [mes-atual]?" + _FIM_AGENDAR},
         vr.VARIAVEIS_DO_TRATAMENTO, ROTULOS_PACIENTE),
    Tipo(CONFIRMAR, "Tratamentos", "Confirmar o dia da manutenção",
         "Vai no lugar de “Agendar manutenção” quando o dia da consulta já está marcado.",
         {PACIENTE: _ola("paciente") + "Passando para confirmar a sua manutenção do aparelho na [dia-da-consulta]. "
                                       "Está tudo certo para esse dia?",
          RESPONSAVEL: _ola("responsavel") + "Passando para confirmar a manutenção do aparelho de "
                                             "[primeiro-nome-do-paciente] na [dia-da-consulta]. "
                                             "Está tudo certo para esse dia?"},
         {**vr.VARIAVEIS_DO_TRATAMENTO, **vr.VARIAVEIS_DA_CONSULTA}, ROTULOS_PACIENTE),
    Tipo(PIX_MANUTENCAO, "Tratamentos", "Cobrar a manutenção (Pix)",
         "Precisa da chave Pix, preenchida em WhatsApp.",
         {PACIENTE: _ola("paciente") + "Segue a chave Pix para o pagamento da manutenção de [mes-atual], "
                                       "no valor de [valor]" + _FIM_PIX,
          RESPONSAVEL: _ola("responsavel") + "Segue a chave Pix para o pagamento da manutenção de "
                                             "[primeiro-nome-do-paciente], referente a [mes-atual], "
                                             "no valor de [valor]" + _FIM_PIX},
         {**vr.VARIAVEIS_DO_TRATAMENTO, **vr.VARIAVEIS_DO_PIX}, ROTULOS_PACIENTE),
    Tipo(RETORNO, "Tratamentos", "Agendar retorno", "Tratamentos → botão do WhatsApp → Agendar retorno.",
         {PACIENTE: _ola("paciente") + "Está na hora de agendar o seu retorno." + _FIM_AGENDAR,
          RESPONSAVEL: _ola("responsavel") + "Está na hora de agendar o retorno de [primeiro-nome-do-paciente]."
          + _FIM_AGENDAR},
         vr.VARIAVEIS_DO_TRATAMENTO, ROTULOS_PACIENTE),
    Tipo(COBRANCA, "Atendimentos", "Cobrar um atendimento",
         "Vai pelo botão do WhatsApp em Atendimentos, nas linhas que ainda não foram pagas.",
         {PACIENTE: _ola("paciente") + "Passando para lembrar do pagamento do seu atendimento em "
                                       "[data-do-atendimento] ([tratamento]), no valor de [valor].\n"
                                       "Segue a chave Pix: [chave-pix]\nDepois me envie o comprovante, por favor.",
          RESPONSAVEL: _ola("responsavel") + "Passando para lembrar do pagamento do atendimento de "
                                             "[primeiro-nome-do-paciente] em [data-do-atendimento] ([tratamento]), "
                                             "no valor de [valor].\nSegue a chave Pix: [chave-pix]\n"
                                             "Depois me envie o comprovante, por favor."},
         vr.VARIAVEIS_DA_COBRANCA, ROTULOS_PACIENTE),
    Tipo(NOTA, "Notas fiscais", "Enviar uma nota", "Ao enviar uma nota pelo WhatsApp.",
         {v: _ola("responsavel") + "Segue a nota fiscal referente ao tratamento odontológico realizado dia "
                                   "[data-competencia]." for v in (PACIENTE, RESPONSAVEL)},
         vr.VARIAVEIS, ROTULOS_NOTA),
    Tipo(NOTAS, "Notas fiscais", "Enviar várias notas juntas", "Ao enviar mais de uma nota na mesma mensagem.",
         {v: _ola("responsavel") + "Seguem as [quantidade-de-notas] notas fiscais referentes ao tratamento "
                                   "odontológico:\n[lista-das-notas]" for v in (PACIENTE, RESPONSAVEL)},
         {**vr.VARIAVEIS, **vr.VARIAVEIS_SO_DE_VARIAS}, ROTULOS_NOTA),
    Tipo(LEMBRETE_CONTAS, "Lembretes", "Lembrete de contas", "Lembretes → contas a vencer.",
         {UNICO: "[assinatura]Olá, [nome-de-quem-recebe].\nLembrete de pagamento:\n[lista-das-contas]"},
         {**vr.VARIAVEIS_DO_LEMBRETE, **vr.VARIAVEIS_DAS_CONTAS}),
    Tipo(LEMBRETE_LIVRE, "Lembretes", "Outros lembretes", "Lembretes → os que você cria (Novo lembrete).",
         {UNICO: "[assinatura]Olá, [nome-de-quem-recebe].\nLembrete: [titulo]\n[observacao]"},
         {**vr.VARIAVEIS_DO_LEMBRETE, **vr.VARIAVEIS_DO_LEMBRETE_LIVRE}),
]
POR_CHAVE = {t.chave: t for t in TIPOS}


def tipo(chave: str) -> Tipo:
    if chave not in POR_CHAVE:
        raise ValueError("Mensagem desconhecida.")
    return POR_CHAVE[chave]


def versao_certa(t: Tipo, versao: str) -> str:
    if versao not in t.padroes:
        raise ValueError("Versão da mensagem desconhecida.")
    return versao


def versao_para(papel: str) -> str:
    """O destino com papel (mãe, pai, responsável) é um responsável; sem papel, o próprio contato."""
    return RESPONSAVEL if papel else PACIENTE


def modelo(cfg: dict, chave: str, versao: str) -> str:
    """O texto das Configurações, ou o padrão."""
    t = tipo(chave)
    if versao not in t.padroes:
        versao = next(iter(t.padroes))
    return (cfg.get("mensagens") or {}).get(chave, {}).get(versao) or t.padroes[versao]


def montar(cfg: dict, chave: str, versao: str, valores: dict[str, str]) -> str:
    return vr.limpar(vr.preencher(modelo(cfg, chave, versao), valores))


def usa(cfg: dict, chave: str, versao: str, variavel: str) -> bool:
    return f"[{variavel}]" in modelo(cfg, chave, versao).replace(" ", "").lower()


# --- Configurações ---------------------------------------------------------------------


def validar(texto: str, chave: str) -> str:
    """O texto como vai ser guardado. Variável escrita errada não deixa salvar."""
    texto = str(texto or "").replace("\r\n", "\n").strip()
    if not texto:
        raise vr.ModeloInvalido("A mensagem não pode ficar vazia. Para voltar ao texto de antes, use “Voltar ao padrão”.")
    erradas = vr.desconhecidas(texto, tipo(chave).variaveis)
    if erradas:
        lista = ", ".join(f"[{v}]" for v in erradas)
        raise vr.ModeloInvalido(f"Não conheço {lista}. Use os botões para pôr as variáveis certas.")
    return texto


def com_texto(cfg: dict, chave: str, versao: str, texto: str | None) -> dict:
    """As mensagens do cfg com este texto trocado. Igual ao padrão (ou None) guarda vazio: segue o padrão."""
    t = tipo(chave)
    versao_certa(t, versao)
    if texto is not None:
        texto = validar(texto, chave)
    mensagens = {k: dict(v) for k, v in (cfg.get("mensagens") or {}).items()}
    mensagens.setdefault(chave, {})[versao] = "" if texto is None or texto == t.padroes[versao] else texto
    return mensagens


def vista(cfg: dict) -> list[dict]:
    """Os grupos (Tratamentos, Atendimentos…) com cada mensagem, na ordem da tela."""
    grupos: dict[str, list] = {}
    for t in TIPOS:
        grupos.setdefault(t.grupo, []).append({
            "tipo": t.chave, "titulo": t.titulo, "dica": t.dica,
            "variaveis": [{"nome": k, "descricao": v} for k, v in t.variaveis.items()],
            "versoes": [{"versao": v, "rotulo": t.rotulos.get(v, ""), "modelo": modelo(cfg, t.chave, v),
                         "padrao": padrao, "mudada": modelo(cfg, t.chave, v) != padrao}
                        for v, padrao in t.padroes.items()],
        })
    return [{"nome": nome, "mensagens": lista} for nome, lista in grupos.items()]


# Exemplo da prévia (inventado: nenhum dado real aparece na tela de Configurações).
EXEMPLO_PACIENTE = "LUCAS COSTA RIBEIRO"
EXEMPLO_RESPONSAVEL = "FERNANDA COSTA"
EXEMPLO_HOJE = date(2026, 10, 30)
EXEMPLO_NOTAS = {
    NOTA: [vr.NotaDaMensagem(836, EXEMPLO_PACIENTE, date(2026, 10, 30), date(2026, 10, 30), Decimal("180.00"))],
    NOTAS: [vr.NotaDaMensagem(836, EXEMPLO_PACIENTE, date(2026, 10, 2), date(2026, 10, 2), Decimal("180.00")),
            vr.NotaDaMensagem(837, EXEMPLO_PACIENTE, date(2026, 10, 16), date(2026, 10, 16), Decimal("180.00")),
            vr.NotaDaMensagem(838, "SOFIA COSTA RIBEIRO", date(2026, 10, 16), date(2026, 10, 17), Decimal("250.00"))],
}


def _exemplo(chave: str, versao: str, assistente: str) -> dict[str, str]:
    quem = EXEMPLO_PACIENTE if versao == PACIENTE else EXEMPLO_RESPONSAVEL
    if chave in EXEMPLO_NOTAS:
        return vr.valores(assistente, EXEMPLO_RESPONSAVEL, EXEMPLO_NOTAS[chave])
    if chave == COBRANCA:
        return vr.valores_cobranca(assistente, quem, EXEMPLO_PACIENTE, EXEMPLO_HOJE, "Manutenção", 18000,
                                   "chave@exemplo.com")
    if chave in (LEMBRETE_CONTAS, LEMBRETE_LIVRE):
        contas = [{"nome": "Aluguel", "situacao": "vence amanhã (31/10)"},
                  {"nome": "Internet", "situacao": "vence hoje (30/10)"}]
        return vr.valores_lembrete(assistente, "Dra. Exemplo", contas, "Ligar para o laboratório",
                                   "Pedir a moldagem do Lucas.")
    return vr.valores_tratamento(assistente, quem, EXEMPLO_PACIENTE, EXEMPLO_HOJE, "2026-11-06", 18000,
                                 "chave@exemplo.com")


def previa(chave: str, versao: str, texto: str, assistente: str) -> dict:
    t = tipo(chave)
    versao_certa(t, versao)
    texto = str(texto or "")
    return {"texto": vr.limpar(vr.preencher(texto, _exemplo(chave, versao, assistente))),
            "desconhecidas": vr.desconhecidas(texto, t.variaveis)}


# --- As mensagens prontas ----------------------------------------------------------------


def nota(cfg: dict, destinatario: str, papel: str, notas: list) -> str:
    """Uma nota usa o modelo de uma nota; mais de uma, o de várias."""
    lista = [vr.NotaDaMensagem(n.numero, n.paciente, n.competencia, n.emissao, n.valor) for n in notas]
    return montar(cfg, NOTA if len(notas) == 1 else NOTAS, versao_para(papel),
                  vr.valores(cfg.get("assistente_nome", ""), destinatario, lista))


def cobranca(cfg: dict, destinatario: str, papel: str, paciente: str, dia: date, tratamento: str,
             valor_centavos: int | None) -> str:
    v = vr.valores_cobranca(cfg.get("assistente_nome", ""), destinatario, paciente, dia, tratamento,
                            valor_centavos, cfg.get("chave_pix", ""))
    return montar(cfg, COBRANCA, versao_para(papel), v)


def lembrete_contas(cfg: dict, destinatario: str, contas: list[dict]) -> str:
    return montar(cfg, LEMBRETE_CONTAS, UNICO, vr.valores_lembrete(cfg.get("assistente_nome", ""), destinatario,
                                                                    contas))


def lembrete_livre(cfg: dict, destinatario: str, titulo: str, observacao: str = "") -> str:
    return montar(cfg, LEMBRETE_LIVRE, UNICO, vr.valores_lembrete(cfg.get("assistente_nome", ""), destinatario,
                                                                   titulo=titulo, observacao=observacao))
