<p align="center">
  <img src="assets/omac.png" width="96" alt="Ícone do OMAC">
</p>

<h1 align="center">OMAC</h1>
<p align="center"><strong>Organizador Mensal de Arquivos Contábeis</strong><br>
Aplicativo para Windows que automatiza a rotina contábil mensal de uma clínica odontológica.</p>

<p align="center">
  <img src="docs/capturas/notas-claro.png" alt="Tela de notas fiscais no tema claro" width="49%">
  <img src="docs/capturas/notas-escuro.png" alt="Tela de notas fiscais no tema escuro" width="49%">
</p>

> Todas as imagens usam **notas de exemplo geradas pelo próprio projeto**. Nenhum dado real de paciente está neste repositório.

## O problema

Todo fim de mês as notas fiscais de serviço (NFS-e) emitidas no ISS do DF precisavam ser
passadas à mão para uma planilha que vai para a contabilidade: número, paciente, valor,
data de emissão e data de competência, nota por nota.

## O que o OMAC faz

- **Lê a pasta de PDFs das notas do ano** (ex.: `NFS-e 2026`) e monta a planilha do mês em um clique, em **Excel (.xlsx)** ou **CSV**.
- **Filtra pela data de competência**, não pela de emissão. Uma nota emitida em 03/11 com competência em outubro entra no relatório de outubro.
- **Nome do paciente:** vem do nome do arquivo. Se a descrição do serviço disser *"tratamento odontológico referente ao dependente FULANO"*, o nome do dependente tem prioridade (caso de nota no CPF do responsável).
- **Notas canceladas** ficam fora do relatório e são movidas sozinhas para a subpasta `Canceladas`.
- **Avisos antes de mandar para a contabilidade:** descrição sem "tratamento odontológico", número do arquivo diferente do número da nota, nota repetida, PDF ilegível, nome de arquivo fora do padrão.
- **Rápido em PC antigo:** cada nota é lida uma única vez (≈5 ms) e fica em cache. Nas próximas vezes, só as notas novas são lidas.

### Interface

- **Visual "Bonito"**, com efeito de vidro líquido, cantos arredondados e temas claro/escuro (ou automático, seguindo o Windows).
- **Visual "Otimizado"**, sem transparências nem animações, para computador fraco. Ele já vem ligado sozinho na primeira vez em PCs com pouca memória.
- **Acessibilidade:** texto de 100% a 200% (também com <kbd>Ctrl</kbd> + <kbd>+</kbd> / <kbd>−</kbd> / <kbd>0</kbd>), alto contraste, opção de reduzir animações, navegação por teclado e leitores de tela.
- **Menu lateral preparado para os próximos módulos** (extrato bancário, WhatsApp).

<p align="center">
  <img src="docs/capturas/notas-otimizado.png" alt="Visual otimizado" width="32%">
  <img src="docs/capturas/notas-alto-contraste.png" alt="Alto contraste" width="32%">
  <img src="docs/capturas/config-claro.png" alt="Configurações" width="32%">
</p>

## Como usar

1. Baixe o `OMAC-64bits.exe` na aba **[Releases](../../releases)**. Use o `OMAC-32bits.exe` se o Windows for 32 bits; para conferir, vá em *Configurações → Sistema → Sobre → Tipo de sistema*.
2. Abra o arquivo. Na primeira vez o Windows pode mostrar "O Windows protegeu o computador", porque o app não tem assinatura digital paga. Clique em **Mais informações → Executar assim mesmo**.
3. Escolha a pasta das notas, o mês e clique em **Exportar Excel**.

> Se aparecer um aviso pedindo o **WebView2**, é só aceitar: o próprio OMAC abre a página de download da Microsoft (gratuito). Quase todo Windows 10 atualizado já tem.

### Padrão de nome dos arquivos

```
NFS-e Nº 000000835 - NOME DO PACIENTE - 30-10 -.pdf
NFS-e Nº 000000836 - NOME DO PACIENTE - 03-11 - 31-10.pdf   ← competência diferente (opcional)
```

Número, valor e datas são lidos **de dentro do PDF**. Do nome do arquivo sai só o nome do paciente.

## Privacidade (LGPD)

Dados de saúde são dados sensíveis. O OMAC:

- funciona **100% offline**, sem enviar nada para a internet;
- guarda configurações e cache só no computador (`%APPDATA%\OMAC`);
- tem um `.gitignore` que bloqueia PDF, planilhas e extratos, para nenhum dado real ir parar no GitHub.

## Tecnologias

| Parte | Escolha | Por quê |
|---|---|---|
| Lógica | Python 3.12 | leitura de PDF e Excel maduras, fácil de manter |
| Interface | HTML/CSS/JS puro + [pywebview](https://pywebview.flowrl.com/) | usa o WebView2 que já vem no Windows: visual moderno sem pesar como um Electron |
| PDF | [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | motor do Chrome, ~30× mais rápido que alternativas em Python puro |
| Planilha | openpyxl | gera .xlsx com formatação de moeda, data e total |
| .exe | PyInstaller + GitHub Actions | o executável é gerado e testado num Windows real a cada versão |

## Desenvolvimento

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt   # no Windows: .venv\Scripts\pip

python -m pytest              # testes
python -m omac                # abre o app
python -m tests.fabrica pasta-de-teste   # cria notas de exemplo para testar
```

- `tools/capturas.py` regenera as imagens deste README (precisa do `playwright`).
- `tools/icone.py` regenera o ícone.

### Gerar uma versão

```bash
git tag v1.0.0
git push origin v1.0.0
```

O GitHub Actions roda os testes, gera o `.exe` de 64 e 32 bits, executa um **autoteste do próprio .exe** com notas de exemplo e publica tudo na aba Releases.

### Estrutura

```
omac/
├── app.py            janela + API que a interface chama
├── config.py         configurações do usuário
├── sistema.py        coisas do Windows (WebView2, abrir arquivo, PC fraco?)
├── notas/
│   ├── leitor.py     lê um PDF de NFS-e (DANFSe v2.0)
│   ├── pasta.py      varre a pasta, cache, move canceladas
│   └── exportar.py   gera .xlsx / .csv
└── ui/               index.html, estilo.css, app.js
tests/                testes + gerador de notas de exemplo
```

## Próximos passos

- [ ] **Extrato bancário:** ler o extrato e classificar entradas e saídas por regras editáveis (PIX de paciente, cartão, fornecedores, aluguel…).
- [ ] **Conciliação:** cruzar PIX recebidos com notas emitidas.
- [ ] **WhatsApp Business:** lembretes e confirmação de consultas.
