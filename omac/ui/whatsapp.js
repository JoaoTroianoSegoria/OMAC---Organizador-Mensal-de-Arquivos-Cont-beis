/* OMAC — módulo de WhatsApp: envio de notas, contas com lembrete e contatos. */
"use strict";

const whats = {
  aba: "enviar",
  notas: [],
  contas: [],
  contatos: [],
  atual: null, // nota aberta na janela de envio
  contaEditando: null,
  mesContas: "", // "AAAA-MM" da coluna "este mês" das contas
  lembrete: null,
};

modulos.whatsapp = {
  aoMostrar: carregarWhats,
  carregar: carregarWhats,
  ligar() {
    $("#form-conta").addEventListener("submit", salvarConta);
    $("#form-envio").addEventListener("submit", (e) => e.preventDefault());
    $("#conta-dia").replaceChildren(...diasDoMes().map((d) => new Option(`Dia ${d}`, String(d))));
    $("#cfg-fechamento").replaceChildren(new Option("Desligado", "0"),
      ...diasDoMes(28).map((d) => new Option(`Todo dia ${d}`, String(d))));
    aplicarConfig();
  },
  aoIniciar: verLembretesDoDia,
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
  "whats-contato-apagar": (alvo) => apagarContato(whats.contatos[Number(alvo.dataset.indice)]),
  "whats-ver-lembretes": () => verLembretesDoDia(true),
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
  $("#whats-contatos").hidden = aba !== "contatos";
}

async function carregarWhats() {
  mostrarAbaWhats(whats.aba);
  await Promise.all([carregarAEnviar(), carregarContas(), carregarContatos()]);
}

/* ---------- Notas a enviar ---------- */

async function carregarAEnviar() {
  const r = await api().whatsapp_a_enviar();
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
  const r = await api().whatsapp_preparar_nota(numero);
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
  const r = await api().whatsapp_enviar_nota(whats.atual.numero, $("#envio-telefone").value, $("#envio-mensagem").value);
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
  carregarContatos();
  const proximas = whats.notas.filter((n) => n.numero !== whats.atual.numero).length;
  $("#envio-proxima").hidden = proximas === 0;
}

function notasMudaram() {
  notasEstado.chave = "";
  if (estado.view === "notas") carregarNotas();
}

async function concluirEnvio(irParaProxima) {
  const numero = whats.atual.numero;
  const r = await api().whatsapp_marcar_enviada(numero, true);
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
  const r = await api().whatsapp_marcar_enviada(numero, true);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  await carregarAEnviar();
  notasMudaram();
  mostrarToast(`Nota nº ${numero} marcada como enviada.`, {
    acoes: [["Desfazer", async () => {
      await api().whatsapp_marcar_enviada(numero, false);
      await carregarAEnviar();
      notasMudaram();
    }]],
  });
}

/* ---------- Contas ---------- */

async function carregarContas() {
  const r = await api().whatsapp_contas();
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
  $("#whats-contato-dica").textContent = estado.cfg.lembrete_telefone
    ? ""
    : "Falta dizer quem recebe os lembretes: preencha o nome e o telefone em Configurações.";
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
    tdAcoes.className = "c-acoes-regra";
    tdAcoes.append(botaoIcone("whats-conta-editar", "i-lapis", `Alterar ${c.nome}`, { indice: i }),
      botaoIcone("whats-conta-apagar", "i-lixeira", `Apagar ${c.nome}`, { indice: i }));
    tr.append(tdNome, tdDia, tdMes, tdPassado, tdAcoes);
    return tr;
  }));
}

async function marcarContaPaga(caixa) {
  const conta = whats.contas[Number(caixa.dataset.indice)];
  const r = await api().whatsapp_marcar_paga(conta.nome, whats.mesContas, caixa.checked);
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
  const r = await api().whatsapp_salvar_conta(
    { nome: $("#conta-nome").value, dia: Number($("#conta-dia").value) }, whats.contaEditando);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  limparFormularioConta();
  desenharContas(r);
}

async function apagarConta(conta) {
  const r = await api().whatsapp_apagar_conta(conta.nome);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  desenharContas(r);
  mostrarToast(`Conta apagada: ${conta.nome}`, {
    acoes: [["Desfazer", async () => {
      const volta = await api().whatsapp_salvar_conta(conta, null);
      if (!volta.erro) desenharContas(volta);
    }]],
  });
}

/* ---------- Contatos ---------- */

async function carregarContatos() {
  const r = await api().whatsapp_contatos();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  desenharContatos(r.contatos);
}

function desenharContatos(contatos) {
  whats.contatos = contatos;
  $("#contatos-tabela").hidden = contatos.length === 0;
  $("#contatos-vazio").hidden = contatos.length > 0;
  $("#contatos-corpo").replaceChildren(...contatos.map((c, i) => {
    const tr = document.createElement("tr");
    const tdNome = Object.assign(document.createElement("td"), { textContent: c.nome });
    const tdTel = Object.assign(document.createElement("td"), { className: "c-telefone", textContent: telefoneBR(c.telefone) });
    const tdAcao = document.createElement("td");
    tdAcao.className = "c-acao";
    tdAcao.append(botaoIcone("whats-contato-apagar", "i-lixeira", `Apagar ${c.nome}`, { indice: i }));
    tr.append(tdNome, tdTel, tdAcao);
    return tr;
  }));
}

async function apagarContato(contato) {
  const r = await api().whatsapp_apagar_contato(contato.nome);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  desenharContatos(r.contatos);
  mostrarToast(`Contato apagado: ${contato.nome}`, {
    acoes: [["Desfazer", async () => {
      const volta = await api().whatsapp_salvar_contato(contato.nome, contato.telefone);
      if (!volta.erro) desenharContatos(volta.contatos);
    }]],
  });
}

/* ---------- Lembretes ---------- */

async function verLembretesDoDia(pedidoNaTela = false) {
  const forcar = pedidoNaTela === true;
  const r = await api().whatsapp_lembretes(forcar);
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
  const r = await api().whatsapp_marcar_paga(conta.nome, conta.mes, paga);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  conta.paga = paga;
  botao.setAttribute("aria-pressed", String(paga));
  botao.closest("li").classList.toggle("paga", paga);
  if (whats.contas.length) desenharContas(r);
  const abertas = whats.lembrete.contas.filter((c) => !c.paga);
  if (abertas.length) {
    const texto = await api().whatsapp_texto_lembrete(abertas);
    if (!texto.erro) whats.lembrete.mensagem = texto.mensagem;
  }
  desenharBotaoDoLembrete();
}

function desenharBotaoDoLembrete() {
  $("#lembretes-enviar").hidden = !whats.lembrete.contas.some((c) => !c.paga);
}

async function enviarLembrete() {
  const r = await api().whatsapp_enviar_lembrete(whats.lembrete.mensagem);
  $("#lembretes").close();
  if (r.sem_contato) {
    mostrarToast("Falta o telefone de quem recebe os lembretes.", {
      acoes: [["Abrir Configurações", () => mostrarView("config")]],
    });
    return;
  }
  if (r.erro) mostrarToast(r.erro, { erro: true });
}
