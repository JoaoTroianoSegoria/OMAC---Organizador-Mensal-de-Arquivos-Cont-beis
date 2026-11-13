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

Todo fim de mês as notas fiscais de serviço (NFS-e) emitidas no ISS do DF e cada linha do
extrato do banco precisavam ser passadas à mão para uma planilha que vai para a contabilidade.

## O que o OMAC faz

### Notas fiscais

- **Lê a pasta de PDFs das notas do ano** (ex.: `NFS-e 2026`) e monta a planilha do mês em um clique, em **Excel (.xlsx)** ou **CSV**.
- **Filtra pela data de competência**, não pela de emissão. Uma nota emitida em 03/11 com competência em outubro entra no relatório de outubro.
- **Nome do paciente:** vem do nome do arquivo. Se a descrição do serviço disser *"tratamento odontológico referente ao dependente FULANO"*, o nome do dependente tem prioridade (caso de nota no CPF do responsável).
- **Notas canceladas** ficam fora do relatório e são movidas sozinhas para a subpasta `Canceladas`.
- **Avisos antes de mandar para a contabilidade:** descrição sem "tratamento odontológico", número do arquivo diferente do número da nota, nota repetida, PDF ilegível, nome de arquivo fora do padrão.
- **Rápido em PC antigo:** cada nota é lida uma única vez (≈5 ms) e fica em cache. Nas próximas vezes, só as notas novas são lidas.

### Extrato bancário

<p align="center">
  <img src="docs/capturas/extrato-claro.png" alt="Tela de extrato bancário" width="49%">
  <img src="docs/capturas/extrato-regras.png" alt="Regras de preenchimento" width="49%">
</p>

- **Lê os extratos em PDF do Banco Inter** de uma pasta e junta tudo. Se os períodos se repetirem, cada dia vem do extrato baixado por último.
- **Regras "quando aparecer X, colocar Y"** preenchem a coluna Operação. As entradas (Pix, crédito e débito) já vêm prontas; as saídas sem regra ficam em amarelo para preencher, e dá para criar a regra a partir da própria linha.
- **Confere pelo saldo:** cada lançamento é checado com o saldo que o banco informa. Se faltar um período e o saldo tiver mudado nele, o OMAC avisa quanto ficou de fora.
- **Fechamento do mês em um arquivo só:** abas de extrato, notas e resumo por operação, com fórmulas que acompanham o que for digitado depois.

### WhatsApp

<p align="center">
  <img src="docs/capturas/whatsapp-envio.png" alt="Janela de envio da nota" width="49%">
  <img src="docs/capturas/whatsapp-lembretes.png" alt="Lembretes do dia" width="49%">
</p>

- **Enviar a nota ao paciente:** a mensagem sai pronta e assinada, o PDF é copiado e a conversa abre no aplicativo ou no WhatsApp Web. A pessoa cola o PDF e aperta enviar.
- **Lista "Notas a enviar":** as notas novas ficam ali, em qualquer mês, até serem enviadas. Dá para seguir direto para a próxima.
- **Lembretes de contas:** na primeira abertura do dia, uma janela mostra o que vence amanhã ou hoje, e um clique deixa a mensagem pronta para quem cuida dos pagamentos.
- **Conta paga:** um botão **Paga** no próprio lembrete faz a conta parar de avisar naquele mês. Na lista de contas aparece o mês atual e o anterior; o que não foi marcado até o fim do mês fica como **não paga**.
- **Sem automação no WhatsApp:** o OMAC usa o link oficial e nunca envia nada sozinho, para não colocar o número em risco.

### Agendamentos

<p align="center">
  <img src="docs/capturas/agendamentos.png" alt="Lista de pacientes de ortodontia com o confere do mês" width="49%">
  <img src="docs/capturas/agendamentos-mensagem.png" alt="Janela de mensagem com as três opções" width="49%">
</p>

- **Lista dos pacientes de ortodontia:** nome, telefone e valor da manutenção. Dá para alterar ou excluir, com a opção de desfazer.
- **Três mensagens prontas:** agendar a manutenção do mês, cobrar com a chave Pix das Configurações e agendar o retorno. O texto pode ser ajustado antes de abrir a conversa.
- **Confere do mês:** marca quem já está agendado e recomeça sozinho todo dia 1, mesmo que o app esteja fechado nesse dia.
- **Responsáveis:** paciente criança pode ter pai e mãe no cadastro, com a escolha de quem sempre recebe as mensagens. O texto já sai falando com o responsável.
- **Alta temporária:** com o dia em que foi dada e o dia em que acaba. Enquanto durar, o paciente fica fora do confere, e o OMAC avisa quando a alta termina.
- **Finalizados:** quem termina o tratamento vai para outra aba e pode voltar para a lista se precisar.

### Ficha de pagamentos

<p align="center">
  <img src="docs/capturas/pagamentos.png" alt="Ficha de pagamentos do mês" width="49%">
  <img src="docs/capturas/pagamentos-atendimento.png" alt="Janela de atendimento" width="49%">
</p>

- **A ficha de papel, dentro do app:** paciente, tratamento, data, valor, forma de pagamento (Pix PJ, Pix PF, dinheiro, débito ou crédito), em quantas vezes no crédito, pago e nota.
- **Pago sem esforço:** fica em branco enquanto espera; se o mês acabar sem marcar, aparece como **não pago**. Pagou depois, é só marcar.
- **Nota marcada sozinha:** o OMAC procura na pasta das notas uma nota do paciente com competência no mês e marca "ok". Se a nota saiu em outro nome, dá para marcar à mão.
- **Menos digitação:** o campo de paciente sugere os nomes já usados na ficha e os pacientes de ortodontia, que já vêm com a manutenção e o valor. Os tratamentos sugeridos (limpeza, manutenção, botox…) são editáveis nas Configurações.
- **Resumo do mês:** recebido, a receber, não pago e quantos estão sem nota, com filtros.
- **Exportar Excel:** a ficha do mês em uma folha deitada, pronta para imprimir.

### Interface

- **Visual "Bonito"**, com efeito de vidro líquido, cantos arredondados e temas claro/escuro (ou automático, seguindo o Windows).
- **Visual "Otimizado"**, sem transparências nem animações, para computador fraco. Ele já vem ligado sozinho na primeira vez em PCs com pouca memória.
- **Acessibilidade:** texto de 100% a 200% (também com <kbd>Ctrl</kbd> + <kbd>+</kbd> / <kbd>−</kbd> / <kbd>0</kbd>), alto contraste, opção de reduzir animações, navegação por teclado e leitores de tela.
- **Avisos que minimizam:** a faixa de avisos fica só com a quantidade, sem sumir, e abre de novo com um clique.
- **Aviso de versão nova:** o OMAC avisa e abre o download no navegador. Trocar a pasta do programa não mexe nos dados.
- **Menu lateral preparado para novos módulos.**

<p align="center">
  <img src="docs/capturas/notas-otimizado.png" alt="Visual otimizado" width="32%">
  <img src="docs/capturas/notas-alto-contraste.png" alt="Alto contraste" width="32%">
  <img src="docs/capturas/config-claro.png" alt="Configurações" width="32%">
</p>

## Como usar

1. Baixe o `OMAC-64bits.zip` na aba **[Releases](../../releases)**, extraia a pasta e abra o `OMAC.exe` que está dentro. Use o `OMAC-32bits.zip` se o Windows for 32 bits; para conferir, vá em *Configurações → Sistema → Sobre → Tipo de sistema*.
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

- não envia nenhum dado seu para a internet: a única saída é a conversa do WhatsApp que a própria pessoa abre e envia;
- guarda configurações e cache só no computador (`%APPDATA%\OMAC`), em uma pasta separada do programa, que as atualizações não alteram;
- para procurar versão nova, só consulta o GitHub, sem enviar nenhum dado seu, e dá para desligar nas Configurações;
- guarda os telefones dos pacientes, os dados de agendamento e a ficha de pagamentos só no computador;
- deixa o nome de quem mandou Pix fora da planilha do fechamento;
- guarda as regras do extrato (com nomes de fornecedores) só no computador, nunca no código;
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
python -m tests.fabrica pasta-de-teste   # cria notas e extratos de exemplo para testar
```

- `tools/capturas.py` regenera as imagens deste README (precisa do `playwright`).
- `tools/icone.py` regenera o ícone.

### Gerar uma versão

```bash
git tag v1.0.0
git push origin v1.0.0
```

O GitHub Actions roda os testes, gera o programa de 64 e 32 bits, executa **autotestes do próprio .exe** (notas de exemplo e a tela no WebView2) e publica os `.zip` na aba Releases.

### Publicar uma versão

Mude `__version__` em `omac/__init__.py` e leve para a `main`. O GitHub Actions testa, gera os `.zip` e publica a Release sozinho; na próxima abertura, o app avisa que há versão nova. Um merge sem mudar o número não publica nada.

### Estrutura

```
omac/
├── app.py            janela; a classe Api junta a API de cada módulo
├── nucleo.py         base da API: configurações, diálogos, tratamento de erro
├── config.py         configurações do usuário
├── armazem.py        leitura e gravação segura dos JSON com os dados do usuário
├── sistema.py        coisas do Windows (WebView2, abrir arquivo, PC fraco?)
├── pdf.py            extração de texto de PDF
├── planilha.py       estilo comum das planilhas
├── fechamento.py     planilha do mês, com as abas de cada módulo
├── notas/            leitor.py · pasta.py · exportar.py · api.py
├── extrato/          leitor.py · pasta.py · regras.py · exportar.py · api.py
├── whatsapp/         mensagens.py · lembretes.py · dados.py · api.py
├── agendamentos/     pacientes.py · mensagens.py · api.py
├── pagamentos/       ficha.py · exportar.py · api.py
├── atualizacao/      github.py · api.py
└── ui/               index.html, estilo.css, nucleo.js + um .js/.css por módulo
tests/                testes + gerador de notas e extratos de exemplo
```

Para criar um módulo: uma pasta em `omac/` com a classe da API (herdando de `ApiBase`), que entra na lista de `Api` em `app.py`, e um `.js` em `ui/` que se registra em `modulos` e `acoes`. Os métodos de cada módulo levam o nome dele (`pagamentos_listar`, `_lista_ficha`…): como todos viram uma classe só, dois métodos com o mesmo nome se apagariam sem erro, e um teste confere isso.

## Próximos passos

- [x] **Extrato bancário:** leitura do PDF do Inter, regras editáveis e fechamento do mês.
- [ ] **Conciliação:** cruzar Pix recebidos com notas emitidas.
- [x] **WhatsApp:** envio de notas e lembretes de contas pelo link oficial.
- [x] **Agendamentos:** pacientes de ortodontia, mensagens e confere do mês.
- [x] **Ficha de pagamentos** e contas pagas nos lembretes.
- [ ] **Tela inicial personalizável** e **resumo do ano**.
- [ ] **Backup** das notas, extratos e dados.
