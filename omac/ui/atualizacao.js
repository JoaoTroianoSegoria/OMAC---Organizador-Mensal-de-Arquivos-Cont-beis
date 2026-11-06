/* OMAC — aviso de versão nova. O download é feito pelo navegador, e é sempre opcional. */
"use strict";

modulos.atualizacao = {
  async ligar() {
    const r = await api().atualizacao_disponivel_aqui();
    const disponivel = !r.erro && r.disponivel;
    $("#atualizacao-procurar").disabled = !disponivel;
    $("#atualizacao-indisponivel").hidden = disponivel;
  },
  aoIniciar: () => procurarAtualizacao(false),
};

Object.assign(acoes, {
  "atualizacao-procurar": () => procurarAtualizacao(true),
  "atualizacao-agora-nao": async () => {
    $("#atualizacao").close();
    const r = await api().atualizacao_adiar();
    if (r.erro) mostrarToast(r.erro, { erro: true });
  },
  "atualizacao-pagina": async () => {
    $("#atualizacao").close();
    const r = await api().atualizacao_abrir_pagina();
    if (r.erro) mostrarToast(r.erro, { erro: true });
  },
});

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
  const janela = $("#atualizacao");
  if (!janela.open) janela.showModal();
}
