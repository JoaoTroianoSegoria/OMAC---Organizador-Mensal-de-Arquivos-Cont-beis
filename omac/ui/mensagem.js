/* OMAC — a janela de mensagem pelo WhatsApp, a mesma para todas as telas (1.12.0).
 *
 * Antes eram quatro (nota, várias notas, Tratamentos e lembretes), cada uma sabendo uma parte.
 * Agora quem chama diz o que tem, e a janela monta só o que precisa:
 *
 *   abrirJanelaMensagem({
 *     titulo,                 // texto, ou (destino) => texto
 *     itens,                  // [elementos] da lista em cima (notas, contas...), opcional
 *     busca,                  // {contatos, valor, dica, trocar(nome, contato) => Promise<parte nova>}, opcional
 *     destinos, escolhido,    // [{contato_id, nome, papel, telefone, ...}]: quem pode receber
 *     rotuloDestino,          // (destino) => texto do botão, opcional
 *     tipos, tipo,            // [{id, rotulo}]: mensagens diferentes (agendar, cobrar...), opcional
 *     texto,                  // (destino, tipo) => mensagem pronta
 *     falta,                  // (destino, tipo) => {texto, botao, acao} | null: o que falta para mandar
 *     semTelefone,            // true: o telefone vem de outro lugar (lembretes para a Dra.)
 *     colar,                  // {marcado}: a opção "colar os PDFs sozinho", opcional
 *     botao,                  // texto do botão principal
 *     enviar,                 // async ({destino, telefone, texto, tipo, colar}) => resposta do Python
 *     depois,                 // (resposta) => {passo, acoes: [{rotulo, acao, primario}]} | null
 *     aoEnviar,               // (resposta) => ..., quando fecha logo depois de abrir a conversa
 *   })
 */
"use strict";

const janelaMsg = { op: null, destino: "", tipo: "", nomeBuscado: "", acoesDepois: [] };

modulos.mensagem = {
  ligar() {
    $("#form-msg").addEventListener("submit", (e) => { e.preventDefault(); enviarDaJanelaMensagem(); });
    $("#msg-contato").addEventListener("change", trocarContatoDaMensagem);
    $("#msg").addEventListener("close", () => { janelaMsg.op = null; });
  },
};

Object.assign(acoes, {
  "msg-destino": (alvo) => escolherDestinoDaMensagem(alvo.dataset.id),
  "msg-tipo": (alvo) => escolherTipoDaMensagem(alvo.dataset.tipo),
  "msg-fechar": () => $("#msg").close(),
  "msg-falta": () => {
    const falta = faltaDaMensagem();
    if (!falta) return;
    $("#msg").close();
    falta.acao();
  },
  "msg-depois": (alvo) => janelaMsg.acoesDepois[Number(alvo.dataset.indice)]?.acao(),
});

function abrirJanelaMensagem(op) {
  janelaMsg.op = op;
  janelaMsg.tipo = op.tipo || (op.tipos && op.tipos[0] ? op.tipos[0].id : "");
  janelaMsg.nomeBuscado = op.busca ? op.busca.valor : "";
  $("#msg-itens").replaceChildren(...(op.itens || []));
  $("#msg-itens").hidden = !(op.itens && op.itens.length);
  $("#msg-busca-campo").hidden = !op.busca;
  if (op.busca) {
    $("#msg-contatos").replaceChildren(...op.busca.contatos.map((c) => new Option(c.nome)));
    $("#msg-contato").value = op.busca.valor;
    $("#msg-busca-dica").textContent = op.busca.dica || "";
  }
  $("#msg-tipos").hidden = !(op.tipos && op.tipos.length > 1);
  $("#msg-tipos").replaceChildren(...(op.tipos || []).map((t) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: "escolha", textContent: t.rotulo });
    b.dataset.acao = "msg-tipo";
    b.dataset.tipo = t.id;
    return b;
  }));
  $("#msg-telefone-campo").hidden = !!op.semTelefone;
  $("#msg-colar-campo").hidden = !op.colar;
  if (op.colar) $("#msg-colar").checked = !!op.colar.marcado;
  $("#msg-enviar-texto").textContent = op.botao || "Abrir o WhatsApp";
  $("#msg-erro").hidden = true;
  $("#msg-passo").hidden = true;
  $("#msg-acoes-1").hidden = false;
  $("#msg-acoes-2").hidden = true;
  desenharDestinosDaMensagem(op.escolhido);
  const janela = $("#msg");
  janela.classList.toggle("modal-largo", !!(op.busca || (op.itens && op.itens.length > 2)));
  if (!janela.open) janela.showModal();
  const d = destinoDaMensagem();
  if (!d && op.busca) $("#msg-contato").focus();
  else if (!op.semTelefone && !$("#msg-telefone").value) $("#msg-telefone").focus();
  else $("#msg-texto").focus();
}

const destinoDaMensagem = () => {
  const { destinos } = janelaMsg.op;
  return destinos.find((d) => d.contato_id === janelaMsg.destino) || destinos[0] || null;
};

const faltaDaMensagem = () => {
  const op = janelaMsg.op;
  const d = destinoDaMensagem();
  return op && op.falta ? op.falta(d, janelaMsg.tipo) : null;
};

function desenharDestinosDaMensagem(escolhido) {
  const op = janelaMsg.op;
  const rotulo = op.rotuloDestino || ((d) => (d.papel ? `${d.nome} (${d.papel})` : d.nome));
  $("#msg-destinos").replaceChildren(...op.destinos.map((d) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: "escolha", textContent: rotulo(d) });
    b.dataset.acao = "msg-destino";
    b.dataset.id = d.contato_id;
    return b;
  }));
  $("#msg-destinos-campo").hidden = op.destinos.length < 2;
  $("#msg-envio").hidden = op.destinos.length === 0;
  escolherDestinoDaMensagem(escolhido);
}

function escolherDestinoDaMensagem(id) {
  const op = janelaMsg.op;
  janelaMsg.destino = id;
  const d = destinoDaMensagem();
  $$("#msg-destinos .escolha").forEach((b) => b.setAttribute("aria-pressed", String(!!d && b.dataset.id === d.contato_id)));
  $("#msg-titulo").textContent = typeof op.titulo === "function" ? op.titulo(d) : op.titulo;
  $("#msg-telefone").value = d && d.telefone ? telefoneBR(d.telefone) : "";
  escolherTipoDaMensagem(janelaMsg.tipo);
}

function escolherTipoDaMensagem(tipo) {
  const op = janelaMsg.op;
  janelaMsg.tipo = tipo;
  $$("#msg-tipos .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tipo === tipo)));
  const d = destinoDaMensagem();
  $("#msg-texto").value = d ? op.texto(d, tipo) : "";
  const falta = faltaDaMensagem();
  $("#msg-falta").hidden = !falta;
  if (falta) {
    $("#msg-falta-texto").textContent = falta.texto;
    $("#msg-falta-botao").textContent = falta.botao;
  }
  $("#msg-texto-campo").hidden = !d || !!falta;
  $("#msg-enviar").disabled = !d || !!falta;
}

/* Outro contato digitado ou escolhido na lista (só nas notas): quem chamou refaz os destinos. */
async function trocarContatoDaMensagem() {
  const op = janelaMsg.op;
  if (!op || !op.busca) return;
  const nome = $("#msg-contato").value.trim();
  // O "change" também vem ao sair do campo: com o mesmo nome, não apaga o telefone digitado.
  if (normalizarNome(nome) === normalizarNome(janelaMsg.nomeBuscado)) return;
  janelaMsg.nomeBuscado = nome;
  const contato = op.busca.contatos.find((c) => normalizarNome(c.nome) === normalizarNome(nome));
  const parte = await op.busca.trocar(nome, contato || null);
  if (!parte || janelaMsg.op !== op) return;
  Object.assign(op, parte);
  desenharDestinosDaMensagem(op.escolhido);
}

async function enviarDaJanelaMensagem() {
  const op = janelaMsg.op;
  const destino = destinoDaMensagem();
  if (!op || !destino || faltaDaMensagem()) return;
  $("#msg-erro").hidden = true;
  const colar = op.colar ? $("#msg-colar").checked : false;
  const r = await op.enviar({ destino, telefone: $("#msg-telefone").value, texto: $("#msg-texto").value, tipo: janelaMsg.tipo, colar });
  if (r && r.erro) {
    // Um aviso comum ficaria escondido atrás da janela.
    $("#msg-erro").textContent = r.erro;
    $("#msg-erro").hidden = false;
    return;
  }
  const depois = op.depois ? op.depois(r) : null;
  if (!depois) {
    $("#msg").close();
    op.aoEnviar?.(r);
    mostrarToast("Conversa aberta no WhatsApp. É só conferir e enviar.");
    return;
  }
  // Notas: a conversa abriu; falta a pessoa contar que enviou (marca como enviada).
  $("#msg-passo-texto").textContent = depois.passo;
  $("#msg-passo").hidden = false;
  $("#msg-acoes-1").hidden = true;
  janelaMsg.acoesDepois = depois.acoes;
  $("#msg-acoes-2").replaceChildren(...depois.acoes.map((a, i) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: `btn${a.primario ? " btn-primario" : ""}` });
    b.dataset.acao = "msg-depois";
    b.dataset.indice = String(i);
    if (a.primario) b.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg>';
    b.append(Object.assign(document.createElement("span"), { textContent: a.rotulo }));
    return b;
  }));
  $("#msg-acoes-2").hidden = false;
  $("#msg-acoes-2 .btn-primario")?.focus();
}

/* Para quem chamou: erro dentro da janela (ex.: ao marcar como enviada). */
function erroNaJanelaMensagem(texto) {
  $("#msg-erro").textContent = texto;
  $("#msg-erro").hidden = false;
}
