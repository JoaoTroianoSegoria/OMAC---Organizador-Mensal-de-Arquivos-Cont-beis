/* OMAC — Modelos: documentos que a clínica imprime sempre (atestado, receita, termo…). */
"use strict";

const modelosEstado = {
  lista: [],
  busca: "",
  editando: null,   // modelo aberto na janela (null = novo)
  arquivo: null,    // arquivo escolhido na janela: {caminho, nome, titulo}
  sugestao: "",     // título sugerido pelo nome do arquivo (trocar o arquivo troca a sugestão)
};

modulos.modelos = {
  aoMostrar: carregarModelos,
  carregar: carregarModelos,
  ligar() {
    $("#md-busca").addEventListener("input", (e) => { modelosEstado.busca = e.target.value; desenharModelos(); });
    $("#form-md-modelo").addEventListener("submit", salvarModelo);
  },
};

Object.assign(acoes, {
  "md-novo": () => abrirModelo(null),
  "md-editar": (alvo) => abrirModelo(modelosEstado.lista.find((m) => m.id === alvo.dataset.id)),
  "md-escolher-arquivo": escolherArquivoDoModelo,
  "md-fechar": () => $("#md-modelo").close(),
  "md-apagar": apagarModelo,
  "md-imprimir": (alvo) => imprimirModelo(alvo.dataset.id),
  "md-abrir": (alvo) => abrirCopiaDoModelo(alvo.dataset.id),
  "md-baixar": (alvo) => baixarModelo(alvo.dataset.id),
});

async function carregarModelos() {
  const r = await api().modelos_listar();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarModelos(r);
}

function aplicarModelos(r) {
  modelosEstado.lista = r.modelos;
  desenharModelos();
}

function desenharModelos() {
  const todos = modelosEstado.lista;
  const busca = normalizarNome(modelosEstado.busca);
  const lista = busca ? todos.filter((m) => normalizarNome(m.titulo).includes(busca)) : todos;
  $("#md-barra").hidden = todos.length < 6 && !busca;
  $("#md-dica").hidden = todos.length === 0;
  $("#md-lista").replaceChildren(...lista.map(cartaoDeModelo));
  $("#md-vazio").hidden = lista.length > 0;
  $("#md-vazio-acoes").hidden = todos.length > 0;
  if (!todos.length) {
    $("#md-vazio-titulo").textContent = "Nenhum modelo ainda";
    $("#md-vazio-texto").textContent = "Adicione um PDF, um documento do Word ou uma imagem: atestado, receita, " +
      "termo de consentimento… Depois é só clicar em Imprimir.";
  } else if (!lista.length) {
    $("#md-vazio-titulo").textContent = "Nenhum modelo encontrado";
    $("#md-vazio-texto").textContent = `Nenhum título tem “${modelosEstado.busca.trim()}”.`;
  }
}

function botaoDeModelo(acao, id, icone, rotulo, classe = "btn btn-peq") {
  const b = Object.assign(document.createElement("button"), { type: "button", className: classe });
  b.dataset.acao = acao;
  b.dataset.id = id;
  b.innerHTML = `<svg class="ic"><use href="#${icone}"/></svg>`;
  b.append(texto("span", rotulo));
  return b;
}

function cartaoDeModelo(m) {
  const li = Object.assign(document.createElement("li"), { className: "md-cartao vidro" });
  const topo = Object.assign(document.createElement("div"), { className: "md-topo" });
  const tipo = texto("span", m.extensao.toUpperCase(), `md-tipo md-tipo-${m.tipo === "PDF" ? "pdf" : m.tipo === "Word" ? "word" : m.tipo === "Imagem" ? "imagem" : "outro"}`);
  tipo.title = m.tipo;
  const titulo = texto("h2", m.titulo, "md-titulo");
  topo.append(tipo, titulo, botaoIcone("md-editar", "i-lapis", `Alterar o modelo ${m.titulo}`, { id: m.id }));
  li.append(topo);
  if (m.existe) {
    li.append(texto("p", m.nome_original ? `Arquivo: ${m.nome_original}` : "", "md-original"));
  } else {
    li.append(texto("p", "O arquivo sumiu da pasta do OMAC. Clique no lápis e troque o arquivo.", "md-sumiu"));
  }
  const acoesDoCartao = Object.assign(document.createElement("div"), { className: "md-acoes" });
  const imprimir = botaoDeModelo("md-imprimir", m.id, "i-impressora", "Imprimir", "btn btn-primario btn-peq");
  imprimir.setAttribute("aria-label", `Imprimir ${m.titulo}`);
  const abrir = botaoDeModelo("md-abrir", m.id, "i-abrir", "Abrir");
  abrir.setAttribute("aria-label", `Abrir uma cópia de ${m.titulo}`);
  abrir.title = "Abre uma cópia: o que você escrever nela não muda o modelo";
  const baixar = botaoDeModelo("md-baixar", m.id, "i-baixar", "Baixar");
  baixar.setAttribute("aria-label", `Salvar uma cópia de ${m.titulo}`);
  baixar.title = "Salvar uma cópia onde você escolher";
  for (const b of [imprimir, abrir, baixar]) b.disabled = !m.existe;
  acoesDoCartao.append(imprimir, abrir, baixar);
  li.append(acoesDoCartao);
  return li;
}

/* ---------- Janela: novo ou alterar ---------- */

function abrirModelo(m) {
  modelosEstado.editando = m || null;
  modelosEstado.arquivo = null;
  modelosEstado.sugestao = "";
  $("#md-modelo-titulo").textContent = m ? "Alterar modelo" : "Novo modelo";
  $("#md-titulo").value = m ? m.titulo : "";
  $("#md-apagar").hidden = !m;
  $("#md-modelo-erro").hidden = true;
  mostrarArquivoDoModelo();
  $("#md-modelo").showModal();
  if (m) $("#md-titulo").focus();
  else $("#md-escolher").focus();
}

function mostrarArquivoDoModelo() {
  const { editando: m, arquivo } = modelosEstado;
  const nome = arquivo ? arquivo.nome : m ? (m.existe ? m.nome_original || "Arquivo guardado" : "O arquivo sumiu") : "";
  $("#md-arquivo-nome").textContent = nome || "Nenhum arquivo escolhido";
  $("#md-arquivo-nome").classList.toggle("md-arquivo-vazio", !nome);
  $("#md-escolher").textContent = m || arquivo ? "Trocar arquivo" : "Escolher arquivo";
}

async function escolherArquivoDoModelo() {
  const r = await api().modelos_escolher_arquivo();
  if (!r || r.cancelado) return;
  if (r.erro) {
    $("#md-modelo-erro").textContent = r.erro;
    $("#md-modelo-erro").hidden = false;
    return;
  }
  $("#md-modelo-erro").hidden = true;
  // O título acompanha o arquivo enquanto a pessoa não escreveu outro.
  const atual = $("#md-titulo").value.trim();
  if (!atual || atual === modelosEstado.sugestao) $("#md-titulo").value = r.titulo;
  modelosEstado.sugestao = r.titulo;
  modelosEstado.arquivo = r;
  mostrarArquivoDoModelo();
  $("#md-titulo").focus();
}

async function salvarModelo(e) {
  e.preventDefault();
  const { editando, arquivo } = modelosEstado;
  const r = await api().modelos_salvar({
    id: editando ? editando.id : "",
    titulo: $("#md-titulo").value,
    caminho: arquivo ? arquivo.caminho : "",
  });
  if (r.erro) {
    $("#md-modelo-erro").textContent = r.erro;
    $("#md-modelo-erro").hidden = false;
    return;
  }
  $("#md-modelo").close();
  aplicarModelos(r);
  mostrarToast(editando ? "Modelo alterado." : "Modelo adicionado. Já dá para imprimir.");
}

async function apagarModelo() {
  const m = modelosEstado.editando;
  const r = await api().modelos_apagar(m.id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  $("#md-modelo").close();
  aplicarModelos(r);
  mostrarToast(`Modelo “${m.titulo}” apagado.`, {
    acoes: [["Desfazer", async () => {
      const volta = await api().modelos_restaurar(r.apagado, r.posicao);
      if (volta.erro) return mostrarToast(volta.erro, { erro: true });
      aplicarModelos(volta);
    }]],
  });
}

/* ---------- Imprimir, abrir, baixar ---------- */

async function imprimirModelo(id) {
  const r = await api().modelos_imprimir(id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  mostrarToast(r.impresso
    ? `“${r.titulo}” foi para a impressora.`
    : `Abri “${r.titulo}”. Para imprimir, aperte Ctrl + P.`);
}

async function abrirCopiaDoModelo(id) {
  const r = await api().modelos_abrir(id);
  if (r.erro) mostrarToast(r.erro, { erro: true });
}

async function baixarModelo(id) {
  const r = await api().modelos_baixar(id);
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  toastDeArquivo(`Cópia salva: ${r.caminho.split(/[\\/]/).pop()}`, r.caminho);
}

/* ---------- Widget do Início ---------- */

registrarWidget("modelos", {
  icone: "i-impressora",
  desenhar(corpo, o) {
    if (!o.modelos.length) {
      corpo.append(texto("p", "Nenhum modelo ainda. Guarde aqui o que você imprime sempre.", "dica"),
        rodape(botaoIr("Adicionar modelo", "modelos")));
      return;
    }
    const ul = Object.assign(document.createElement("ul"), { className: "ini-lista" });
    for (const m of o.modelos.slice(0, 6)) {
      const li = Object.assign(document.createElement("li"), { className: "ini-conta" });
      const b = botaoDeModelo("md-imprimir", m.id, "i-impressora", "Imprimir");
      b.setAttribute("aria-label", `Imprimir ${m.titulo}`);
      li.append(texto("span", m.titulo), b);
      ul.append(li);
    }
    corpo.append(ul);
    if (o.modelos.length > 6) corpo.append(texto("p", `e mais ${o.modelos.length - 6}`, "dica"));
    corpo.append(rodape(botaoIr("Ver modelos", "modelos")));
  },
});
