"""Leitura de uma NFS-e (DANFSe v2.0, padrão nacional) a partir do PDF.

O texto do PDF é extraído pelo pdfium, que entrega cada rótulo seguido do seu
valor na linha de baixo, por exemplo:

    NÚMERO DA NFS-E
    836
    COMPETÊNCIA DA NFS-E
    30/10/2026

O nome do paciente vem do nome do arquivo, salvo quando a descrição do
serviço indica um dependente ("... referente ao(a) dependente FULANO"): nesse
caso o nome do dependente tem prioridade. A nota fica no CPF do responsável
(o tomador); o nome do arquivo é o do dependente (1.15.0; antes era o do
responsável, e os arquivos antigos assim continuam sendo lidos).

O jeito de nomear os arquivos e o serviço que a descrição deve ter são da
pessoa (Configurações → Notas fiscais): chegam aqui como `Regras`. Do nome do
arquivo só saem o número e o nome; as datas e o valor vêm sempre do PDF.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..pdf import PdfIlegivel, extrair_paginas
from ..texto import mesma_pessoa

# Mude quando a forma de ler as notas mudar: invalida o cache antigo.
VERSAO_LEITOR = 4  # 2: nome e CPF do tomador; 3: quem recebe a nota guardado na leitura; 4: arquivo com o dependente


class NotaIlegivel(Exception):
    """O PDF não pôde ser aberto ou não tem os campos de uma NFS-e."""


class FormatoInvalido(ValueError):
    """O formato do nome do arquivo não tem o número e o nome, ou tem uma variável que não existe."""


FORMATO_PADRAO = "NFS-e Nº [numero-da-nota] - [nome-do-paciente] - [data-de-emissao]"
SERVICO_PADRAO = "tratamento odontológico"
DEPENDENTE = "nome-do-dependente"
SERVICO_DEPENDENTE_PADRAO = f"tratamento odontológico referente ao(a) dependente [{DEPENDENTE}]"
NUMERO, NOME, EMISSAO, COMPETENCIA = "numero-da-nota", "nome-do-paciente", "data-de-emissao", "data-competencia"
VARIAVEIS_DO_ARQUIVO = (NUMERO, NOME, EMISSAO, COMPETENCIA)


@dataclass(frozen=True)
class Regras:
    """Como ler: o formato do nome dos arquivos e o serviço que a descrição deve ter ("" = não avisa),
    sem e com dependente. O da nota com dependente também diz onde está o nome dele."""

    formato: str = FORMATO_PADRAO
    servico: str = SERVICO_PADRAO
    servico_dependente: str = SERVICO_DEPENDENTE_PADRAO

    def assinatura(self) -> str:
        """Muda quando a leitura muda: o cache guardado com outras regras não vale."""
        partes = (self.formato, self.servico, self.servico_dependente)
        return "|".join(" ".join(p.split()) for p in partes)


PADRAO = Regras()


@dataclass
class Nota:
    numero: int
    paciente: str
    valor: Decimal
    emissao: date
    competencia: date
    arquivo: str
    dependente: bool = False
    cancelada: bool = False
    avisos: list[str] = field(default_factory=list)
    responsavel: str = ""  # quem recebe a nota (ver _quem_recebe)
    tomador: str = ""  # nome de quem recebeu a nota, como está no PDF
    cpf_tomador: str = ""  # só os 11 números; vazio se for CNPJ ou não estiver lá

    def para_dict(self) -> dict:
        return {
            "numero": self.numero,
            "paciente": self.paciente,
            "valor": str(self.valor),
            "emissao": self.emissao.isoformat(),
            "competencia": self.competencia.isoformat(),
            "arquivo": self.arquivo,
            "dependente": self.dependente,
            "cancelada": self.cancelada,
            "avisos": list(self.avisos),
            "responsavel": self.responsavel,
            "tomador": self.tomador,
            "cpf_tomador": self.cpf_tomador,
        }

    @classmethod
    def de_dict(cls, d: dict) -> "Nota":
        return cls(
            numero=d["numero"],
            paciente=d["paciente"],
            valor=Decimal(d["valor"]),
            emissao=date.fromisoformat(d["emissao"]),
            competencia=date.fromisoformat(d["competencia"]),
            arquivo=d["arquivo"],
            dependente=d.get("dependente", False),
            cancelada=d.get("cancelada", False),
            avisos=list(d.get("avisos", [])),
            responsavel=d.get("responsavel", ""),
            tomador=d.get("tomador", ""),
            cpf_tomador=d.get("cpf_tomador", ""),
        )


# --- Nome do arquivo -------------------------------------------------------

# "NFS-e Nº 000000835 - NOME DO PACIENTE - 30-10 -" (competência opcional no fim)
_RE_ARQUIVO = re.compile(
    r"^NFS-?e\s*N\S*\s*0*(?P<numero>\d+)\s*-\s*(?P<nome>.+?)\s*-\s*\d{1,2}-\d{1,2}\b",
    re.IGNORECASE,
)


_RE_VARIAVEL = re.compile(r"\[([^\[\]]*)\]")
_DATA = r"\d{1,2}[-./]\d{1,2}(?:[-./]\d{2,4})?"


def _literal(texto: str) -> str:
    """O texto fixo do formato, sem ser exigente com espaço, traço e o "º" de "Nº"."""
    partes = []
    for c in texto:
        if c.isspace():
            partes.append(r"\s*")
        elif c in "-–—":
            partes.append(r"\s*[-–—]\s*")
        elif c in "º°ª":
            partes.append(r"[º°ªo]?")
        else:
            partes.append(re.escape(c))
    return "".join(partes)


def compilar_formato(formato: str) -> re.Pattern:
    """O formato ("NFS-e Nº [numero-da-nota] - [nome-do-paciente] - ...") vira a regra que lê o nome.

    Precisa ter o número e o nome, uma vez cada. O texto que vier depois da última variável
    pode faltar no arquivo (" -", " COMP - 02-10 -"...), e o que vier depois do formato é ignorado.
    """
    formato = " ".join(str(formato or "").split())
    if formato == FORMATO_PADRAO:
        return _RE_ARQUIVO  # o de sempre, exatamente como nas versões anteriores
    partes = _RE_VARIAVEL.split(formato)  # texto, variável, texto, variável, ..., texto
    variaveis = [v.strip().lower() for v in partes[1::2]]
    desconhecidas = [v for v in variaveis if v not in VARIAVEIS_DO_ARQUIVO]
    if desconhecidas:
        raise FormatoInvalido(f"Não conheço [{desconhecidas[0]}]. Use [numero-da-nota], [nome-do-paciente], "
                              "[data-de-emissao] e [data-competencia].")
    for obrigatoria in (NUMERO, NOME):
        if variaveis.count(obrigatoria) != 1:
            raise FormatoInvalido(f"O formato precisa ter [{obrigatoria}] uma vez.")
    if any(variaveis.count(v) > 1 for v in (EMISSAO, COMPETENCIA)):
        raise FormatoInvalido("Cada data pode aparecer uma vez só no formato.")
    regex = [r"^\s*"]
    for i, parte in enumerate(partes):
        if i % 2 == 0:
            if i == len(partes) - 1:
                if parte.strip():
                    regex.append(f"(?:{_literal(parte)})?")
                continue
            regex.append(_literal(parte))
            continue
        variavel = parte.strip().lower()
        if variavel == NUMERO:
            regex.append(r"0*(?P<numero>\d+)")
        elif variavel == NOME:
            # Nome no fim do formato: vai até o fim do nome do arquivo.
            no_fim = i == len(partes) - 2
            regex.append(r"(?P<nome>.+?)\s*[-–—_.]*\s*$" if no_fim else r"(?P<nome>.+?)")
        else:
            regex.append(_DATA)
    return re.compile("".join(regex), re.IGNORECASE)


def ler_nome_arquivo(nome: str, regras: Regras = PADRAO) -> tuple[int, str] | None:
    """Devolve (número, nome) do nome do arquivo, ou None fora do formato."""
    try:
        padrao = compilar_formato(regras.formato)
    except FormatoInvalido:
        padrao = _RE_ARQUIVO
    m = padrao.match(Path(nome).stem.strip())
    if not m:
        return None
    paciente = _limpar_nome(m.group("nome"))
    if not paciente:
        return None
    return int(m.group("numero")), paciente


def problema_no_nome(nota: Nota, regras: Regras = PADRAO) -> str:
    """Por que o nome do arquivo não serve ("" = está certo): fora do formato, com outro número ou,
    na nota de um dependente, com o nome de outra pessoa (o responsável, como era antes da 1.15.0).

    O site novo baixa o PDF com um nome só de números; aí o OMAC sugere o nome certo.
    """
    lido = ler_nome_arquivo(nota.arquivo, regras)
    if lido is None:
        return "fora_do_formato"
    if lido[0] != nota.numero:
        return "numero_diferente"
    if nota.dependente and not mesma_pessoa(lido[1], nota.paciente):
        return "nome_do_responsavel"
    return ""


# Caracteres que o Windows não aceita em nome de arquivo.
_RE_PROIBIDO = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def nome_certo(nota: Nota, nome: str, regras: Regras = PADRAO) -> str:
    """O nome do arquivo no formato das Configurações, com os dados de dentro do PDF.

    O número sai com 9 dígitos (000000013) e as datas como dd-mm. Se o formato não tem a
    competência, ela vai no fim (" - COMP 21-11"), que a leitura ignora: é o jeito da clínica.
    """
    formato = " ".join(str(regras.formato or "").split()) or FORMATO_PADRAO
    try:
        compilar_formato(formato)
    except FormatoInvalido:
        formato = FORMATO_PADRAO
    valores = {
        NUMERO: f"{nota.numero:09d}",
        NOME: " ".join(_RE_PROIBIDO.sub(" ", nome).split()),
        EMISSAO: f"{nota.emissao:%d-%m}",
        COMPETENCIA: f"{nota.competencia:%d-%m}",
    }
    texto = _RE_VARIAVEL.sub(lambda m: valores.get(m.group(1).strip().lower(), m.group(0)), formato)
    if "[" + COMPETENCIA + "]" not in formato.lower().replace(" ", ""):
        texto += f" - COMP {valores[COMPETENCIA]}"
    return " ".join(_RE_PROIBIDO.sub("-", texto).split()) + ".pdf"


def responsavel(nota: Nota) -> str:
    """Quem recebe a nota (o responsável, se ela é de um dependente)."""
    if nota.responsavel:
        return nota.responsavel
    lido = ler_nome_arquivo(nota.arquivo)
    return lido[1] if lido else nota.paciente


# --- Conteúdo do PDF -------------------------------------------------------

_RE_NUMERO = re.compile(r"N[ÚU]MERO DA NFS-E\s*\n\s*(\d+)", re.IGNORECASE)
_RE_COMPETENCIA = re.compile(r"COMPET[ÊE]NCIA DA NFS-E\s*\n\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_RE_EMISSAO = re.compile(
    r"DATA E HORA DA EMISS[ÃA]O DA NFS-E\s*\n\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE
)
_RE_SITUACAO = re.compile(r"SITUA[ÇC][ÃA]O DA NFS-E\s*\n\s*([^\n]+)", re.IGNORECASE)
# O valor pode não vir na linha logo abaixo (a coluna "VALOR TOTAL" ao lado
# costuma estar vazia e o pdfium junta os rótulos), então pega o primeiro R$.
_RE_VALOR_SERVICO = re.compile(
    r"VALOR DA OPERA[ÇC][ÃA]O\s*/\s*SERVI[ÇC]O.*?R\$\s*([\d.]+,\d{2})", re.IGNORECASE | re.DOTALL
)
_RE_VALOR_LIQUIDO = re.compile(
    r"VALOR L[ÍI]QUIDO DA NFS-E\s*\n\s*R\$\s*([\d.]+,\d{2})", re.IGNORECASE
)
_RE_DESCRICAO = re.compile(
    r"Descri[çc][ãa]o do Servi[çc]o\s*\n(.*?)\n\s*TRIBUTA[ÇC][ÃA]O MUNICIPAL",
    re.IGNORECASE | re.DOTALL,
)
_RE_TOMADOR = re.compile(
    r"TOMADOR\s*/\s*ADQUIRENTE.*?Nome\s*/\s*Nome Empresarial\s*\n\s*([^\n]+)",
    re.IGNORECASE | re.DOTALL,
)
# O bloco do tomador vai até o intermediário ou o serviço; o CPF vem logo depois do rótulo.
_RE_BLOCO_TOMADOR = re.compile(
    r"TOMADOR\s*/\s*ADQUIRENTE(.*?)(?:INTERMEDI|SERVI[ÇC]O PRESTADO|$)", re.IGNORECASE | re.DOTALL
)
_RE_CPF = re.compile(r"(?<![\d./-])(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?![\d./-])")
_RE_CANCELADA = re.compile(r"\bcancelad[ao]\b", re.IGNORECASE)
# A marca de cancelamento fica sozinha na linha: "CANCELADA", "NFS-e cancelada".
_RE_MARCA_CANCELADA = re.compile(
    r"^\s*(?:(?:nfs-?e|nota(?:\s+fiscal)?)\s+)?cancelad[ao]\s*$", re.IGNORECASE | re.MULTILINE
)


def extrair_texto(caminho: Path) -> str:
    """Texto da primeira página do PDF (o DANFSe tem uma página só)."""
    try:
        return extrair_paginas(caminho, limite=1)[0]
    except PdfIlegivel as e:
        raise NotaIlegivel(str(e)) from e


def interpretar_texto(texto: str, nome_arquivo: str, regras: Regras = PADRAO) -> Nota:
    """Monta a Nota a partir do texto do PDF e do nome do arquivo."""
    avisos: list[str] = []

    numero = _buscar(_RE_NUMERO, texto)
    competencia = _buscar(_RE_COMPETENCIA, texto)
    emissao = _buscar(_RE_EMISSAO, texto)
    valor = _buscar(_RE_VALOR_SERVICO, texto) or _buscar(_RE_VALOR_LIQUIDO, texto)

    faltando = [
        rotulo
        for rotulo, v in (
            ("número", numero),
            ("competência", competencia),
            ("data de emissão", emissao),
            ("valor", valor),
        )
        if v is None
    ]
    if faltando:
        if not texto.strip():
            raise NotaIlegivel("o PDF não tem texto (é uma imagem escaneada?)")
        raise NotaIlegivel("não encontrei " + ", ".join(faltando) + " no PDF")

    situacao = _buscar(_RE_SITUACAO, texto) or ""
    cancelada = bool(_RE_CANCELADA.search(situacao) or _RE_MARCA_CANCELADA.search(texto))
    if not cancelada and _RE_CANCELADA.search(texto):
        # Pode ser só a descrição do serviço: a nota continua valendo, mas alguém precisa olhar.
        avisos.append("A palavra “cancelada” aparece no texto da nota. Ela continua no relatório: confira se vale mesmo.")

    descricao = " ".join((_buscar(_RE_DESCRICAO, texto) or "").split())
    dependente = _nome_dependente(descricao, regras.servico_dependente)
    aviso = _aviso_da_descricao(descricao, regras, dependente)
    if aviso:
        avisos.append(aviso)

    do_arquivo = ler_nome_arquivo(nome_arquivo, regras)
    tomador = _limpar_nome(_buscar(_RE_TOMADOR, texto) or "")

    if dependente:
        paciente = dependente
    elif do_arquivo:
        paciente = do_arquivo[1]
    else:
        paciente = tomador
        avisos.append(
            "O nome do arquivo está fora do formato; usei o nome do tomador que está na nota."
        )
        if not paciente:
            paciente = "(sem nome)"

    numero_int = int(numero)
    if do_arquivo and do_arquivo[0] != numero_int:
        avisos.append(
            f"O número no nome do arquivo ({do_arquivo[0]}) é diferente do número da nota ({numero_int})."
        )

    return Nota(
        numero=numero_int,
        paciente=paciente,
        valor=_valor(valor),
        emissao=_data(emissao),
        competencia=_data(competencia),
        arquivo=nome_arquivo,
        dependente=bool(dependente),
        cancelada=cancelada,
        avisos=avisos,
        responsavel=_quem_recebe(dependente, do_arquivo, tomador, paciente),
        tomador=tomador,
        cpf_tomador=_cpf_do_tomador(texto),
    )


def ler_nota(caminho: Path, regras: Regras = PADRAO) -> Nota:
    caminho = Path(caminho)
    return interpretar_texto(extrair_texto(caminho), caminho.name, regras)


# --- Auxiliares ------------------------------------------------------------


def _buscar(regex: re.Pattern, texto: str) -> str | None:
    m = regex.search(texto)
    return m.group(1).strip() if m else None


def _cpf_do_tomador(texto: str) -> str:
    """Só os números do CPF do tomador. CNPJ (14 números) não casa com o padrão."""
    bloco = _buscar(_RE_BLOCO_TOMADOR, texto) or ""
    m = _RE_CPF.search(bloco)
    return re.sub(r"\D", "", m.group(1)) if m else ""


def _quem_recebe(dependente: str | None, do_arquivo: tuple[int, str] | None, tomador: str, paciente: str) -> str:
    """O responsável pela nota. Sem dependente, é quem está no nome do arquivo (ou o tomador).
    Com dependente, o nome do arquivo pode ser o do responsável (arquivos de antes da 1.15.0)
    ou o do próprio dependente (o certo agora): aí quem recebe é o tomador, que está no PDF."""
    if not dependente:
        return do_arquivo[1] if do_arquivo else paciente
    if do_arquivo and not mesma_pessoa(do_arquivo[1], dependente):
        return do_arquivo[1]
    return tomador


# Letras com e sem acento: o modelo das Configurações pode estar escrito de um jeito e a nota de outro.
_ACENTOS = {"a": "aáàâãä", "e": "eéèêë", "i": "iíìîï", "o": "oóòôõö", "u": "uúùûü", "c": "cç", "n": "nñ"}


def _sem_ligar_para_acento(palavra: str) -> str:
    return "".join(f"[{_ACENTOS[c]}]" if c in _ACENTOS else re.escape(c) for c in _sem_acentos(palavra).lower())


def _partes_do_modelo(modelo: str) -> tuple[str, str] | None:
    """(texto antes, texto depois) de [nome-do-dependente] no modelo; None se ele não tem a variável."""
    m = re.search(r"\[\s*" + DEPENDENTE + r"\s*\]", modelo or "", re.IGNORECASE)
    return (modelo[:m.start()], modelo[m.end():]) if m else None


def _nome_dependente(descricao: str, modelo: str = SERVICO_DEPENDENTE_PADRAO) -> str | None:
    """O nome que vem depois da última palavra antes de [nome-do-dependente] no modelo
    ("dependente", no padrão). Sem a variável no modelo, procura a palavra "dependente"."""
    partes = _partes_do_modelo(modelo)
    palavras = re.findall(r"[^\W\d_]+", partes[0]) if partes else []
    ancora = _sem_ligar_para_acento(palavras[-1]) if palavras else "dependente"
    m = re.search(rf"\b{ancora}\b\s*[:\-]?\s*(.+)", descricao, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    nome = m.group(1)
    # O que o modelo tem depois do nome (", menor de idade"...) não faz parte dele.
    depois = re.findall(r"[^\W\d_]+", partes[1]) if partes else []
    if depois:
        nome = re.split(rf"\b{_sem_ligar_para_acento(depois[0])}\b", nome, maxsplit=1, flags=re.IGNORECASE)[0]
    # Corta o que vier depois do nome: CPF, números, parênteses, pontuação.
    nome = re.split(r"[,;:()\[\]\d]|\s[-–]\s|\bCPF\b", nome, maxsplit=1, flags=re.IGNORECASE)[0]
    return _limpar_nome(nome) or None


def _comparavel(texto: str) -> str:
    """Para comparar a descrição com a esperada sem ligar para acento, pontuação e artigos:
    "referente ao(a) dependente", "a(ao) dependente" e "à dependente" contam como iguais."""
    palavras = re.findall(r"[a-z0-9]+", _sem_acentos(texto).lower())
    return " ".join(p for p in palavras if len(p) > 2 or p.isdigit())


def _aviso_da_descricao(descricao: str, regras: Regras, dependente: str | None) -> str:
    """Aviso se a descrição não tem o texto esperado (o de dependente, quando a nota é de um)."""
    modelo = " ".join(regras.servico_dependente.split()) if dependente else ""
    if modelo:
        partes = _partes_do_modelo(modelo)
        esperado = f"{partes[0]}{dependente}{partes[1]}" if partes else modelo
        if _comparavel(esperado) not in _comparavel(descricao):
            return f"A descrição do serviço não está como a de dependente: “{' '.join(esperado.split())}”."
        return ""
    servico = " ".join(regras.servico.split())
    if servico and _comparavel(servico) not in _comparavel(descricao):
        return f"A descrição do serviço não contém “{servico}”."
    return ""


def _limpar_nome(nome: str) -> str:
    return " ".join(nome.split()).strip(" .-–").upper()


def _sem_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _valor(s: str) -> Decimal:
    return Decimal(s.replace(".", "").replace(",", "."))


def _data(s: str) -> date:
    return datetime.strptime(s, "%d/%m/%Y").date()
