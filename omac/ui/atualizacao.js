/* OMAC — atualização pelo próprio app. É sempre opcional. */
"use strict";

modulos.atualizacao = {
  async ligar() {
    const r = await api().atualizacao_disponivel_aqui();
    const disponivel = !r.erro && r.disponivel;
    $("#atualizacao-procurar").disabled = !disponivel;
    $("#atualizacao-indisponivel").hidden = disponivel;
    $("#atualizacao").addEventListener("cancel", (e) => {
      if (atualizacaoEmAndamento) e.preventDefault();
    });
  },
  aoIniciar: () => procurarAtualizacao(false),
};

let atualizacaoEmAndamento = false;

Object.assign(acoes, {
  "atualizacao-procurar": () => procurarAtualizacao(true),
  "atualizacao-agora-nao": async () => {
    $("#atualizacao").close();
    const r = await api().atualizacao_adiar();
    if (r.erro) mostrarToast(r.erro, { erro: true });
  },
  "atualizacao-instalar": instalarAtualizacao,
  "atualizacao-pagina": () => api().atualizacao_abrir_pagina(),
});

window.omacProgressoAtualizacao = (recebidos, total) => {
  const pct = total ? Math.min(100, Math.round((recebidos / total) * 100)) : 0;
  $("#atualizacao-progresso-texto").textContent = `Baixando… ${pct}%`;
  $("#atualizacao-cheio").style.width = `${pct}%`;
  $("#atualizacao-barra").setAttribute("aria-valuenow", String(pct));
};

async function procurarAtualizacao(pedidoNaTela) {
  const r = await api().atualizacao_procurar(pedidoNaTela);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  if (r.versao) return abrirJanelaDeAtualizacao(r);
  if (pedidoNaTela && !r.indisponivel) mostrarToast("Você já está com a versão mais recente.");
}

function abrirJanelaDeAtualizacao({ versao, novidades }) {
  $("#atualizacao-titulo").textContent = `Nova versão disponível: ${versao}`;
  $("#atualizacao-novidades").replaceChildren(...novidades.map((n) =>
    Object.assign(document.createElement("li"), { textContent: n })));
  $("#atualizacao-erro").hidden = true;
  $("#atualizacao-pagina").hidden = true;
  $("#atualizacao-progresso").hidden = true;
  $("#atualizacao-acoes").hidden = false;
  const janela = $("#atualizacao");
  if (!janela.open) janela.showModal();
}

async function instalarAtualizacao() {
  atualizacaoEmAndamento = true;
  $("#atualizacao-acoes").hidden = true;
  $("#atualizacao-erro").hidden = true;
  $("#atualizacao-pagina").hidden = true;
  $("#atualizacao-progresso").hidden = false;
  window.omacProgressoAtualizacao(0, 1);

  const r = await api().atualizacao_instalar();
  atualizacaoEmAndamento = false;
  if (r.erro) {
    $("#atualizacao-progresso").hidden = true;
    $("#atualizacao-acoes").hidden = false;
    $("#atualizacao-erro").textContent = r.erro;
    $("#atualizacao-erro").hidden = false;
    $("#atualizacao-pagina").hidden = false;
    return;
  }
  $("#atualizacao-progresso-texto").textContent = "Abrindo a versão nova…";
}
