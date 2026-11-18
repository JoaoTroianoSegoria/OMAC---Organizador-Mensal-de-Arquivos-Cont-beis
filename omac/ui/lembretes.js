/* OMAC — Lembretes: notas a enviar, contas, lembretes livres e comandos.
 *
 * No WhatsApp o OMAC só deixa a conversa pronta: quem aperta enviar é a pessoa.
 * Quem recebe os lembretes de contas é um contato (Configurações). */
"use strict";

const whats = {
  aba: "enviar",
  notas: [],
  contas: [],
  destinatario: null, // contato que recebe os lembretes
  envioContas: null, // dados da janela "Enviar lembrete" das contas
  livres: { em_aberto: [], feitos: [] },
  livreEditando: null,
  categorias: [],
  categoria: "", // id da categoria aberta em Comandos
  comandoEditando: null,
  categoriaEditando: null,
  atual: null, // nota aberta na janela de envio
  contaEditando: null,
  mesContas: "", // "AAAA-MM" da coluna "este mês" das contas
  lembrete: null,
};

modulos.lembretes = {
  aoMostrar: carregarWhats,
  carregar: carregarWhats,
  antesDeMostrar(aba) { whats.aba = aba; },
  irParaAba: mostrarAbaWhats,
  ligar() {
    $("#form-conta").addEventListener("submit", salvarConta);
    $("#form-livre").addEventListener("submit", salvarLivre);
    $("#form-lb-envio").addEventListener("submit", enviarLembreteDeContas);
    $("#form-lb-comando").addEventListener("submit", salvarComando);
    $("#form-lb-categoria").addEventListener("submit", salvarCategoria);
    $("#form-destinatario").addEventListener("submit", (e) => { e.preventDefault(); definirDestinatario(); });
    $("#cfg-destinatario").addEventListener("change", definirDestinatario);
    $("#form-envio").addEventListener("submit", (e) => e.preventDefault());
    $("#conta-dia").replaceChildren(...diasDoMes().map((d) => new Option(`Dia ${d}`, String(d))));
    $("#cfg-fechamento").replaceChildren(new Option("Desligado", "0"),
      ...diasDoMes(28).map((d) => new Option(`Todo dia ${d}`, String(d))));
    aplicarConfig();
  },
  aoIniciar() {
    verLembretesDoDia();
    carregarDestinatario();
  },
};

function diasDoMes(fim = 31) {
  return Array.from({ length: fim }, (_, i) => i + 1);
}

Object.assign(acoes, {
  "whats-aba": (alvo) => mostrarAbaWhats(alvo.dataset.aba),
  "whats-enviar": (alvo) => abrirEnvio(Number(alvo.dataset.numero)),
  "whats-ja-enviada": (alvo) => marcarSemEnviar(Number(alvo.dataset.numero)),
  "whats-abrir-conversa": abrirConversa,
  "whats-fechar-envio": () => $("#envio").close(),
  "whats-marcar-fechar": () => concluirEnvio(false),
  "whats-proxima": () => concluirEnvio(true),
  "whats-conta-editar": (alvo) => editarConta(whats.contas[Number(alvo.dataset.indice)]),
  "whats-conta-apagar": (alvo) => apagarConta(whats.contas[Number(alvo.dataset.indice)]),
  "whats-conta-paga": marcarContaPaga,
  "whats-lembrete-paga": marcarPagaNoLembrete,
  "whats-conta-cancelar": limparFormularioConta,
  "whats-ver-lembretes": () => verLembretesDoDia(true),
  "lb-lembrar": (alvo) => abrirEnvioDeContas(whats.contas[Number(alvo.dataset.indice)].nome),
  "lb-lembrar-todas": () => abrirEnvioDeContas(null),
  "lb-envio-fechar": () => $("#lb-envio-contas").close(),
  "lb-envio-ir": irParaOndeFaltaContato,
  "lb-livre-feito": (alvo) => marcarLivre(alvo.dataset.id, true),
  "lb-livre-desfazer": (alvo) => marcarLivre(alvo.dataset.id, false),
  "lb-livre-editar": (alvo) => editarLivre(alvo.dataset.id),
  "lb-livre-apagar": (alvo) => apagarLivre(alvo.dataset.id),
  "lb-livre-cancelar": limparFormularioLivre,
  "lb-categoria": (alvo) => { whats.categoria = alvo.dataset.id; desenharComandos(); },
  "lb-categoria-nova": () => abrirCategoria(null),
  "lb-categoria-renomear": () => abrirCategoria(categoriaAtual()),
  "lb-categoria-apagar": apagarCategoria,
  "lb-categoria-mover": (alvo) => moverCategoria(Number(alvo.dataset.passo)),
  "lb-categoria-fechar": () => $("#lb-categoria").close(),
  "lb-comando-novo": () => abrirComando(null),
  "lb-comando-editar": (alvo) => abrirComando(comandoPorId(alvo.dataset.id)),
  "lb-comando-fechar": () => $("#lb-comando").close(),
  "lb-comando-apagar": apagarComando,
  "lb-comando-mover": (alvo) => moverComando(alvo.dataset.id, Number(alvo.dataset.passo)),
  "lb-copiar": (alvo) => copiarComando(alvo.dataset.id),
  "whats-fechar-lembretes": () => $("#lembretes").close(),
  "whats-ir-extrato": () => { $("#lembretes").close(); mostrarView("extrato"); },
  "whats-enviar-lembrete": enviarLembrete,
});

/* ---------- Abas ---------- */

function mostrarAbaWhats(aba) {
  whats.aba = aba;
  $$("#whats-abas .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.aba === aba)));
  $("#whats-enviar").hidden = aba !== "enviar";
  $("#whats-contas").hidden = aba !== "contas";
  $("#whats-livres").hidden = aba !== "livres";
  $("#whats-comandos").hidden = aba !== "comandos";
}

async function carregarWhats() {
  mostrarAbaWhats(whats.aba);
  await Promise.all([carregarAEnviar(), carregarContas(), carregarDestinatario(), carregarLivres(), carregarComandos()]);
}

/* ---------- Notas a enviar ---------- */

async function carregarAEnviar() {
  const r = await api().notas_a_enviar();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  whats.notas = r.notas ?? [];
  desenharAEnviar(r);
}

function desenharAEnviar(r) {
  const vazio = whats.notas.length === 0;
  $("#whats-qtd").textContent = vazio ? "" : `(${whats.notas.length})`;
  $("#whats-tabela").hidden = vazio;
  $("#whats-vazio").hidden = !vazio;
  $("#whats-vazio-pasta").hidden = !r.sem_pasta;
  $("#whats-vazio-titulo").textContent = r.sem_pasta ? "Escolha a pasta das notas" : "Nenhuma nota para enviar";
  $("#whats-vazio-texto").textContent = r.sem_pasta
    ? "Depois disso, cada nota nova aparece aqui até ser enviada."
    : "Quando você salvar uma nota nova na pasta, ela aparece aqui.";
  $("#whats-inicio").textContent = r.inicio
    ? `Aqui entram as notas emitidas desde ${dataBR(r.inicio)}. Para enviar uma mais antiga, use o botão na tela de Notas fiscais.`
    : "";

  $("#whats-corpo").replaceChildren(...whats.notas.map((n) => {
    const tr = document.createElement("tr");
    const tdNum = Object.assign(document.createElement("td"), { className: "c-num", textContent: n.numero });

    const tdNome = document.createElement("td");
    const caixa = Object.assign(document.createElement("div"), { className: "paciente" });
    caixa.append(Object.assign(document.createElement("span"), { textContent: n.responsavel }));
    if (n.dependente) {
      caixa.append(Object.assign(document.createElement("span"), {
        className: "etiqueta", textContent: `dependente: ${n.dependente}`,
      }));
    }
    tdNome.append(caixa);

    const tdValor = Object.assign(document.createElement("td"), {
      className: "c-valor", textContent: real.format(n.valor_centavos / 100),
    });
    const tdData = Object.assign(document.createElement("td"), { className: "c-data", textContent: dataBR(n.competencia) });

    const tdAcoes = document.createElement("td");
    tdAcoes.className = "c-acoes-envio";
    const caixaAcoes = Object.assign(document.createElement("div"), { className: "envio-acoes" });
    const enviar = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq", textContent: "Enviar" });
    enviar.dataset.acao = "whats-enviar";
    enviar.dataset.numero = n.numero;
    enviar.setAttribute("aria-label", `Enviar a nota ${n.numero}`);
    caixaAcoes.append(enviar, botaoIcone("whats-ja-enviada", "i-ok", `Marcar a nota ${n.numero} como já enviada`, { numero: n.numero }));
    tdAcoes.append(caixaAcoes);

    tr.append(tdNum, tdNome, tdValor, tdData, tdAcoes);
    return tr;
  }));
}

/* ---------- Janela de envio ---------- */

async function abrirEnvio(numero) {
  const r = await api().notas_preparar_envio(numero);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  whats.atual = r;
  $("#envio-titulo").textContent = `Nota nº ${r.numero} para ${r.nome}`;
  $("#envio-telefone").value = r.telefone;
  $("#envio-mensagem").value = r.mensagem;
  $("#envio-erro").hidden = true;
  $("#envio-passo").hidden = true;
  $("#envio-acoes-1").hidden = false;
  $("#envio-acoes-2").hidden = true;
  const janela = $("#envio");
  if (!janela.open) janela.showModal();
  (r.telefone ? $("#envio-mensagem") : $("#envio-telefone")).focus();
}

async function abrirConversa() {
  $("#envio-erro").hidden = true;
  const r = await api().notas_enviar(whats.atual.numero, $("#envio-telefone").value, $("#envio-mensagem").value);
  if (r.erro) {
    // Um aviso comum ficaria escondido atrás da janela.
    $("#envio-erro").textContent = r.erro;
    $("#envio-erro").hidden = false;
    return;
  }
  $("#envio-passo-texto").textContent = r.pdf_copiado
    ? "Na conversa, aperte Ctrl + V para anexar o PDF e envie. Depois volte aqui."
    : "Abri a pasta com o PDF: arraste o arquivo para a conversa e envie. Depois volte aqui.";
  $("#envio-passo").hidden = false;
  $("#envio-acoes-1").hidden = true;
  $("#envio-acoes-2").hidden = false;
  const proximas = whats.notas.filter((n) => n.numero !== whats.atual.numero).length;
  $("#envio-proxima").hidden = proximas === 0;
}

function notasMudaram() {
  notasEstado.chave = "";
  if (estado.view === "notas") carregarNotas();
}

async function concluirEnvio(irParaProxima) {
  const numero = whats.atual.numero;
  const r = await api().notas_marcar_enviada(numero, true);
  if (r.erro) {
    $("#envio-erro").textContent = r.erro;
    $("#envio-erro").hidden = false;
    return;
  }
  await carregarAEnviar();
  notasMudaram();
  if (irParaProxima && whats.notas.length) return abrirEnvio(whats.notas[0].numero);
  $("#envio").close();
}

async function marcarSemEnviar(numero) {
  const r = await api().notas_marcar_enviada(numero, true);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  await carregarAEnviar();
  notasMudaram();
  mostrarToast(`Nota nº ${numero} marcada como enviada.`, {
    acoes: [["Desfazer", async () => {
      await api().notas_marcar_enviada(numero, false);
      await carregarAEnviar();
      notasMudaram();
    }]],
  });
}

/* ---------- Contas ---------- */

async function carregarContas() {
  const r = await api().lembretes_contas();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  desenharContas(r);
}

const SITUACAO_DA_CONTA = { paga: "Paga", nao_paga: "Não paga", em_aberto: "Em aberto", "": "—" };

function desenharContas(r) {
  const contas = r.contas;
  whats.contas = contas;
  whats.mesContas = r.mes;
  $("#contas-tabela").hidden = contas.length === 0;
  $("#contas-th-mes").textContent = r.nome_mes;
  $("#contas-th-passado").textContent = r.nome_mes_passado;
  const abertas = contas.filter((c) => c.em_aberto).length;
  $("#lb-qtd-contas").textContent = abertas ? `(${abertas})` : "";
  $("#lb-barra-contas").hidden = abertas === 0;
  $("#lb-barra-texto").textContent = `${plural(abertas, "conta tem", "contas têm")} pagamento em aberto${r.destinatario ? `. O lembrete vai para ${r.destinatario}.` : "."}`;
  desenharDicaDoDestinatario();
  $("#contas-corpo").replaceChildren(...contas.map((c, i) => {
    const tr = document.createElement("tr");
    const tdNome = Object.assign(document.createElement("td"), { textContent: c.nome });
    const tdDia = Object.assign(document.createElement("td"), { className: "c-data", textContent: `Dia ${c.dia}` });

    // Este mês: a caixa marca como paga; sem marcar e já vencida, ganha a etiqueta.
    const tdMes = document.createElement("td");
    tdMes.className = "c-paga";
    const rotulo = Object.assign(document.createElement("label"), { className: "paga-caixa" });
    const caixa = Object.assign(document.createElement("input"), { type: "checkbox", className: "confere", checked: c.este_mes === "paga" });
    caixa.dataset.acao = "whats-conta-paga";
    caixa.dataset.indice = i;
    rotulo.append(caixa, Object.assign(document.createElement("span"), { textContent: "Paga" }));
    tdMes.append(rotulo);
    if (c.este_mes !== "paga" && c.venceu) {
      tdMes.append(Object.assign(document.createElement("span"), {
        className: "etiqueta etiqueta-aviso", textContent: `venceu ${dataBR(c.vencimento).slice(0, 5)}`,
      }));
    }

    const tdPassado = Object.assign(document.createElement("td"), { className: "c-paga" });
    tdPassado.append(Object.assign(document.createElement("span"), {
      className: c.mes_passado === "nao_paga" ? "etiqueta etiqueta-erro" : (c.mes_passado ? "" : "ag-sem-dado"),
      textContent: SITUACAO_DA_CONTA[c.mes_passado],
    }));

    const tdAcoes = document.createElement("td");
    tdAcoes.className = "c-acoes-alta";
    if (c.em_aberto) tdAcoes.append(botaoIcone("lb-lembrar", "i-whats", `Enviar lembrete de ${c.nome}`, { indice: i }));
    tdAcoes.append(botaoIcone("whats-conta-editar", "i-lapis", `Alterar ${c.nome}`, { indice: i }),
      botaoIcone("whats-conta-apagar", "i-lixeira", `Apagar ${c.nome}`, { indice: i }));
    tr.append(tdNome, tdDia, tdMes, tdPassado, tdAcoes);
    return tr;
  }));
}

async function marcarContaPaga(caixa) {
  const conta = whats.contas[Number(caixa.dataset.indice)];
  const r = await api().lembretes_marcar_paga(conta.nome, whats.mesContas, caixa.checked);
  if (r.erro) {
    caixa.checked = !caixa.checked;
    return mostrarToast(r.erro, { erro: true });
  }
  desenharContas(r);
}

function limparFormularioConta() {
  whats.contaEditando = null;
  $("#conta-nome").value = "";
  $("#conta-dia").value = "1";
  $("#form-conta-titulo").textContent = "Nova conta";
  $("#form-conta-salvar").textContent = "Adicionar conta";
  $("#form-conta-cancelar").hidden = true;
}

function editarConta(conta) {
  whats.contaEditando = conta;
  $("#conta-nome").value = conta.nome;
  $("#conta-dia").value = String(conta.dia);
  $("#form-conta-titulo").textContent = "Alterar conta";
  $("#form-conta-salvar").textContent = "Salvar alteração";
  $("#form-conta-cancelar").hidden = false;
  $("#conteudo").scrollTop = 0;
  $("#conta-nome").focus();
}

async function salvarConta(e) {
  e.preventDefault();
  const r = await api().lembretes_salvar_conta(
    { nome: $("#conta-nome").value, dia: Number($("#conta-dia").value) }, whats.contaEditando);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  limparFormularioConta();
  desenharContas(r);
}

async function apagarConta(conta) {
  const r = await api().lembretes_apagar_conta(conta.nome);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  desenharContas(r);
  mostrarToast(`Conta apagada: ${conta.nome}`, {
    acoes: [["Desfazer", async () => {
      const volta = await api().lembretes_salvar_conta(conta, null);
      if (!volta.erro) desenharContas(volta);
    }]],
  });
}

/* ---------- Quem recebe os lembretes (Configurações) ---------- */

async function carregarDestinatario() {
  const r = await api().lembretes_destinatario();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarDestinatario(r);
}

function aplicarDestinatario(r) {
  whats.destinatario = r.contato;
  $("#cfg-destinatario-nomes").replaceChildren(...r.nomes.map((n) => Object.assign(document.createElement("option"), { value: n })));
  if (document.activeElement !== $("#cfg-destinatario")) $("#cfg-destinatario").value = r.contato ? r.contato.nome : "";
  const c = r.contato;
  $("#cfg-destinatario-dica").textContent = !c
    ? "Escolha da lista de contatos. Um nome novo vira contato."
    : c.telefone ? `Os lembretes vão para ${telefoneBR(c.telefone)}. Para trocar o telefone, altere o contato em Contatos.`
      : `${c.nome} está sem telefone: preencha em Contatos.`;
  desenharDicaDoDestinatario();
}

function desenharDicaDoDestinatario() {
  const c = whats.destinatario;
  $("#whats-contato-dica").textContent = c && c.telefone ? ""
    : "Falta dizer quem recebe os lembretes: escolha um contato em Configurações.";
}

async function definirDestinatario() {
  const campo = $("#cfg-destinatario");
  const nome = campo.value.trim();
  if (normalizarNome(nome) === normalizarNome(whats.destinatario ? whats.destinatario.nome : "")) return;
  const r = await api().lembretes_definir_destinatario(nome);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  campo.blur();
  aplicarDestinatario(r);
  mostrarToast(r.contato ? `Os lembretes vão para ${r.contato.nome}.` : "Ninguém recebe os lembretes agora.");
}

/* ---------- Lembretes ---------- */

async function verLembretesDoDia(pedidoNaTela = false) {
  const forcar = pedidoNaTela === true;
  const r = await api().lembretes_do_dia(forcar);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  if (!r.mostrar) {
    if (forcar) mostrarToast("Nenhum lembrete para hoje.");
    return;
  }
  whats.lembrete = r;

  $("#lembretes-contas").replaceChildren(...r.contas.map((c, i) => {
    const li = document.createElement("li");
    li.className = "lembrete-conta";
    const texto = document.createElement("span");
    texto.append(Object.assign(document.createElement("b"), { textContent: `${c.nome}: ` }), c.situacao);
    const paga = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
    paga.dataset.acao = "whats-lembrete-paga";
    paga.dataset.indice = i;
    paga.setAttribute("aria-pressed", "false");
    paga.setAttribute("aria-label", `${c.nome} já foi paga`);
    paga.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg><span>Paga</span>';
    li.append(texto, paga);
    return li;
  }));
  $("#lembretes-fechamento").hidden = !r.fechamento;
  $("#lembretes-fechamento-texto").textContent = r.fechamento;
  $("#lembretes-ir-extrato").hidden = !r.fechamento;
  desenharBotaoDoLembrete();
  $("#lembretes-enviar-texto").textContent = r.destinatario ? `Enviar para ${r.destinatario}` : "Enviar";
  $("#lembretes").showModal();
}

/* Conta marcada como paga sai da mensagem e para de avisar neste mês. */
async function marcarPagaNoLembrete(botao) {
  const conta = whats.lembrete.contas[Number(botao.dataset.indice)];
  const paga = botao.getAttribute("aria-pressed") !== "true";
  const r = await api().lembretes_marcar_paga(conta.nome, conta.mes, paga);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  conta.paga = paga;
  botao.setAttribute("aria-pressed", String(paga));
  botao.closest("li").classList.toggle("paga", paga);
  if (whats.contas.length) desenharContas(r);
  const abertas = whats.lembrete.contas.filter((c) => !c.paga);
  if (abertas.length) {
    const texto = await api().lembretes_texto(abertas);
    if (!texto.erro) whats.lembrete.mensagem = texto.mensagem;
  }
  desenharBotaoDoLembrete();
}

function desenharBotaoDoLembrete() {
  $("#lembretes-enviar").hidden = !whats.lembrete.contas.some((c) => !c.paga);
}

async function enviarLembrete() {
  const r = await api().lembretes_enviar(whats.lembrete.mensagem);
  $("#lembretes").close();
  if (r.sem_contato) {
    mostrarToast(r.nome ? `${r.nome} está sem telefone. Preencha em Contatos.` : "Falta escolher quem recebe os lembretes.", {
      acoes: r.nome ? [["Abrir Contatos", () => mostrarView("contatos")]]
        : [["Abrir Configurações", () => irPara("config", "whats")]],
    });
    return;
  }
  if (r.erro) mostrarToast(r.erro, { erro: true });
}

/* ---------- Widget do Início ---------- */

async function marcarContaPagaNoInicio(botao) {
  const r = await api().lembretes_marcar_paga(botao.dataset.nome, botao.dataset.mes, true);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  mostrarToast(`${botao.dataset.nome} marcada como paga.`, {
    acoes: [["Desfazer", async () => {
      await api().lembretes_marcar_paga(botao.dataset.nome, botao.dataset.mes, false);
      carregarInicio();
    }]],
  });
  carregarInicio();
}

acoes["ini-conta-paga"] = marcarContaPagaNoInicio;
acoes["ini-livre-feito"] = async (botao) => {
  const r = await api().lembretes_marcar_feito(botao.dataset.id, true);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  mostrarToast("Lembrete marcado como feito.", {
    acoes: [["Desfazer", async () => { await api().lembretes_marcar_feito(botao.dataset.id, false); carregarInicio(); }]],
  });
  carregarInicio();
};

function contasDoWidget(c, hoje) {
  const perto = c.abertas.filter((x) => x.perto);
  if (!c.total) return [texto("p", "Nenhuma conta com lembrete.", "dica")];
  if (!perto.length) {
    return [texto("p", c.abertas.length
      ? `Nada vence até amanhã. ${plural(c.abertas.length, "conta ainda em aberto", "contas ainda em aberto")} no mês.`
      : "Todas as contas do mês estão pagas.", "ini-tudo-certo")];
  }
  const ul = Object.assign(document.createElement("ul"), { className: "ini-lista" });
  for (const conta of perto) {
    const li = Object.assign(document.createElement("li"), { className: "ini-conta" });
    const [, mes, dia] = conta.vencimento.split("-");
    const quando = conta.venceu ? `venceu ${dia}/${mes}` : conta.vencimento === hoje ? "vence hoje" : "vence amanhã";
    li.append(Object.assign(document.createElement("span"), { textContent: conta.nome }),
      texto("span", quando, conta.venceu ? "etiqueta etiqueta-erro" : "etiqueta etiqueta-aviso"));
    const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
    b.dataset.acao = "ini-conta-paga";
    b.dataset.nome = conta.nome;
    b.dataset.mes = conta.mes;
    b.setAttribute("aria-label", `${conta.nome} já foi paga`);
    b.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg><span>Paga</span>';
    li.append(b);
    ul.append(li);
  }
  return [ul];
}

registrarWidget("lembretes", {
  icone: "i-whats",
  desenhar(corpo, c) {
    corpo.append(texto("p", "Contas", "ini-subtitulo"), ...contasDoWidget(c, inicio.painel.data));
    const n = c.notas_enviar;
    let notas;
    if (n.sem_pasta) notas = "Escolha a pasta das notas para ver o que falta enviar.";
    else if (n.erro) notas = n.erro;
    else notas = n.qtd ? `${plural(n.qtd, "nota esperando", "notas esperando")} para ser enviada${n.qtd === 1 ? "" : "s"}.` : "Todas as notas foram enviadas.";
    corpo.append(texto("p", "Notas a enviar", "ini-subtitulo"), texto("p", notas, n.qtd ? "ini-alerta" : "ini-tudo-certo"));
    if (c.livres.length) {
      corpo.append(texto("p", "Lembretes", "ini-subtitulo"));
      const ul = Object.assign(document.createElement("ul"), { className: "ini-lista" });
      for (const l of c.livres.slice(0, 5)) {
        const li = Object.assign(document.createElement("li"), { className: "ini-conta" });
        const t = Object.assign(document.createElement("span"), { textContent: l.titulo, title: l.observacao });
        const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
        b.dataset.acao = "ini-livre-feito";
        b.dataset.id = l.id;
        b.setAttribute("aria-label", `${l.titulo}: feito`);
        b.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg><span>Feito</span>';
        li.append(t, b);
        ul.append(li);
      }
      corpo.append(ul);
      if (c.livres.length > 5) corpo.append(texto("p", `e mais ${c.livres.length - 5}`, "dica"));
    }
    corpo.append(rodape(botaoIr("Ver contas", "lembretes", "contas"), botaoIr("Enviar notas", "lembretes", "enviar"),
      botaoIr("Lembretes", "lembretes", "livres")));
  },
});

/* ---------- Contas: enviar lembrete a qualquer momento ---------- */

/* `nome`: uma conta só; null: todas as que estão em aberto. */
async function abrirEnvioDeContas(nome) {
  const r = await api().lembretes_preparar_contas(nome);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  if (!r.contas.length) return mostrarToast("Nenhuma conta em aberto para lembrar.");
  whats.envioContas = r;
  $("#lb-envio-titulo").textContent = r.destinatario ? `Lembrete para ${r.destinatario}` : "Lembrete de pagamento";
  $("#lb-envio-lista").replaceChildren(...r.contas.map((c) => {
    const li = document.createElement("li");
    li.append(Object.assign(document.createElement("b"), { textContent: `${c.nome}: ` }), c.situacao);
    return li;
  }));
  $("#lb-envio-texto").value = r.mensagem;
  const semContato = !r.destinatario || !r.telefone;
  $("#lb-envio-sem-contato").hidden = !semContato;
  $("#lb-envio-sem-contato-texto").textContent = !r.destinatario
    ? "Falta escolher quem recebe os lembretes."
    : `${r.destinatario} está sem telefone.`;
  $("#lb-envio-ir").textContent = !r.destinatario ? "Abrir Configurações" : "Abrir Contatos";
  $("#lb-envio-abrir").disabled = semContato;
  $("#lb-envio-contas").showModal();
  $("#lb-envio-texto").focus();
}

function irParaOndeFaltaContato() {
  $("#lb-envio-contas").close();
  if (whats.envioContas && whats.envioContas.destinatario) mostrarView("contatos");
  else irPara("config", "whats");
}

async function enviarLembreteDeContas(e) {
  e.preventDefault();
  const r = await api().lembretes_enviar($("#lb-envio-texto").value);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  $("#lb-envio-contas").close();
  if (r.sem_contato) return mostrarToast("Falta o telefone de quem recebe os lembretes.", { erro: true });
  mostrarToast("Conversa aberta no WhatsApp. É só conferir e enviar.");
}

/* ---------- Lembretes livres ---------- */

async function carregarLivres() {
  aplicarLivres(await api().lembretes_livres());
}

function aplicarLivres(r) {
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  whats.livres = { em_aberto: r.em_aberto, feitos: r.feitos };
  desenharLivres();
}

function itemDeLivre(l, feito) {
  const li = Object.assign(document.createElement("li"), { className: `lb-livre vidro${feito ? " lb-feito" : ""}` });
  const corpo = Object.assign(document.createElement("div"), { className: "lb-livre-corpo" });
  corpo.append(Object.assign(document.createElement("strong"), { textContent: l.titulo }));
  if (l.observacao) corpo.append(Object.assign(document.createElement("p"), { className: "lb-livre-obs", textContent: l.observacao }));
  if (feito) corpo.append(Object.assign(document.createElement("small"), { className: "dica", textContent: `feito em ${dataBR(l.feito_em)}` }));
  const botoes = Object.assign(document.createElement("div"), { className: "lb-livre-botoes" });
  if (feito) {
    const volta = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
    volta.dataset.acao = "lb-livre-desfazer";
    volta.dataset.id = l.id;
    volta.innerHTML = '<svg class="ic"><use href="#i-atualizar"/></svg><span>Desfazer</span>';
    volta.setAttribute("aria-label", `Voltar “${l.titulo}” para em aberto`);
    botoes.append(volta);
  } else {
    const ok = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
    ok.dataset.acao = "lb-livre-feito";
    ok.dataset.id = l.id;
    ok.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg><span>Feito</span>';
    ok.setAttribute("aria-label", `“${l.titulo}”: feito`);
    botoes.append(ok, botaoIcone("lb-livre-editar", "i-lapis", `Alterar “${l.titulo}”`, { id: l.id }));
  }
  botoes.append(botaoIcone("lb-livre-apagar", "i-lixeira", `Apagar “${l.titulo}”`, { id: l.id }));
  li.append(corpo, botoes);
  return li;
}

function desenharLivres() {
  const { em_aberto: abertos, feitos } = whats.livres;
  $("#lb-qtd-livres").textContent = abertos.length ? `(${abertos.length})` : "";
  $("#lb-livres").replaceChildren(...abertos.map((l) => itemDeLivre(l, false)));
  $("#lb-livres").hidden = abertos.length === 0;
  $("#lb-livres-vazio").hidden = abertos.length > 0;
  $("#lb-feitos").hidden = feitos.length === 0;
  $("#lb-feitos-titulo").textContent = `Feitos (${feitos.length})`;
  $("#lb-feitos-lista").replaceChildren(...feitos.map((l) => itemDeLivre(l, true)));
}

const livrePorId = (id) => [...whats.livres.em_aberto, ...whats.livres.feitos].find((l) => l.id === id);

function limparFormularioLivre() {
  whats.livreEditando = null;
  $("#livre-titulo").value = "";
  $("#livre-obs").value = "";
  $("#form-livre-titulo").textContent = "Novo lembrete";
  $("#form-livre-salvar").textContent = "Adicionar lembrete";
  $("#form-livre-cancelar").hidden = true;
}

function editarLivre(id) {
  const l = livrePorId(id);
  whats.livreEditando = l;
  $("#livre-titulo").value = l.titulo;
  $("#livre-obs").value = l.observacao;
  $("#form-livre-titulo").textContent = "Alterar lembrete";
  $("#form-livre-salvar").textContent = "Salvar alteração";
  $("#form-livre-cancelar").hidden = false;
  $("#conteudo").scrollTop = 0;
  $("#livre-titulo").focus();
}

async function salvarLivre(e) {
  e.preventDefault();
  const r = await api().lembretes_salvar_livre({ titulo: $("#livre-titulo").value, observacao: $("#livre-obs").value },
    whats.livreEditando ? whats.livreEditando.id : null);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  limparFormularioLivre();
  aplicarLivres(r);
  atualizarInicioSeAberto();
}

async function marcarLivre(id, feito) {
  const r = await api().lembretes_marcar_feito(id, feito);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarLivres(r);
  if (feito) {
    mostrarToast("Lembrete feito.", {
      acoes: [["Desfazer", async () => aplicarLivres(await api().lembretes_marcar_feito(id, false))]],
    });
  }
}

async function apagarLivre(id) {
  const r = await api().lembretes_apagar_livre(id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarLivres(r);
  if (whats.livreEditando && whats.livreEditando.id === id) limparFormularioLivre();
  mostrarToast(`Lembrete apagado: ${r.apagado.titulo}`, {
    acoes: [["Desfazer", async () => aplicarLivres(await api().lembretes_restaurar_livre(r.apagado, r.posicao))]],
  });
}

/* ---------- Comandos ---------- */

async function carregarComandos() {
  aplicarComandos(await api().comandos_listar());
}

function aplicarComandos(r) {
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  whats.categorias = r.categorias;
  if (!r.categorias.some((c) => c.id === whats.categoria)) whats.categoria = r.categorias.length ? r.categorias[0].id : "";
  desenharComandos();
}

const categoriaAtual = () => whats.categorias.find((c) => c.id === whats.categoria) || null;
const comandoPorId = (id) => (categoriaAtual() ? categoriaAtual().comandos.find((c) => c.id === id) : null);

function desenharComandos() {
  const cat = categoriaAtual();
  $("#lb-categorias").replaceChildren(...whats.categorias.map((c) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: "escolha" });
    b.dataset.acao = "lb-categoria";
    b.dataset.id = c.id;
    b.setAttribute("aria-pressed", String(c.id === whats.categoria));
    b.append(c.nome);
    if (c.comandos.length) b.append(" ", Object.assign(document.createElement("span"), { className: "ag-qtd", textContent: `(${c.comandos.length})` }));
    return b;
  }));
  $("#lb-categorias").hidden = whats.categorias.length === 0;
  $("#lb-categoria-cab").hidden = !cat;
  const vazio = !cat || cat.comandos.length === 0;
  $("#lb-comandos").hidden = vazio;
  $("#lb-comandos-dica").hidden = vazio;
  $("#lb-comandos-vazio").hidden = !vazio;
  $("#lb-comandos-vazio-titulo").textContent = cat ? "Nenhum comando nesta categoria" : "Nenhuma categoria ainda";
  $("#lb-comandos-vazio-texto").textContent = cat
    ? "Clique em Novo comando e escreva um texto que você manda sempre, como o endereço ou o horário."
    : "Crie uma categoria (por exemplo: Geral, Pós-atendimento, Orçamentos) e depois os comandos dentro dela.";
  if (!cat) {
    $("#lb-comandos").replaceChildren();
    return;
  }
  $("#lb-categoria-nome").textContent = cat.nome;
  const i = whats.categorias.indexOf(cat);
  const subir = botaoIcone("lb-categoria-mover", "i-cima", `Mover “${cat.nome}” para a esquerda`, { passo: -1 });
  subir.disabled = i === 0;
  subir.querySelector("svg").classList.add("lb-seta-esq");
  const descer = botaoIcone("lb-categoria-mover", "i-cima", `Mover “${cat.nome}” para a direita`, { passo: 1 });
  descer.disabled = i === whats.categorias.length - 1;
  descer.querySelector("svg").classList.add("lb-seta-dir");
  $("#lb-categoria-botoes").replaceChildren(subir, descer,
    botaoIcone("lb-categoria-renomear", "i-lapis", `Renomear “${cat.nome}”`, {}),
    botaoIcone("lb-categoria-apagar", "i-lixeira", `Apagar a categoria “${cat.nome}”`, {}));
  $("#lb-comandos").replaceChildren(...cat.comandos.map((c, n) => {
    const li = Object.assign(document.createElement("li"), { className: "lb-comando vidro" });
    const cab = Object.assign(document.createElement("div"), { className: "lb-comando-cab" });
    cab.append(Object.assign(document.createElement("strong"), { textContent: c.nome }));
    const botoes = Object.assign(document.createElement("div"), { className: "lb-livre-botoes" });
    const cima = botaoIcone("lb-comando-mover", "i-cima", `Subir “${c.nome}”`, { id: c.id, passo: -1 });
    cima.disabled = n === 0;
    const baixo = botaoIcone("lb-comando-mover", "i-seta", `Descer “${c.nome}”`, { id: c.id, passo: 1 });
    baixo.disabled = n === cat.comandos.length - 1;
    const copiar = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-primario btn-peq" });
    copiar.dataset.acao = "lb-copiar";
    copiar.dataset.id = c.id;
    copiar.innerHTML = '<svg class="ic"><use href="#i-copiar"/></svg><span>Copiar</span>';
    copiar.setAttribute("aria-label", `Copiar “${c.nome}”`);
    botoes.append(cima, baixo, botaoIcone("lb-comando-editar", "i-lapis", `Alterar “${c.nome}”`, { id: c.id }));
    const rodapeDele = Object.assign(document.createElement("div"), { className: "lb-comando-rodape" });
    rodapeDele.append(botoes, copiar);
    li.append(cab, Object.assign(document.createElement("p"), { className: "lb-comando-texto", textContent: c.texto }), rodapeDele);
    return li;
  }));
}

/* Copia exatamente o texto guardado. O jeito do navegador primeiro; se ele não deixar,
 * o jeito antigo (uma caixa de texto escondida). */
async function copiarTexto(textoDele) {
  try {
    await navigator.clipboard.writeText(textoDele);
    return true;
  } catch {
    const area = Object.assign(document.createElement("textarea"), { value: textoDele });
    area.setAttribute("readonly", "");
    area.style.cssText = "position:fixed;top:-100px;opacity:0";
    document.body.append(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  }
}

async function copiarComando(id) {
  const c = comandoPorId(id);
  if (!c) return;
  if (await copiarTexto(c.texto)) mostrarToast(`Copiado: ${c.nome}`);
  else mostrarToast("Não consegui copiar. Selecione o texto e use Ctrl + C.", { erro: true });
}

function abrirComando(c) {
  if (!categoriaAtual()) return;
  whats.comandoEditando = c;
  $("#lb-comando-titulo").textContent = c ? "Alterar comando" : `Novo comando em ${categoriaAtual().nome}`;
  $("#lb-comando-nome").value = c ? c.nome : "";
  $("#lb-comando-texto").value = c ? c.texto : "";
  $("#lb-comando-apagar").hidden = !c;
  $("#lb-comando-erro").hidden = true;
  $("#lb-comando").showModal();
  $("#lb-comando-nome").focus();
}

async function salvarComando(e) {
  e.preventDefault();
  const r = await api().comandos_salvar(whats.categoria,
    { nome: $("#lb-comando-nome").value, texto: $("#lb-comando-texto").value },
    whats.comandoEditando ? whats.comandoEditando.id : null);
  if (r.erro) {
    $("#lb-comando-erro").textContent = r.erro;
    $("#lb-comando-erro").hidden = false;
    return;
  }
  $("#lb-comando").close();
  aplicarComandos(r);
}

async function apagarComando() {
  const c = whats.comandoEditando;
  const categoria = whats.categoria;
  const r = await api().comandos_apagar(categoria, c.id);
  $("#lb-comando").close();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarComandos(r);
  mostrarToast(`Comando apagado: ${c.nome}`, {
    acoes: [["Desfazer", async () => aplicarComandos(await api().comandos_restaurar(categoria, r.apagado, r.posicao))]],
  });
}

async function moverComando(id, passo) {
  const r = await api().comandos_mover(whats.categoria, id, passo);
  aplicarComandos(r);
  $(`[data-acao="lb-comando-mover"][data-id="${id}"][data-passo="${passo}"]`)?.focus();
}

function abrirCategoria(c) {
  whats.categoriaEditando = c;
  $("#lb-categoria-titulo").textContent = c ? "Renomear categoria" : "Nova categoria";
  $("#lb-categoria-campo").value = c ? c.nome : "";
  $("#lb-categoria-erro").hidden = true;
  $("#lb-categoria").showModal();
  $("#lb-categoria-campo").focus();
}

async function salvarCategoria(e) {
  e.preventDefault();
  const r = await api().comandos_salvar_categoria($("#lb-categoria-campo").value,
    whats.categoriaEditando ? whats.categoriaEditando.id : null);
  if (r.erro) {
    $("#lb-categoria-erro").textContent = r.erro;
    $("#lb-categoria-erro").hidden = false;
    return;
  }
  $("#lb-categoria").close();
  whats.categoria = r.salva.id;
  aplicarComandos(r);
}

async function apagarCategoria() {
  const cat = categoriaAtual();
  const r = await api().comandos_apagar_categoria(cat.id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarComandos(r);
  const qtd = cat.comandos.length ? ` (com ${plural(cat.comandos.length, "comando", "comandos")})` : "";
  mostrarToast(`Categoria apagada: ${cat.nome}${qtd}`, {
    acoes: [["Desfazer", async () => {
      const volta = await api().comandos_restaurar_categoria(r.apagada, r.posicao);
      whats.categoria = r.apagada.id;
      aplicarComandos(volta);
    }]],
  });
}

async function moverCategoria(passo) {
  const id = whats.categoria;
  aplicarComandos(await api().comandos_mover_categoria(id, passo));
  $(`[data-acao="lb-categoria-mover"][data-passo="${passo}"]`)?.focus();
}
