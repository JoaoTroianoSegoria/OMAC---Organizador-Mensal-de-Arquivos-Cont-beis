/* OMAC — Relatório mensal: uma tela com as abas Notas fiscais, Extrato bancário e Regras do
 * extrato, um seletor de mês só, e a ilha das notas escolhidas para enviar juntas.
 * As abas em si ficam em notas.js e extrato.js. */
"use strict";

const relatorio = {
  aba: "notas",   // "notas" | "extrato" | "regras"
};

modulos.relatorio = {
  aoMostrar() {
    modulos[moduloDaAba()].aoMostrar();
    desenharIlha();
  },
  carregar() { return modulos[moduloDaAba()].carregar(); },
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

/* ---------- Enviar notas (uma ou várias) ----------
 * Pela janela de mensagem (mensagem.js). Uma nota só usa o mesmo caminho: o Python escolhe o
 * contato pelo nome que está na nota, e dá para trocar por outro (mãe, pai...). */

function abrirLote() {
  const numeros = [...notasEstado.selecao.keys()];
  if (numeros.length) abrirEnvioDeNotas(numeros, { daEscolha: true });
}

/* `daEscolha`: veio da ilha (limpa a escolha depois). `umaPorVez`: veio da lista de notas a
 * enviar (oferece a próxima). */
async function abrirEnvioDeNotas(numeros, { daEscolha = false, umaPorVez = false } = {}) {
  const r = await api().notas_preparar_lote(numeros);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  let lote = r;
  const uma = r.notas.length === 1;
  const itens = r.notas.map((n) => {
    const li = document.createElement("li");
    li.append(`Nº ${n.numero} · ${n.paciente} · ${dataBR(n.competencia)} · `, dinheiro(n.valor_centavos));
    return li;
  });
  if (!uma) {
    const total = texto("li", "Total: ", "rel-lote-total");
    total.append(dinheiro(r.total_centavos));
    itens.push(total);
  }
  abrirJanelaMensagem({
    titulo: uma ? `Enviar a nota nº ${r.notas[0].numero}` : `Enviar ${r.notas.length} notas juntas`,
    itens,
    busca: {
      contatos: r.contatos,
      valor: r.nome,
      dica: r.mesma_pessoa
        ? "Já escolhi pelo nome que está na nota. Para mandar para outra pessoa, digite outro contato."
        : "As notas são de pessoas diferentes: escolha o contato que vai receber (ou escreva um nome novo).",
      trocar: async (nome, contato) => {
        const novo = await api().notas_preparar_lote(numeros, contato ? contato.id : "", contato ? "" : nome);
        if (novo.erro) {
          mostrarToast(novo.erro, { erro: true });
          return null;
        }
        lote = novo;
        return { destinos: novo.destinos, escolhido: novo.escolhido };
      },
    },
    destinos: r.destinos,
    escolhido: r.escolhido,
    texto: (d) => d.mensagem,
    colar: r.colar_disponivel ? { marcado: r.colar_sozinho } : null,
    botao: uma ? "Copiar o PDF e abrir o WhatsApp" : "Copiar os PDFs e abrir o WhatsApp",
    enviar: async ({ destino, telefone, texto: mensagem, colar }) => {
      const x = await api().notas_enviar_lote(numeros, lote.contato_id, destino.contato_id, destino.nome,
        telefone, mensagem, colar);
      if (!x.erro && r.colar_disponivel) estado.cfg.colar_sozinho = colar;
      return x;
    },
    depois: (x) => ({ passo: passoDoEnvio(x), acoes: acoesDepoisDoEnvio(numeros, { daEscolha, umaPorVez }) }),
  });
}

function passoDoEnvio(x) {
  const pdfs = x.qtd === 1 ? "o PDF" : `os ${x.qtd} PDFs`;
  if (x.colando) return `Abri a conversa. Quando ela aparecer, o OMAC cola ${pdfs} sozinho: confira e aperte Enter. Depois volte aqui.`;
  if (x.pdf_copiado) return `Na conversa, aperte Ctrl + V para colar ${pdfs} de uma vez e envie. Depois volte aqui.`;
  return `Abri a pasta das notas: arraste ${pdfs} para a conversa e envie. Depois volte aqui.`;
}

const outrasParaEnviar = (numeros) => whats.notas.filter((n) => !numeros.includes(n.numero));

function acoesDepoisDoEnvio(numeros, { daEscolha, umaPorVez }) {
  const proxima = umaPorVez && outrasParaEnviar(numeros).length > 0;
  const acoesDaJanela = [
    { rotulo: "Agora não", acao: () => $("#msg").close() },
    {
      rotulo: numeros.length === 1 ? "Já enviei, marcar como enviada" : `Já enviei, marcar as ${numeros.length} como enviadas`,
      acao: () => marcarNotasEnviadas(numeros, { daEscolha, proxima: false }),
      primario: !proxima,
    },
  ];
  if (proxima) {
    acoesDaJanela.push({ rotulo: "Já enviei, próxima nota", acao: () => marcarNotasEnviadas(numeros, { proxima: true }), primario: true });
  }
  return acoesDaJanela;
}

async function marcarNotasEnviadas(numeros, { daEscolha = false, proxima = false } = {}) {
  const r = await api().notas_marcar_enviadas(numeros, true);
  if (r.erro) return erroNaJanelaMensagem(r.erro);
  numeros.forEach((n) => notasEstado.enviadas.add(n));
  if (daEscolha) limparSelecao();
  if (notasEstado.dados) desenharNotas();
  await carregarAEnviar();
  if (proxima && whats.notas.length) return abrirEnvioDeNotas([whats.notas[0].numero], { umaPorVez: true });
  $("#msg").close();
  mostrarToast(numeros.length === 1 ? "Nota marcada como enviada." : `${numeros.length} notas marcadas como enviadas.`, {
    acoes: [["Desfazer", async () => {
      await api().notas_marcar_enviadas(numeros, false);
      numeros.forEach((n) => notasEstado.enviadas.delete(n));
      if (notasEstado.dados) desenharNotas();
      carregarAEnviar();
    }]],
  });
}

/* Resposta da tentativa de colar sozinho (vem do Python). */
window.omacColagem = (colou) => {
  mostrarToast(colou
    ? "Colei os PDFs na conversa. Confira e aperte Enter no WhatsApp."
    : "Não consegui colar sozinho. Na conversa, aperte Ctrl + V.");
};
