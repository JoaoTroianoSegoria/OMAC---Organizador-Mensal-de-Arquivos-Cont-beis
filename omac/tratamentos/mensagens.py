"""As três mensagens que podem ser mandadas para o paciente ou para o responsável.

Os textos ficam no catálogo (Configurações → Mensagens): cada um tem a versão para o próprio
paciente e a versão para o responsável (que cita o paciente pelo primeiro nome).
"""

from __future__ import annotations

from datetime import date

from ..whatsapp import catalogo as cat
from ..whatsapp import variaveis as vr

# As opções da janela de mensagem de Tratamentos
AGENDAR = "agendar"
COBRAR = "cobrar"
RETORNO = "retorno"


def todas(cfg: dict, nome: str, hoje: date, valor_centavos: int | None, responsavel: str = "",
          consulta: str = "") -> dict[str, str]:
    """Com o dia da consulta já marcado, "agendar" confirma o dia em vez de pedir um.
    Sem chave Pix (e com o texto pedindo a chave), "cobrar" vem vazio para a tela pedir a chave."""
    versao = cat.RESPONSAVEL if responsavel else cat.PACIENTE
    v = vr.valores_tratamento(cfg.get("assistente_nome", ""), responsavel or nome, nome, hoje, consulta,
                              valor_centavos, cfg.get("chave_pix", ""))
    sem_pix = not v["chave-pix"] and cat.usa(cfg, cat.PIX_MANUTENCAO, versao, "chave-pix")
    return {
        AGENDAR: cat.montar(cfg, cat.CONFIRMAR if consulta else cat.AGENDAR, versao, v),
        COBRAR: "" if sem_pix else cat.montar(cfg, cat.PIX_MANUTENCAO, versao, v),
        RETORNO: cat.montar(cfg, cat.RETORNO, versao, v),
    }
