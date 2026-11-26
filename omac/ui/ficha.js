"use strict";

/* Ficha do paciente (1.15.0): clicar no nome em Atendimentos ou Tratamentos.
 * Mostra os dados, os responsáveis e dependentes (cada um abre a ficha dele, com "voltar") e um
 * resumo: tratamento, últimos atendimentos e notas. Só mostra: o Editar abre a janela de contato.
 * Os dados vêm de contatos_ficha (omac/contatos/ficha.py). */

const fichaPaciente = { pilha: [], atual: null };

Object.assign(acoes, {
  "ficha-abrir": (alvo) => abrirFicha(alvo.dataset.contato),
  "ficha-vinculo": (alvo) => abrirFicha(alvo.dataset.contato, { empilhar: true }),
  "ficha-voltar": () => {
    const anterior = fichaPaciente.pilha.pop();
    if (anterior) abrirFicha(anterior, { voltando: true });
  },
  "ficha-editar": () => editarDaFicha(),
  "ficha-fechar": () => $("#ficha").close(),
  "ficha-nota": (alvo) => abrirNotaDaFicha(alvo.dataset.arquivo),
});

/* O nome do paciente numa tabela, como botão que abre a ficha. */
function nomeComFicha(nome, contatoId, classe = "") {
  if (!contatoId || nome === "(contato apagado)") return texto("span", nome, classe);
  const b = Object.assign(document.createElement("button"), { type: "button", className: `ficha-nome ${classe}`.trim(), textContent: nome });
  b.dataset.acao = "ficha-abrir";
  b.dataset.contato = contatoId;
  b.title = `Ver a ficha de ${nome}`;
  return b;
}

async function abrirFicha(contatoId, { empilhar = false, voltando = false } = {}) {
  const r = await api().contatos_ficha(contatoId);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  if (empilhar && fichaPaciente.atual) fichaPaciente.pilha.push(fichaPaciente.atual.id);
  if (!empilhar && !voltando) fichaPaciente.pilha = [];
  fichaPaciente.atual = r;
  desenharFichaDoPaciente(r);
  const janela = $("#ficha");
  if (!janela.open) janela.showModal();
  $("#ficha-corpo").scrollTop = 0;
}

function desenharFichaDoPaciente(f) {
  $("#ficha-titulo").textContent = f.nome;
  $("#ficha-sub").textContent = f.idade != null ? `${f.idade} ${f.idade === 1 ? "ano" : "anos"}` : "";
  $("#ficha-sub").hidden = f.idade == null;
  const voltar = $("#ficha-voltar");
  const anterior = fichaPaciente.pilha.length > 0;
  voltar.hidden = !anterior;

  $("#ficha-dados").replaceChildren(...dadosDaPessoa(f));
  $("#ficha-vinculos-bloco").hidden = f.vinculos.length === 0;
  $("#ficha-vinculos").replaceChildren(...f.vinculos.map(cartaoDoVinculo));
  desenharTratamentoDaFicha(f.tratamento);
  desenharAtendimentosDaFicha(f.atendimentos);
  desenharNotasDaFicha(f.notas);
}

function dadosDaPessoa(p) {
  const linha = (rotulo, valor) => {
    const div = texto("div", "", "ficha-dado");
    div.append(texto("dt", rotulo), valor ? texto("dd", valor) : texto("dd", "Não informado", "ficha-falta"));
    return div;
  };
  return [
    linha("Telefone", p.telefone ? telefoneBR(p.telefone) : ""),
    linha("CPF", p.cpf),
    linha("Nascimento", p.nascimento ? dataBR(p.nascimento) : ""),
  ];
}

function cartaoDoVinculo(v) {
  const b = Object.assign(document.createElement("button"), { type: "button", className: "ficha-vinculo" });
  b.dataset.acao = "ficha-vinculo";
  b.dataset.contato = v.id;
  b.title = `Ver a ficha de ${v.nome}`;
  const topo = texto("span", "", "ficha-vinculo-topo");
  topo.append(texto("strong", v.nome), texto("span", v.relacao, `etiqueta${v.tipo === "responsavel" ? " etiqueta-acento" : ""}`));
  const detalhes = [
    v.telefone ? telefoneBR(v.telefone) : "sem telefone",
    v.cpf ? `CPF ${v.cpf}` : "sem CPF",
    v.nascimento ? `nasceu em ${dataBR(v.nascimento)}${v.idade != null ? ` (${v.idade} ${v.idade === 1 ? "ano" : "anos"})` : ""}` : "",
  ].filter(Boolean);
  b.append(topo, texto("span", detalhes.join(" · "), "ficha-vinculo-detalhe"));
  return b;
}

function desenharTratamentoDaFicha(t) {
  $("#ficha-tratamento-bloco").hidden = !t;
  if (!t) return;
  const partes = [texto("strong", t.situacao)];
  if (t.mes) partes.push(` · ${t.mes}`);
  const linhas = [texto("p", "", "ficha-linha")];
  linhas[0].append(...partes);
  const mais = [];
  if (t.valor_centavos != null) mais.push(["manutenção de ", dinheiro(t.valor_centavos)]);
  if (t.esperados) mais.push([`veio em ${t.veio} de ${t.esperados} ${t.esperados === 1 ? "mês" : "meses"}`]);
  if (t.proxima_consulta) mais.push([`próxima consulta em ${dataBR(t.proxima_consulta)}`]);
  if (mais.length) linhas.push(frase("p", "ficha-linha ficha-suave", mais));
  $("#ficha-tratamento").replaceChildren(...linhas);
}

function desenharAtendimentosDaFicha(a) {
  const partes = [[`${a.qtd} ${a.qtd === 1 ? "atendimento" : "atendimentos"}`], ["pago ", dinheiro(a.pago_centavos)]];
  if (a.a_receber_centavos) partes.push(["falta receber ", dinheiro(a.a_receber_centavos)]);
  $("#ficha-atendimentos-resumo").replaceChildren(a.qtd ? frase("span", "", partes) : "Nenhum atendimento na ficha.");
  $("#ficha-atendimentos").replaceChildren(...a.ultimos.map((x) => {
    const li = texto("li", "", "ficha-item");
    const titulo = [x.tratamento || "Atendimento", x.lista].filter(Boolean).join(" · ");
    li.append(
      texto("span", dataBR(x.data), "ficha-item-data"),
      texto("span", titulo, "ficha-item-nome"),
      texto("span", x.valor_centavos == null ? "sem valor" : dinheiro(x.valor_centavos), "ficha-item-valor"),
      texto("span", x.pagamento, `etiqueta ficha-pg-${x.situacao}`),
    );
    return li;
  }));
}

function desenharNotasDaFicha(n) {
  if (!n) {
    $("#ficha-notas-resumo").textContent = "As notas ainda não foram lidas. Abra o Relatório mensal para ler a pasta.";
    $("#ficha-notas").replaceChildren();
    return;
  }
  $("#ficha-notas-resumo").replaceChildren(n.qtd
    ? frase("span", "", [[`${n.qtd} ${n.qtd === 1 ? "nota" : "notas"}`], [dinheiro(n.total_centavos)]])
    : "Nenhuma nota com este nome na pasta.");
  $("#ficha-notas").replaceChildren(...n.ultimas.map((x) => {
    const li = texto("li", "", `ficha-item${x.cancelada ? " ficha-cancelada" : ""}`);
    const b = Object.assign(document.createElement("button"), { type: "button", className: "ficha-nota", textContent: `Nº ${x.numero}` });
    b.dataset.acao = "ficha-nota";
    b.dataset.arquivo = x.arquivo;
    b.title = "Abrir o PDF da nota";
    li.append(
      texto("span", dataBR(x.competencia), "ficha-item-data"),
      b,
      texto("span", x.de ? `de ${x.de} (como responsável)` : "", "ficha-item-nome ficha-suave"),
      texto("span", dinheiro(x.valor_centavos), "ficha-item-valor"),
    );
    if (x.cancelada) li.append(texto("span", "cancelada", "etiqueta"));
    return li;
  }));
}

/* Partes (cada uma uma lista de textos e elementos, como o valor com o olho) separadas por " · ". */
function frase(tag, classe, partes) {
  const el = texto(tag, "", classe);
  partes.forEach((parte, i) => el.append(...(i ? [" · "] : []), ...parte));
  return el;
}

async function abrirNotaDaFicha(arquivo) {
  const r = await api().abrir_nota(arquivo);
  if (r.erro) mostrarToast(r.erro, { erro: true });
}

/* Editar: a janela de contato de sempre. Ao salvar, a ficha volta atualizada e a tela de trás recarrega. */
function editarDaFicha() {
  const id = fichaPaciente.atual?.id;
  if (!id) return;
  $("#ficha").close();
  abrirContatoPorId(id, {
    depoisDeSalvar: () => {
      if (estado.view === "atendimentos") carregarFicha();
      abrirFicha(id, { voltando: true });
    },
  });
}
