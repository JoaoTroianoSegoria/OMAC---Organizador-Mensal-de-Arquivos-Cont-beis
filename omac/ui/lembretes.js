/* OMAC — Lembretes: notas a enviar, contas e lembretes livres (os Comandos viraram Textos prontos).
 *
 * No WhatsApp o OMAC só deixa a conversa pronta: quem aperta enviar é a pessoa.
 * Quem recebe os lembretes de contas é um contato (Configurações). */
"use strict";

const whats = {
  aba: "enviar",
  notas: [],
  contas: [],
  destinatario: null, // contato que recebe os lembretes
  livres: { em_aberto: [], programados: [], feitos: [], padrao: "", nomes: [] },
  livreEditando: null,
  repetir: "nao", // repetição escolhida no formulário de lembrete
  diaVisto: new Date().toDateString(), // para mostrar os lembretes de novo quando o dia vira com o app aberto
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
    $("#form-destinatario").addEventListener("submit", (e) => { e.preventDefault(); definirDestinatario(); });
    $("#cfg-destinatario").addEventListener("change", definirDestinatario);
    $("#conta-dia").replaceChildren(...diasDoMes().map((d) => new Option(`Dia ${d}`, String(d))));
    $("#cfg-fechamento").replaceChildren(new Option("Desligado", "0"),
      ...diasDoMes(28).map((d) => new Option(`Todo dia ${d}`, String(d))));
    $("#livre-dia-mes").replaceChildren(...diasDoMes().map((d) => new Option(`Dia ${d}`, String(d))));
    limparFormularioLivre();
    aplicarConfig();
    // O OMAC costuma ficar aberto o dia todo: na virada do dia, os lembretes aparecem sozinhos.
    setInterval(() => {
      const hoje = new Date().toDateString();
      if (hoje === whats.diaVisto) return;
      whats.diaVisto = hoje;
      verLembretesDoDia();
      if (estado.view === "lembretes") carregarLivres();
    }, 5 * 60000);
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
  "whats-enviar": (alvo) => abrirEnvioDeNotas([Number(alvo.dataset.numero)], { umaPorVez: true }),
  "whats-ja-enviada": (alvo) => marcarSemEnviar(Number(alvo.dataset.numero)),
  "whats-conta-editar": (alvo) => editarConta(whats.contas[Number(alvo.dataset.indice)]),
  "whats-conta-apagar": (alvo) => apagarConta(whats.contas[Number(alvo.dataset.indice)]),
  "whats-conta-paga": marcarContaPaga,
  "whats-lembrete-paga": marcarPagaNoLembrete,
  "whats-conta-cancelar": limparFormularioConta,
  "whats-ver-lembretes": () => verLembretesDoDia(true),
  "lb-lembrar": (alvo) => abrirEnvioDeContas(whats.contas[Number(alvo.dataset.indice)].nome),
  "lb-lembrar-todas": () => abrirEnvioDeContas(null),
  "lb-livre-feito": (alvo) => marcarLivre(alvo.dataset.id, true),
  "lb-livre-desfazer": (alvo) => marcarLivre(alvo.dataset.id, false),
  "lb-livre-editar": (alvo) => editarLivre(alvo.dataset.id),
  "lb-livre-apagar": (alvo) => apagarLivre(alvo.dataset.id),
  "lb-livre-cancelar": limparFormularioLivre,
  "lb-repetir": (alvo) => escolherRepeticao(alvo.dataset.repetir),
  "lb-livre-enviar": (alvo) => abrirEnvioDeLivre(alvo.dataset.id),
  "lb-pop-feito": marcarLivreNoLembrete,
  "whats-fechar-lembretes": () => $("#lembretes").close(),
  "whats-ir-extrato": () => { $("#lembretes").close(); irPara("relatorio", "extrato"); },
  "whats-enviar-lembrete": enviarLembrete,
});

/* ---------- Abas ---------- */

function mostrarAbaWhats(aba) {
  whats.aba = aba;
  $$("#whats-abas .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.aba === aba)));
  $("#whats-enviar").hidden = aba !== "enviar";
  $("#whats-contas").hidden = aba !== "contas";
  $("#whats-livres").hidden = aba !== "livres";
}

async function carregarWhats() {
  mostrarAbaWhats(whats.aba);
  await Promise.all([carregarAEnviar(), carregarContas(), carregarDestinatario(), carregarLivres()]);
}

/* ---------- Notas a enviar ---------- */

async function carregarAEnviar() {
  const r = await api().notas_a_enviar();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  whats.notas = r.notas ?? [];
  desenharSeMudou("lb-enviar", r, () => desenharAEnviar(r));
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

    const tdValor = celula(dinheiro(n.valor_centavos), "c-valor");
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

/* ---------- Enviar uma nota ----------
 * A mesma janela de várias notas (relatorio.js), com uma nota só. Daqui ela ainda oferece
 * "Já enviei, próxima nota" enquanto houver notas na lista. */

function notasMudaram() {
  notasEstado.chave = "";
  if (estado.view === "relatorio" && relatorio.aba === "notas") carregarNotas();
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
  if ($("#lembretes").open) $("#lembretes").close();

  const livres = r.livres || [];
  $("#lembretes-livres").hidden = livres.length === 0;
  $("#lembretes-livres").replaceChildren(...livres.map(itemDoLembreteAoAbrir));
  $("#lembretes-contas").hidden = r.contas.length === 0;
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

function botaoEnviarLivre(l) {
  const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
  b.dataset.acao = "lb-livre-enviar";
  b.dataset.id = l.id;
  b.title = "Mandar este lembrete pelo WhatsApp";
  b.setAttribute("aria-label", `Enviar “${l.titulo}” pelo WhatsApp`);
  b.innerHTML = '<svg class="ic"><use href="#i-whats"/></svg><span>Enviar</span>';
  return b;
}

function itemDoLembreteAoAbrir(l) {
  const li = Object.assign(document.createElement("li"), { className: "lb-livre vidro" });
  const corpo = Object.assign(document.createElement("div"), { className: "lb-livre-corpo" });
  corpo.append(texto("strong", l.titulo));
  if (l.observacao) corpo.append(texto("p", l.observacao, "lb-livre-obs"));
  if (l.quando) corpo.append(texto("small", l.quando, "dica"));
  const botoes = Object.assign(document.createElement("div"), { className: "lb-livre-botoes" });
  const feito = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
  feito.dataset.acao = "lb-pop-feito";
  feito.dataset.id = l.id;
  feito.setAttribute("aria-pressed", "false");
  feito.setAttribute("aria-label", `“${l.titulo}”: feito`);
  feito.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg><span>Feito</span>';
  botoes.append(feito, botaoEnviarLivre(l));
  li.append(corpo, botoes);
  return li;
}

/* Feito na janela: some até a próxima vez. Clicar de novo desfaz. */
async function marcarLivreNoLembrete(botao) {
  const feito = botao.getAttribute("aria-pressed") !== "true";
  const r = await api().lembretes_marcar_feito(botao.dataset.id, feito);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  botao.setAttribute("aria-pressed", String(feito));
  botao.closest("li").classList.toggle("lb-feito", feito);
  aplicarLivres(r);
  atualizarInicioSeAberto();
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
        if (l.quando) t.append(" ", texto("small", `(${l.quando})`, "dica"));
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
  abrirEnvioDeLembrete(r, r.destinatario ? `Lembrete para ${r.destinatario}` : "Lembrete de pagamento",
    r.contas.map((c) => {
      const li = document.createElement("li");
      li.append(Object.assign(document.createElement("b"), { textContent: `${c.nome}: ` }), c.situacao);
      return li;
    }), "");
}

/* Um lembrete livre pelo WhatsApp: a mesma janela das contas, com a mensagem do lembrete. */
async function abrirEnvioDeLivre(id) {
  const r = await api().lembretes_preparar_livre(id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  abrirEnvioDeLembrete(r, r.destinatario ? `Lembrete para ${r.destinatario}` : "Enviar lembrete",
    [texto("li", r.titulo)], r.contato_id);
}

/* Contas e lembretes vão para quem recebe os lembretes (ou quem o lembrete escolheu): o
 * telefone é o do contato, então a janela mostra só a mensagem. `para` "" = quem recebe os lembretes. */
function abrirEnvioDeLembrete(r, titulo, itens, para) {
  const semContato = !r.destinatario || !r.telefone;
  abrirJanelaMensagem({
    titulo,
    itens,
    destinos: [{ contato_id: para || "", nome: r.destinatario || "", papel: "", telefone: r.telefone || "" }],
    semTelefone: true,
    texto: () => r.mensagem,
    falta: () => (semContato
      ? {
        texto: !r.destinatario ? "Falta escolher quem recebe os lembretes." : `${r.destinatario} está sem telefone.`,
        botao: !r.destinatario ? "Abrir Configurações" : "Abrir Contatos",
        acao: () => {
          if ($("#lembretes").open) $("#lembretes").close();
          if (r.destinatario) mostrarView("contatos");
          else irPara("config", "whats");
        },
      }
      : null),
    enviar: async ({ texto: mensagem }) => {
      const resposta = await api().lembretes_enviar(mensagem, para || "");
      return resposta.sem_contato ? { erro: "Falta o telefone de quem recebe os lembretes." } : resposta;
    },
  });
}

/* ---------- Lembretes livres ---------- */

async function carregarLivres() {
  aplicarLivres(await api().lembretes_livres());
}

function aplicarLivres(r) {
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  whats.livres = { em_aberto: r.em_aberto, programados: r.programados || [], feitos: r.feitos,
    padrao: r.padrao || "", nomes: r.nomes || [] };
  $("#livre-para-nomes").replaceChildren(...whats.livres.nomes.map((n) => new Option(n, n)));
  $("#livre-para").placeholder = whats.livres.padrao ? `${whats.livres.padrao} (quem recebe os lembretes)` : "Escolha um contato";
  desenharSeMudou("lb-livres", r, desenharLivres);
}

/* "toda segunda · próximo: 24/11 · para Fulana" */
function quandoDoLivre(l, programado) {
  const partes = [];
  if (l.quando) partes.push(l.quando);
  if (programado && l.proxima && l.repetir !== "data") partes.push(`próximo: ${dataBR(l.proxima).slice(0, 5)}`);
  if (l.destinatario_nome) partes.push(`para ${l.destinatario_nome}`);
  return partes.join(" · ");
}

function itemDeLivre(l, feito, programado = false) {
  const li = Object.assign(document.createElement("li"), { className: `lb-livre vidro${feito ? " lb-feito" : ""}` });
  const corpo = Object.assign(document.createElement("div"), { className: "lb-livre-corpo" });
  corpo.append(Object.assign(document.createElement("strong"), { textContent: l.titulo }));
  if (l.observacao) corpo.append(Object.assign(document.createElement("p"), { className: "lb-livre-obs", textContent: l.observacao }));
  const quando = quandoDoLivre(l, programado);
  if (quando && !feito) corpo.append(texto("small", quando, "dica lb-livre-quando"));
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
    if (!programado) {
      const ok = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
      ok.dataset.acao = "lb-livre-feito";
      ok.dataset.id = l.id;
      ok.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg><span>Feito</span>';
      ok.setAttribute("aria-label", `“${l.titulo}”: feito`);
      botoes.append(ok);
    }
    botoes.append(botaoEnviarLivre(l),
      botaoIcone("lb-livre-editar", "i-lapis", `Alterar “${l.titulo}”`, { id: l.id }));
  }
  botoes.append(botaoIcone("lb-livre-apagar", "i-lixeira", `Apagar “${l.titulo}”`, { id: l.id }));
  li.append(corpo, botoes);
  return li;
}

function desenharLivres() {
  const { em_aberto: abertos, programados, feitos } = whats.livres;
  $("#lb-qtd-livres").textContent = abertos.length ? `(${abertos.length})` : "";
  $("#lb-livres").replaceChildren(...abertos.map((l) => itemDeLivre(l, false)));
  $("#lb-livres").hidden = abertos.length === 0;
  $("#lb-livres-vazio").hidden = abertos.length > 0;
  $("#lb-programados").hidden = programados.length === 0;
  $("#lb-programados-lista").replaceChildren(...programados.map((l) => itemDeLivre(l, false, true)));
  $("#lb-feitos").hidden = feitos.length === 0;
  $("#lb-feitos-titulo").textContent = `Feitos (${feitos.length})`;
  $("#lb-feitos-lista").replaceChildren(...feitos.map((l) => itemDeLivre(l, true)));
}

const livrePorId = (id) => [...whats.livres.em_aberto, ...whats.livres.programados, ...whats.livres.feitos]
  .find((l) => l.id === id);

function escolherRepeticao(repetir) {
  whats.repetir = repetir;
  $$("#lb-repetir .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.repetir === repetir)));
  $("#livre-dia-semana-campo").hidden = repetir !== "semana";
  $("#livre-dia-mes-campo").hidden = repetir !== "mes";
  $("#livre-data-campo").hidden = repetir !== "data";
  $("#livre-repetir-dica").hidden = repetir === "nao";
  if (repetir === "data" && !$("#livre-data").value) $("#livre-data").value = hojeISO();
}

function hojeISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function limparFormularioLivre() {
  whats.livreEditando = null;
  $("#livre-titulo").value = "";
  $("#livre-obs").value = "";
  $("#livre-dia-semana").value = String((new Date().getDay() + 6) % 7);
  $("#livre-dia-mes").value = String(new Date().getDate());
  $("#livre-data").value = "";
  $("#livre-para").value = "";
  escolherRepeticao("nao");
  $("#form-livre-titulo").textContent = "Novo lembrete";
  $("#form-livre-salvar").textContent = "Adicionar lembrete";
  $("#form-livre-cancelar").hidden = true;
}

function editarLivre(id) {
  const l = livrePorId(id);
  whats.livreEditando = l;
  $("#livre-titulo").value = l.titulo;
  $("#livre-obs").value = l.observacao;
  $("#livre-dia-semana").value = String(l.dia_semana ?? 0);
  $("#livre-dia-mes").value = String(l.dia_mes ?? 1);
  $("#livre-data").value = l.data || "";
  $("#livre-para").value = l.destinatario_nome || "";
  escolherRepeticao(l.repetir || "nao");
  $("#form-livre-titulo").textContent = "Alterar lembrete";
  $("#form-livre-salvar").textContent = "Salvar alteração";
  $("#form-livre-cancelar").hidden = false;
  $("#conteudo").scrollTop = 0;
  $("#livre-titulo").focus();
}

async function salvarLivre(e) {
  e.preventDefault();
  const r = await api().lembretes_salvar_livre({
    titulo: $("#livre-titulo").value,
    observacao: $("#livre-obs").value,
    repetir: whats.repetir,
    dia_semana: Number($("#livre-dia-semana").value),
    dia_mes: Number($("#livre-dia-mes").value),
    data: $("#livre-data").value,
    destinatario: $("#livre-para").value,
  }, whats.livreEditando ? whats.livreEditando.id : null);
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

