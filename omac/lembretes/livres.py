"""Lembretes livres: um título, uma observação e, se quiser, quando repetir.

- Sem repetir: fica "em aberto" até ser marcado como feito; o feito vai para uma lista
  à parte (riscado) e pode voltar.
- Todo dia, toda semana (num dia da semana), todo mês (num dia do mês) ou numa data:
  aparece no dia (e ao abrir o app, até ser marcado). Marcado como feito, some até a
  próxima vez. O da data, depois de feito, não volta mais.

Nada é regravado com o tempo: o que aparece sai das datas (`desde`, `feito_em`).
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date, timedelta

from ..dados import esquema
from ..texto import nome_limpo


class LembreteInvalido(ValueError):
    """Faltou o título, ou o lembrete não existe mais."""


def completar(lembrete: dict) -> dict:
    return esquema.completar_item(esquema.LEMBRETES, lembrete, "livres")


NAO, DIA, SEMANA, MES, DATA = "nao", "dia", "semana", "mes", "data"
REPETICOES = (NAO, DIA, SEMANA, MES, DATA)
DIAS_DA_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _inteiro(valor, menor: int, maior: int, erro: str) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise LembreteInvalido(erro) from None
    if not menor <= n <= maior:
        raise LembreteInvalido(erro)
    return n


def _repeticao(dados: dict) -> dict:
    """Só os campos da repetição escolhida; os outros voltam ao padrão."""
    repetir = dados.get("repetir") or NAO
    if repetir not in REPETICOES:
        raise LembreteInvalido("Escolha quando repetir o lembrete.")
    campos = {"repetir": repetir, "dia_semana": 0, "dia_mes": 1, "data": ""}
    if repetir == SEMANA:
        campos["dia_semana"] = _inteiro(dados.get("dia_semana"), 0, 6, "Escolha o dia da semana.")
    elif repetir == MES:
        campos["dia_mes"] = _inteiro(dados.get("dia_mes"), 1, 31, "O dia do mês precisa ser de 1 a 31.")
    elif repetir == DATA:
        try:
            campos["data"] = date.fromisoformat(str(dados.get("data") or "")).isoformat()
        except ValueError:
            raise LembreteInvalido("Escolha a data do lembrete.") from None
    return campos


def _validar(dados: dict) -> dict:
    titulo = nome_limpo(dados.get("titulo"))
    if not titulo:
        raise LembreteInvalido("Diga o que é para lembrar.")
    # A observação pode ter mais de uma linha: só tira o espaço das pontas.
    return {"titulo": titulo, "observacao": str(dados.get("observacao") or "").strip(), **_repeticao(dados)}


def _mesma_repeticao(item: dict, novos: dict) -> bool:
    return all(item.get(k) == novos[k] for k in ("repetir", "dia_semana", "dia_mes", "data"))


# --- Quando aparece ---------------------------------------------------------------------


def _dia_no_mes(ano: int, mes: int, dia: int) -> date:
    """Dia 31 em mês mais curto vira o último dia do mês (como nas contas)."""
    return date(ano, mes, min(dia, monthrange(ano, mes)[1]))


def _mes_anterior(d: date) -> tuple[int, int]:
    return (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)


def _mes_seguinte(d: date) -> tuple[int, int]:
    return (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)


def _desde(item: dict) -> date:
    texto = item.get("desde") or item.get("criado_em")
    try:
        return date.fromisoformat(texto) if texto else date.min
    except ValueError:
        return date.min


def ocorrencia(item: dict, hoje: date) -> date | None:
    """A vez mais recente (até hoje) em que o lembrete devia aparecer. None: ainda não chegou
    (ou não repete). Vezes de antes de o lembrete existir não contam."""
    repetir = item.get("repetir") or NAO
    if repetir == NAO:
        return None
    if repetir == DATA:
        try:
            dia = date.fromisoformat(item["data"])
        except (KeyError, ValueError):
            return None
        return dia if dia <= hoje else None
    if repetir == DIA:
        dia = hoje
    elif repetir == SEMANA:
        dia = hoje - timedelta(days=(hoje.weekday() - int(item.get("dia_semana", 0))) % 7)
    else:
        dia = _dia_no_mes(hoje.year, hoje.month, int(item.get("dia_mes", 1)))
        if dia > hoje:
            dia = _dia_no_mes(*_mes_anterior(hoje), int(item.get("dia_mes", 1)))
    return dia if dia >= _desde(item) else None


def proxima(item: dict, hoje: date) -> date | None:
    """A próxima vez depois de hoje (para mostrar "próximo: 05/12"). None: não tem mais."""
    repetir = item.get("repetir") or NAO
    amanha = hoje + timedelta(days=1)
    if repetir == NAO:
        return None
    if repetir == DATA:
        dia = ocorrencia(item, date.max)
        return dia if dia and dia > hoje else None
    if repetir == DIA:
        dia = amanha
    elif repetir == SEMANA:
        dia = amanha + timedelta(days=(int(item.get("dia_semana", 0)) - amanha.weekday()) % 7)
    else:
        dia = _dia_no_mes(hoje.year, hoje.month, int(item.get("dia_mes", 1)))
        if dia <= hoje:
            dia = _dia_no_mes(*_mes_seguinte(hoje), int(item.get("dia_mes", 1)))
    return max(dia, _desde(item))


def pendente(item: dict, hoje: date) -> bool:
    """Tem o que lembrar agora: sem repetir e não feito, ou a vez de agora ainda não foi feita."""
    if (item.get("repetir") or NAO) == NAO:
        return not item["feito_em"]
    vez = ocorrencia(item, hoje)
    return vez is not None and (not item["feito_em"] or item["feito_em"] < vez.isoformat())


def terminado(item: dict) -> bool:
    """Não volta mais: o sem repetir feito, ou o da data já feito."""
    repetir = item.get("repetir") or NAO
    if repetir == NAO:
        return bool(item["feito_em"])
    return repetir == DATA and bool(item["feito_em"]) and item["feito_em"] >= item.get("data", "")


def quando(item: dict) -> str:
    """A repetição por extenso: "todo dia", "toda segunda", "todo dia 5", "em 25/12/2026"."""
    repetir = item.get("repetir") or NAO
    if repetir == DIA:
        return "todo dia"
    if repetir == SEMANA:
        dia = DIAS_DA_SEMANA[int(item.get("dia_semana", 0))]
        return f"{'todo' if dia in ('sábado', 'domingo') else 'toda'} {dia}"
    if repetir == MES:
        return f"todo dia {int(item.get('dia_mes', 1))} do mês"
    if repetir == DATA and item.get("data"):
        a, m, d = item["data"].split("-")
        return f"em {d}/{m}/{a}"
    return ""


def buscar(livres: list[dict], lembrete_id: str) -> dict:
    for item in livres:
        if item["id"] == lembrete_id:
            return item
    raise LembreteInvalido("Não encontrei esse lembrete. Ele pode ter sido apagado.")


def salvar(livres: list[dict], dados: dict, lembrete_id: str | None, hoje: date,
           destinatario: str | None = None) -> dict:
    """`destinatario`: id do contato que recebe este lembrete ("" = quem recebe os das contas).

    Mudar a repetição recomeça a contar de hoje: o que era da regra antiga não aparece de novo.
    """
    novos = _validar(dados)
    if destinatario is not None:
        novos["destinatario"] = destinatario
    if lembrete_id:
        item = buscar(livres, lembrete_id)
        if not _mesma_repeticao(item, novos):
            novos["desde"] = hoje.isoformat()
            if novos["repetir"] != NAO:
                novos["feito_em"] = ""
        item.update(novos)
        return item
    item = completar({"id": uuid.uuid4().hex, **novos, "criado_em": hoje.isoformat(), "desde": hoje.isoformat()})
    livres.append(item)
    return item


def marcar_feito(item: dict, feito: bool, hoje: date) -> None:
    item["feito_em"] = hoje.isoformat() if feito else ""


def restaurar(livres: list[dict], item: dict, posicao: int | None = None) -> None:
    """Desfaz uma exclusão, de volta ao mesmo lugar da lista."""
    if any(x["id"] == item.get("id") for x in livres):
        return
    livres.insert(len(livres) if posicao is None else max(0, min(int(posicao), len(livres))), completar(item))


def em_aberto(livres: list[dict], hoje: date) -> list[dict]:
    """O que tem para lembrar agora, na ordem em que foram criados."""
    return [x for x in livres if pendente(x, hoje)]


def programados(livres: list[dict], hoje: date) -> list[dict]:
    """Os que repetem (ou têm data) e não têm nada para agora: o mais próximo primeiro."""
    lista = [x for x in livres if not pendente(x, hoje) and not terminado(x) and proxima(x, hoje)]
    return sorted(lista, key=lambda x: proxima(x, hoje))


def feitos(livres: list[dict]) -> list[dict]:
    """Os que não voltam mais. O feito mais recente primeiro."""
    return sorted((x for x in livres if terminado(x)), key=lambda x: x["feito_em"], reverse=True)


def a_lembrar_ao_abrir(livres: list[dict], hoje: date) -> list[dict]:
    """Os que repetem ou têm data e estão para fazer: aparecem toda vez que o app abre."""
    return [x for x in em_aberto(livres, hoje) if (x.get("repetir") or NAO) != NAO]
