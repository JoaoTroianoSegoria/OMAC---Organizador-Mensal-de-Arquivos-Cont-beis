/* OMAC — Relatório mensal: uma tela com as abas Notas fiscais, Extrato bancário e Regras do
 * extrato, um seletor de mês só, e a ilha das notas escolhidas para enviar juntas.
 * As abas em si ficam em notas.js e extrato.js. */
"use strict";

const relatorio = {
  aba: "notas",   // "notas" | "extrato" | "regras"
  lote: null,     // o que o Python preparou para o envio (notas, contatos, destinos…)
  destino: "",    // contato_id de quem recebe ("" = contato novo)
  nomeContato: "", // o nome que gerou os destinos: digitar o mesmo de novo não refaz nada
  enviando: [],   // números do envio aberto, para marcar como enviadas depois
};

modulos.relatorio = {
  aoMostrar() {
    modulos[moduloDaAba()].aoMostrar();
    desenharIlha();
  },
  carregar() { return modulos[moduloDaAba()].carregar(); },
  ligar() {
    $("#form-rel-lote").addEventListener("submit", enviarLote);
    $("#rel-lote-contato").addEventListener("change", trocarContatoDoLote);
    $("#rel-lote").addEventListener("close", () => { relatorio.lote = null; });
  },
  // Sem a pasta dos extratos não há regras para mostrar.
  aoAplicarConfig(cfg) { $('#rel-abas [data-aba="regras"]').hidden = !cfg.pasta_extratos; },
  antesDeMostrar: mostrarAbaDoRelatorio,
  irParaAba: () => {},
};

const moduloDaAba = () => (relatorio.aba === "notas" ? "notas" : "extrato");

Object.assign(acoes, {
  "rel-aba": (alvo) => { mostrarAbaDoRelatorio(alvo.dataset.aba); modulos.relatorio.aoMostrar(); },
  "rel-atualizar": () => modulos.relatorio.carregar(),
  "rel-tirar": (alvo) => escolherParaEnviar(Number(alvo.dataset.numero), false),
  "rel-limpar-selecao": limparSelecao,
  "rel-enviar-lote": abrirLote,
  "rel-lote-destino": (alvo) => escolherDestinoDoLote(alvo.dataset.id),
  "rel-lote-fechar": () => $("#rel-lote").close(),
  "rel-lote-marcar": marcarLoteEnviado,
});

function mostrarAbaDoRelatorio(aba) {
  relatorio.aba = aba;
  $$("#rel-abas .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.aba === aba)));
  $("#rel-notas").hidden = aba !== "notas";
  $("#rel-extrato").hidden = aba !== "extrato";
  $("#ext-regras").hidden = aba !== "regras";
  // Botões, pasta e mês de cada aba. As regras valem para todos os meses.
  $$("[data-rel-acao]").forEach((b) => { b.hidden = b.dataset.relAcao !== moduloDaAba() || aba === "regras"; });
  $$("[data-rel-pasta]").forEach((c) => { c.hidden = c.dataset.relPasta !== moduloDaAba(); });
  $("#rel-barra").hidden = aba === "regras";
  $("#rel-atualizar").hidden = aba === "regras";
  $("#rel-lidas").hidden = aba !== "notas" || !$("#rel-lidas span").textContent;
  const fora = aba === "notas" && notasEstado.escopo !== "mes";
  $("#sel-mes").disabled = fora;
  $("#sel-ano").disabled = fora;
  desenharIlha();
}

/* ---------- Ilha das notas escolhidas ---------- */

function desenharIlha() {
  const escolhidas = [...notasEstado.selecao.values()].sort((a, b) => a.numero - b.numero);
  const ilha = $("#rel-ilha");
  ilha.hidden = escolhidas.length === 0 || relatorio.aba !== "notas";
  if (!escolhidas.length) return;
  const total = escolhidas.reduce((soma, n) => soma + n.valor_centavos, 0);
  $("#rel-ilha-titulo").textContent = escolhidas.length === 1 ? "1 nota escolhida" : `${escolhidas.length} notas escolhidas`;
  $("#rel-ilha-total").replaceChildren(dinheiro(total));
  $("#rel-ilha-lista").replaceChildren(...escolhidas.map((n) => {
    const li = Object.assign(document.createElement("li"), { className: "rel-chip" });
    li.append(texto("span", `Nº ${n.numero} · ${n.paciente} · `));
    li.lastChild.append(dinheiro(n.valor_centavos));
    const x = Object.assign(document.createElement("button"), { type: "button", className: "rel-chip-tirar" });
    x.dataset.acao = "rel-tirar";
    x.dataset.numero = n.numero;
    x.title = "Tirar da escolha";
    x.setAttribute("aria-label", `Tirar a nota ${n.numero} da escolha`);
    x.innerHTML = '<svg class="ic"><use href="#i-fechar"/></svg>';
    li.append(x);
    return li;
  }));
}

function limparSelecao() {
  notasEstado.selecao.clear();
  $$("#tabela-corpo .rel-escolher").forEach((c) => {
    c.checked = false;
    c.closest("tr").classList.remove("rel-escolhida");
  });
  marcarCabecalho();
  desenharIlha();
}

/* ---------- Envio de várias notas ---------- */

async function abrirLote() {
  const numeros = [...notasEstado.selecao.keys()];
  if (!numeros.length) return;
  const r = await api().notas_preparar_lote(numeros);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  relatorio.enviando = numeros;
  $("#rel-lote-titulo").textContent = numeros.length === 1 ? "Enviar 1 nota" : `Enviar ${numeros.length} notas juntas`;
  const linhas = r.notas.map((n) => {
    const li = document.createElement("li");
    li.append(`Nº ${n.numero} · ${n.paciente} · ${dataBR(n.competencia)} · `, dinheiro(n.valor_centavos));
    return li;
  });
  const total = texto("li", "Total: ", "rel-lote-total");
  total.append(dinheiro(r.total_centavos));
  linhas.push(total);
  $("#rel-lote-notas").replaceChildren(...linhas);
  $("#rel-lote-contatos").replaceChildren(...r.contatos.map((c) => new Option(c.nome)));
  $("#rel-lote-contato").value = r.nome;
  $("#rel-lote-contato-dica").textContent = r.mesma_pessoa
    ? "Já escolhi pelo nome que está nas notas. Para mandar para outra pessoa, digite outro contato."
    : "As notas são de pessoas diferentes: escolha o contato que vai receber (ou escreva um nome novo).";
  $("#rel-lote-colar-campo").hidden = !r.colar_disponivel;
  $("#rel-lote-colar").checked = r.colar_sozinho;
  $("#rel-lote-erro").hidden = true;
  $("#rel-lote-passo").hidden = true;
  $("#rel-lote-acoes-1").hidden = false;
  $("#rel-lote-acoes-2").hidden = true;
  aplicarLote(r);
  $("#rel-lote").showModal();
  if (!r.destinos.length) $("#rel-lote-contato").focus();
  else ($("#rel-lote-telefone").value ? $("#rel-lote-mensagem") : $("#rel-lote-telefone")).focus();
}

function aplicarLote(r) {
  relatorio.lote = r;
  relatorio.nomeContato = r.nome;
  $("#rel-lote-destinos").replaceChildren(...r.destinos.map((d) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: "escolha" });
    b.dataset.acao = "rel-lote-destino";
    b.dataset.id = d.contato_id;
    b.textContent = d.papel ? `${d.nome} (${d.papel})` : d.nome;
    return b;
  }));
  $("#rel-lote-destinos-campo").hidden = r.destinos.length < 2;
  $("#rel-lote-envio").hidden = r.destinos.length === 0;
  $("#rel-lote-abrir").disabled = r.destinos.length === 0;
  if (r.destinos.length) escolherDestinoDoLote(r.escolhido);
}

function destinoDoLote() {
  const { destinos } = relatorio.lote;
  return destinos.find((d) => d.contato_id === relatorio.destino) || destinos[0];
}

function escolherDestinoDoLote(id) {
  relatorio.destino = id;
  const d = destinoDoLote();
  $$("#rel-lote-destinos .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.id === d.contato_id)));
  $("#rel-lote-telefone").value = d.telefone ? telefoneBR(d.telefone) : "";
  $("#rel-lote-mensagem").value = d.mensagem;
}

/* Outro contato digitado ou escolhido na lista: refaz para quem mandar e a mensagem. */
async function trocarContatoDoLote() {
  if (!relatorio.lote) return;
  const nome = $("#rel-lote-contato").value.trim();
  // O "change" também vem ao sair do campo: com o mesmo nome, não apaga o telefone digitado.
  if (normalizarNome(nome) === normalizarNome(relatorio.nomeContato)) return;
  relatorio.nomeContato = nome;
  const contato = relatorio.lote.contatos.find((c) => normalizarNome(c.nome) === normalizarNome(nome));
  const r = await api().notas_preparar_lote(relatorio.enviando, contato ? contato.id : "", contato ? "" : nome);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  if (relatorio.lote) aplicarLote(r);
}

async function enviarLote(e) {
  e.preventDefault();
  if (!relatorio.lote || !relatorio.lote.destinos.length) return;
  const d = destinoDoLote();
  const colar = !$("#rel-lote-colar-campo").hidden && $("#rel-lote-colar").checked;
  $("#rel-lote-erro").hidden = true;
  const r = await api().notas_enviar_lote(relatorio.enviando, relatorio.lote.contato_id, d.contato_id, d.nome,
    $("#rel-lote-telefone").value, $("#rel-lote-mensagem").value, colar);
  if (r.erro) {
    $("#rel-lote-erro").textContent = r.erro;
    $("#rel-lote-erro").hidden = false;
    return;
  }
  if (!$("#rel-lote-colar-campo").hidden) estado.cfg.colar_sozinho = colar;
  const pdfs = r.qtd === 1 ? "o PDF" : `os ${r.qtd} PDFs`;
  $("#rel-lote-passo-texto").textContent = r.colando
    ? `Abri a conversa. Quando ela aparecer, o OMAC cola ${pdfs} sozinho: confira e aperte Enter. Depois volte aqui.`
    : r.pdf_copiado
      ? `Na conversa, aperte Ctrl + V para colar ${pdfs} de uma vez e envie. Depois volte aqui.`
      : `Abri a pasta das notas: arraste ${pdfs} para a conversa e envie. Depois volte aqui.`;
  $("#rel-lote-passo").hidden = false;
  $("#rel-lote-acoes-1").hidden = true;
  $("#rel-lote-acoes-2").hidden = false;
  $("#rel-lote-marcar-texto").textContent = r.qtd === 1 ? "Já enviei, marcar como enviada" : `Já enviei, marcar as ${r.qtd} como enviadas`;
  $("#rel-lote-marcar").focus();
}

/* Resposta da tentativa de colar sozinho (vem do Python). */
window.omacColagem = (colou) => {
  mostrarToast(colou
    ? "Colei os PDFs na conversa. Confira e aperte Enter no WhatsApp."
    : "Não consegui colar sozinho. Na conversa, aperte Ctrl + V.");
};

async function marcarLoteEnviado() {
  const numeros = relatorio.enviando;
  const r = await api().notas_marcar_enviadas(numeros, true);
  if (r.erro) {
    $("#rel-lote-erro").textContent = r.erro;
    $("#rel-lote-erro").hidden = false;
    return;
  }
  $("#rel-lote").close();
  numeros.forEach((n) => notasEstado.enviadas.add(n));
  limparSelecao();
  desenharNotas();
  mostrarToast(numeros.length === 1 ? "Nota marcada como enviada." : `${numeros.length} notas marcadas como enviadas.`, {
    acoes: [["Desfazer", async () => {
      await api().notas_marcar_enviadas(numeros, false);
      numeros.forEach((n) => notasEstado.enviadas.delete(n));
      desenharNotas();
    }]],
  });
}
