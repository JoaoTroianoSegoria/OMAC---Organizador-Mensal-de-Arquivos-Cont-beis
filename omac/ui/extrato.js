/* OMAC — módulo de extrato bancário. */
"use strict";

const extrato = {
  dados: null,
  chave: "",
  carregando: false,
  aba: "lancamentos",
  filtro: "todos",
  editando: null, // regra que o formulário está alterando
  voltarParaLancamentos: false,
};
const chaveExtrato = () => `${estado.ano}-${estado.mes}-${estado.cfg.pasta_extratos}`;

modulos.extrato = {
  aoMostrar() {
    preencherSeletores($("#ext-sel-mes"), $("#ext-sel-ano"), extrato.dados?.meses ?? []);
    if (extrato.chave !== chaveExtrato()) carregarExtrato();
  },
  carregar: carregarExtrato,
  ligar() {
    $("#ext-atualizar").addEventListener("click", carregarExtrato);
    $("#form-regra").addEventListener("submit", salvarRegra);
  },
};

Object.assign(acoes, {
  "ext-exportar": exportarFechamento,
  "ext-aba": (alvo) => mostrarAba(alvo.dataset.aba),
  "ext-filtro": (alvo) => { extrato.filtro = alvo.dataset.filtro; desenharLancamentos(); },
  "ext-criar-regra": (alvo) => criarRegraDaLinha(Number(alvo.dataset.indice)),
  "ext-regra-editar": (alvo) => editarRegra(extrato.dados.regras[Number(alvo.dataset.indice)]),
  "ext-regra-apagar": (alvo) => apagarRegra(extrato.dados.regras[Number(alvo.dataset.indice)]),
  "ext-regra-cancelar": limparFormulario,
  "ext-regras-importar": importarRegras,
  "ext-regras-exportar": exportarRegras,
});

async function carregarExtrato() {
  if (extrato.carregando) return;
  if (!estado.cfg.pasta_extratos) return mostrarSemPasta();
  extrato.carregando = true;
  extrato.chave = chaveExtrato();
  const btn = $("#ext-atualizar");
  btn.disabled = true;
  btn.classList.add("girando");
  try {
    const r = await api().extrato_do_mes(estado.ano, estado.mes);
    if (r.sem_pasta) return mostrarSemPasta();
    if (r.erro) return mostrarToast(r.erro, { erro: true });
    extrato.dados = r;
    preencherSeletores($("#ext-sel-mes"), $("#ext-sel-ano"), r.meses);
    desenharExtrato();
  } finally {
    btn.disabled = false;
    btn.classList.remove("girando");
    extrato.carregando = false;
  }
}

function mostrarSemPasta() {
  $("#ext-sem-pasta").hidden = false;
  $("#ext-abas").hidden = true;
  $("#ext-painel").hidden = true;
  $("#ext-regras").hidden = true;
  $("#ext-exportar").disabled = true;
}

function mostrarAba(aba) {
  extrato.aba = aba;
  $$("#ext-abas .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.aba === aba)));
  $("#ext-painel").hidden = aba !== "lancamentos";
  $("#ext-regras").hidden = aba !== "regras";
}

function desenharExtrato() {
  const d = extrato.dados;
  const nomeMes = `${MESES[estado.mes - 1]} de ${estado.ano}`;
  const vazio = d.lancamentos.length === 0;
  $("#ext-sem-pasta").hidden = true;
  $("#ext-abas").hidden = false;
  mostrarAba(extrato.aba);

  $("#ext-entradas").textContent = real.format(d.entradas_centavos / 100);
  $("#ext-saidas").textContent = real.format(d.saidas_centavos / 100);
  $("#ext-saldo").textContent = d.saldo_final_centavos === null ? "—" : real.format(d.saldo_final_centavos / 100);
  $("#ext-preencher").textContent = String(d.a_preencher);
  $("#ext-preencher-cartao").classList.toggle("tem", d.a_preencher > 0);
  $("#ext-legenda").textContent = `Lançamentos de ${nomeMes}`;
  $("#ext-exportar").disabled = vazio;

  const itens = d.avisos.map((a) => [a.arquivo, a.mensagem]);
  $("#ext-avisos").replaceChildren(...listaDeAvisos(itens));
  $("#ext-faixa-avisos").hidden = itens.length === 0;

  $("#ext-resumo").hidden = vazio;
  $("#ext-filtros").hidden = vazio;
  $("#ext-tabela-caixa").hidden = vazio;
  $("#ext-vazio").hidden = !vazio;
  if (vazio) desenharVazioExtrato(nomeMes);

  desenharLancamentos();
  desenharRegras();
}

function desenharVazioExtrato(nomeMes) {
  const d = extrato.dados;
  if (d.qtd_pasta === 0) {
    $("#ext-vazio-ic").setAttribute("href", "#i-pasta");
    $("#ext-vazio-titulo").textContent = d.qtd_extratos === 0 ? "Nenhum extrato nesta pasta" : "Os extratos não têm lançamentos";
    $("#ext-vazio-texto").textContent =
      "Coloque nesta pasta os extratos em PDF do Banco Inter. O OMAC não olha dentro de subpastas.";
    $("#ext-vazio-meses").replaceChildren();
    return;
  }
  $("#ext-vazio-ic").setAttribute("href", "#i-banco");
  $("#ext-vazio-titulo").textContent = `Nenhum lançamento em ${nomeMes}`;
  $("#ext-vazio-texto").textContent = "Baixe o extrato deste mês no Inter e salve na pasta. Meses que já estão lá:";
  $("#ext-vazio-meses").replaceChildren(...botoesDeMeses(d.meses, "lançamento", "lançamentos"));
}

function desenharLancamentos() {
  const d = extrato.dados;
  if (!d) return;
  $$("#ext-filtros .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.filtro === extrato.filtro)));

  const visivel = (l) => extrato.filtro === "todos"
    || (extrato.filtro === "preencher" ? !l.operacao : l.sentido === extrato.filtro);

  const corpo = document.createDocumentFragment();
  d.lancamentos.forEach((l, indice) => {
    if (!visivel(l)) return;
    const tr = document.createElement("tr");

    const tdData = Object.assign(document.createElement("td"), { className: "c-data", textContent: dataBR(l.data) });

    const tdOp = document.createElement("td");
    if (l.operacao) {
      tdOp.textContent = l.operacao;
    } else {
      const caixa = Object.assign(document.createElement("div"), { className: "paciente" });
      const et = Object.assign(document.createElement("span"), { className: "etiqueta etiqueta-aviso", textContent: "a preencher" });
      const b = Object.assign(document.createElement("button"), { className: "btn btn-peq", textContent: "Criar regra" });
      b.dataset.acao = "ext-criar-regra";
      b.dataset.indice = indice;
      caixa.append(et, b);
      tdOp.append(caixa);
    }

    const tdDesc = document.createElement("td");
    tdDesc.className = "c-desc";
    tdDesc.textContent = l.descricao ? `${l.tipo}: ${l.descricao}` : l.tipo;

    const tdValor = Object.assign(document.createElement("td"), {
      className: `c-valor ${l.sentido === "saida" ? "valor-saida" : "valor-entrada"}`,
      textContent: real.format(l.valor_centavos / 100),
    });
    const tdSaldo = Object.assign(document.createElement("td"), {
      className: "c-valor c-saldo", textContent: real.format(l.saldo_centavos / 100),
    });

    tr.append(tdData, tdOp, tdDesc, tdValor, tdSaldo);
    corpo.append(tr);
  });
  if (!corpo.childElementCount) {
    const tr = document.createElement("tr");
    const td = Object.assign(document.createElement("td"), { colSpan: 5, className: "ext-nada", textContent: "Nada por aqui neste filtro." });
    tr.append(td);
    corpo.append(tr);
  }
  $("#ext-corpo").replaceChildren(corpo);
}

async function exportarFechamento() {
  const r = await api().extrato_exportar(estado.ano, estado.mes);
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  const partes = [`Planilha salva: ${r.caminho.split(/[\\/]/).pop()}.`];
  if (r.a_preencher) partes.push(`${r.a_preencher} ${r.a_preencher === 1 ? "linha para preencher" : "linhas para preencher"} (em amarelo).`);
  if (!r.com_notas) partes.push("Sem a aba de notas: escolha a pasta das notas para incluir.");
  toastDeArquivo(partes.join(" "), r.caminho);
}

/* ---------- Regras ---------- */

function desenharRegras() {
  const regras = extrato.dados.regras;
  const ordem = [...regras.keys()].sort((a, b) =>
    regras[a].sentido.localeCompare(regras[b].sentido) || regras[a].quando.localeCompare(regras[b].quando, "pt-BR"));

  $("#regras-corpo").replaceChildren(...ordem.map((i) => {
    const r = regras[i];
    const tr = document.createElement("tr");
    const tdSentido = document.createElement("td");
    tdSentido.className = "c-sentido";
    tdSentido.append(Object.assign(document.createElement("span"), {
      className: "etiqueta", textContent: r.sentido === "entrada" ? "entrada" : "saída",
    }));
    const tdQuando = Object.assign(document.createElement("td"), { textContent: r.quando });
    const tdOp = Object.assign(document.createElement("td"), { textContent: r.operacao });
    const tdAcoes = document.createElement("td");
    tdAcoes.className = "c-acoes-regra";
    tdAcoes.append(botaoDeRegra("ext-regra-editar", i, "i-lapis", `Alterar a regra de ${r.quando}`),
      botaoDeRegra("ext-regra-apagar", i, "i-lixeira", `Apagar a regra de ${r.quando}`));
    tr.append(tdSentido, tdQuando, tdOp, tdAcoes);
    return tr;
  }));

  const nomes = [...new Set(regras.map((r) => r.operacao))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  $("#regra-sugestoes").replaceChildren(...nomes.map((n) => Object.assign(document.createElement("option"), { value: n })));
}

function botaoDeRegra(acao, indice, icone, rotulo) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "btn-linha";
  b.dataset.acao = acao;
  b.dataset.indice = indice;
  b.title = rotulo;
  b.setAttribute("aria-label", rotulo);
  b.innerHTML = `<svg class="ic"><use href="#${icone}"/></svg>`;
  return b;
}

function preencherFormulario(regra, editando) {
  extrato.editando = editando ? regra : null;
  $("#regra-sentido").value = regra.sentido;
  $("#regra-quando").value = regra.quando;
  $("#regra-operacao").value = regra.operacao;
  $("#form-regra-titulo").textContent = editando ? "Alterar regra" : "Nova regra";
  $("#form-regra-salvar").textContent = editando ? "Salvar alteração" : "Adicionar regra";
  $("#form-regra-cancelar").hidden = !editando && !extrato.voltarParaLancamentos;
}

function limparFormulario() {
  const voltar = extrato.voltarParaLancamentos;
  extrato.voltarParaLancamentos = false;
  preencherFormulario({ sentido: "saida", quando: "", operacao: "" }, false);
  if (voltar) mostrarAba("lancamentos");
}

function criarRegraDaLinha(indice) {
  const l = extrato.dados.lancamentos[indice];
  extrato.voltarParaLancamentos = true;
  preencherFormulario({ sentido: l.sentido, quando: l.descricao || l.tipo, operacao: "" }, false);
  mostrarAba("regras");
  $("#conteudo").scrollTop = 0;
  $("#regra-operacao").focus();
}

function editarRegra(regra) {
  extrato.voltarParaLancamentos = false;
  preencherFormulario(regra, true);
  $("#conteudo").scrollTop = 0;
  $("#regra-operacao").focus();
}

async function salvarRegra(e) {
  e.preventDefault();
  const nova = {
    sentido: $("#regra-sentido").value,
    quando: $("#regra-quando").value,
    operacao: $("#regra-operacao").value,
  };
  const r = await api().extrato_salvar_regra(nova, extrato.editando);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  limparFormulario();
  await carregarExtrato();
  mostrarToast("Regra salva. Ela já vale para todos os meses.");
}

async function apagarRegra(regra) {
  const r = await api().extrato_apagar_regra(regra);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  await carregarExtrato();
  mostrarToast(`Regra apagada: ${regra.quando}`, {
    acoes: [["Desfazer", async () => {
      await api().extrato_salvar_regra(regra, null);
      await carregarExtrato();
    }]],
  });
}

async function importarRegras() {
  const r = await api().extrato_importar_regras();
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  await carregarExtrato();
  mostrarToast(`${r.qtd} ${r.qtd === 1 ? "regra carregada" : "regras carregadas"}.`);
}

async function exportarRegras() {
  const r = await api().extrato_exportar_regras();
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  toastDeArquivo(`Regras salvas: ${r.caminho.split(/[\\/]/).pop()}`, r.caminho);
}
