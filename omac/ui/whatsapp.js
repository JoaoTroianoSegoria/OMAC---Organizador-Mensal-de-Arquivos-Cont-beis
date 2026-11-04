/* OMAC — módulo de WhatsApp: envio de notas, contas com lembrete e contatos. */
"use strict";

const whats = {
  aba: "enviar",
  notas: [],
  contas: [],
  contatos: [],
  atual: null, // nota aberta na janela de envio
  contaEditando: null,
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
  "whats-conta-cancelar": limparFormularioConta,
  "whats-contato-apagar": (alvo) => apagarContato(whats.contatos[Number(alvo.dataset.indice)]),
  "whats-ver-lembretes": () => verLembretesDoDia(true),
  "whats-fechar-lembretes": () => $("#lembretes").close(),
  "whats-ir-extrato": () => { $("#lembretes").close(); mostrarView("extrato"); },
  "whats-enviar-lembrete": enviarLembrete,
});

function botaoIcone(acao, icone, rotulo, dados) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "btn-linha";
  b.dataset.acao = acao;
  Object.assign(b.dataset, dados);
  b.title = rotulo;
  b.setAttribute("aria-label", rotulo);
  b.innerHTML = `<svg class="ic"><use href="#${icone}"/></svg>`;
  return b;
}

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
  desenharContas(r.contas);
}

function desenharContas(contas) {
  whats.contas = contas;
  $("#contas-tabela").hidden = contas.length === 0;
  $("#whats-contato-dica").textContent = estado.cfg.lembrete_telefone
    ? ""
    : "Falta dizer quem recebe os lembretes: preencha o nome e o telefone em Configurações.";
  $("#contas-corpo").replaceChildren(...contas.map((c, i) => {
    const tr = document.createElement("tr");
    const tdNome = Object.assign(document.createElement("td"), { textContent: c.nome });
    const tdDia = Object.assign(document.createElement("td"), { className: "c-data", textContent: `Dia ${c.dia}` });
    const tdAcoes = document.createElement("td");
    tdAcoes.className = "c-acoes-regra";
    tdAcoes.append(botaoIcone("whats-conta-editar", "i-lapis", `Alterar ${c.nome}`, { indice: i }),
      botaoIcone("whats-conta-apagar", "i-lixeira", `Apagar ${c.nome}`, { indice: i }));
    tr.append(tdNome, tdDia, tdAcoes);
    return tr;
  }));
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
  desenharContas(r.contas);
}

async function apagarConta(conta) {
  const r = await api().whatsapp_apagar_conta(conta.nome);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  desenharContas(r.contas);
  mostrarToast(`Conta apagada: ${conta.nome}`, {
    acoes: [["Desfazer", async () => {
      const volta = await api().whatsapp_salvar_conta(conta, null);
      if (!volta.erro) desenharContas(volta.contas);
    }]],
  });
}

/* ---------- Contatos ---------- */

async function carregarContatos() {
  const r = await api().whatsapp_contatos();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  desenharContatos(r.contatos);
}

function telefoneBR(digitos) {
  const m = /^55(\d{2})(\d{4,5})(\d{4})$/.exec(digitos);
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : digitos;
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

  $("#lembretes-contas").replaceChildren(...r.contas.map((c) => {
    const li = document.createElement("li");
    li.append(Object.assign(document.createElement("b"), { textContent: `${c.nome}: ` }), c.situacao);
    return li;
  }));
  $("#lembretes-fechamento").hidden = !r.fechamento;
  $("#lembretes-fechamento-texto").textContent = r.fechamento;
  $("#lembretes-ir-extrato").hidden = !r.fechamento;
  $("#lembretes-enviar").hidden = r.contas.length === 0;
  $("#lembretes-enviar-texto").textContent = r.destinatario ? `Enviar para ${r.destinatario}` : "Enviar";
  $("#lembretes").showModal();
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
