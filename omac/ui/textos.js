/* OMAC — Textos prontos (antes "Comandos", dentro de Lembretes): textos que se mandam sempre,
 * separados por categoria, com Copiar. As [variáveis] só são trocadas na janela Emitir (emitir.js);
 * aqui o texto é copiado como está. */
"use strict";

const textos = {
  categorias: [],
  categoria: "", // id da categoria aberta
  comandoEditando: null,
  categoriaEditando: null,
};

modulos.textos = {
  aoMostrar: carregarComandos,
  carregar: carregarComandos,
  ligar() {
    $("#form-lb-comando").addEventListener("submit", salvarComando);
    $("#form-lb-categoria").addEventListener("submit", salvarCategoria);
  },
};

Object.assign(acoes, {
  "lb-categoria": (alvo) => { textos.categoria = alvo.dataset.id; desenharComandos(); },
  "lb-categoria-nova": () => abrirCategoria(null),
  "lb-categoria-renomear": () => abrirCategoria(categoriaAtual()),
  "lb-categoria-apagar": apagarCategoria,
  "lb-categoria-mover": (alvo) => moverCategoria(Number(alvo.dataset.passo)),
  "lb-categoria-fechar": () => $("#lb-categoria").close(),
  "lb-comando-novo": () => abrirComando(null),
  "lb-comando-editar": (alvo) => abrirComando(comandoPorId(alvo.dataset.id)),
  "lb-comando-fechar": () => $("#lb-comando").close(),
  "lb-comando-apagar": apagarComando,
  "lb-comando-mover": (alvo) => moverComando(alvo.dataset.id, Number(alvo.dataset.passo)),
  "lb-copiar": (alvo) => copiarComando(alvo.dataset.id),
});

async function carregarComandos() {
  aplicarComandos(await api().comandos_listar());
}

function aplicarComandos(r) {
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  textos.categorias = r.categorias;
  if (!r.categorias.some((c) => c.id === textos.categoria)) textos.categoria = r.categorias.length ? r.categorias[0].id : "";
  desenharSeMudou("lb-comandos", [r, textos.categoria], desenharComandos);
}

const categoriaAtual = () => textos.categorias.find((c) => c.id === textos.categoria) || null;
const comandoPorId = (id) => (categoriaAtual() ? categoriaAtual().comandos.find((c) => c.id === id) : null);

function desenharComandos() {
  const cat = categoriaAtual();
  $("#lb-categorias").replaceChildren(...textos.categorias.map((c) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: "escolha" });
    b.dataset.acao = "lb-categoria";
    b.dataset.id = c.id;
    b.setAttribute("aria-pressed", String(c.id === textos.categoria));
    b.append(c.nome);
    if (c.comandos.length) b.append(" ", Object.assign(document.createElement("span"), { className: "ag-qtd", textContent: `(${c.comandos.length})` }));
    return b;
  }));
  $("#lb-categorias").hidden = textos.categorias.length === 0;
  $("#lb-categoria-cab").hidden = !cat;
  const vazio = !cat || cat.comandos.length === 0;
  $("#lb-comandos").hidden = vazio;
  $("#lb-comandos-dica").hidden = vazio;
  $("#lb-comandos-vazio").hidden = !vazio;
  $("#lb-comandos-vazio-titulo").textContent = cat ? "Nenhum texto nesta categoria" : "Nenhuma categoria ainda";
  $("#lb-comandos-vazio-texto").textContent = cat
    ? "Clique em Novo texto e escreva algo que você manda sempre, como o endereço ou o horário."
    : "Crie uma categoria (por exemplo: Geral, Pós-atendimento, Orçamentos) e depois os textos dentro dela.";
  if (!cat) {
    $("#lb-comandos").replaceChildren();
    return;
  }
  $("#lb-categoria-nome").textContent = cat.nome;
  const i = textos.categorias.indexOf(cat);
  const subir = botaoIcone("lb-categoria-mover", "i-cima", `Mover “${cat.nome}” para a esquerda`, { passo: -1 });
  subir.disabled = i === 0;
  subir.querySelector("svg").classList.add("lb-seta-esq");
  const descer = botaoIcone("lb-categoria-mover", "i-cima", `Mover “${cat.nome}” para a direita`, { passo: 1 });
  descer.disabled = i === textos.categorias.length - 1;
  descer.querySelector("svg").classList.add("lb-seta-dir");
  $("#lb-categoria-botoes").replaceChildren(subir, descer,
    botaoIcone("lb-categoria-renomear", "i-lapis", `Renomear “${cat.nome}”`, {}),
    botaoIcone("lb-categoria-apagar", "i-lixeira", `Apagar a categoria “${cat.nome}”`, {}));
  $("#lb-comandos").replaceChildren(...cat.comandos.map((c, n) => {
    const li = Object.assign(document.createElement("li"), { className: "lb-comando vidro" });
    const cab = Object.assign(document.createElement("div"), { className: "lb-comando-cab" });
    cab.append(Object.assign(document.createElement("strong"), { textContent: c.nome }));
    const botoes = Object.assign(document.createElement("div"), { className: "lb-livre-botoes" });
    const cima = botaoIcone("lb-comando-mover", "i-cima", `Subir “${c.nome}”`, { id: c.id, passo: -1 });
    cima.disabled = n === 0;
    const baixo = botaoIcone("lb-comando-mover", "i-seta", `Descer “${c.nome}”`, { id: c.id, passo: 1 });
    baixo.disabled = n === cat.comandos.length - 1;
    const copiar = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-primario btn-peq" });
    copiar.dataset.acao = "lb-copiar";
    copiar.dataset.id = c.id;
    copiar.innerHTML = '<svg class="ic"><use href="#i-copiar"/></svg><span>Copiar</span>';
    copiar.setAttribute("aria-label", `Copiar “${c.nome}”`);
    botoes.append(cima, baixo, botaoIcone("lb-comando-editar", "i-lapis", `Alterar “${c.nome}”`, { id: c.id }));
    const rodapeDele = Object.assign(document.createElement("div"), { className: "lb-comando-rodape" });
    rodapeDele.append(botoes, copiar);
    li.append(cab, Object.assign(document.createElement("p"), { className: "lb-comando-texto", textContent: c.texto }), rodapeDele);
    return li;
  }));
}


async function copiarComando(id) {
  const c = comandoPorId(id);
  if (!c) return;
  if (await copiarTexto(c.texto)) mostrarToast(`Copiado: ${c.nome}`);
  else mostrarToast("Não consegui copiar. Selecione o texto e use Ctrl + C.", { erro: true });
}

function abrirComando(c) {
  if (!categoriaAtual()) return;
  textos.comandoEditando = c;
  $("#lb-comando-titulo").textContent = c ? "Alterar texto" : `Novo texto em ${categoriaAtual().nome}`;
  $("#lb-comando-nome").value = c ? c.nome : "";
  $("#lb-comando-texto").value = c ? c.texto : "";
  $("#lb-comando-apagar").hidden = !c;
  $("#lb-comando-erro").hidden = true;
  $("#lb-comando").showModal();
  $("#lb-comando-nome").focus();
}

async function salvarComando(e) {
  e.preventDefault();
  const r = await api().comandos_salvar(textos.categoria,
    { nome: $("#lb-comando-nome").value, texto: $("#lb-comando-texto").value },
    textos.comandoEditando ? textos.comandoEditando.id : null);
  if (r.erro) {
    $("#lb-comando-erro").textContent = r.erro;
    $("#lb-comando-erro").hidden = false;
    return;
  }
  $("#lb-comando").close();
  aplicarComandos(r);
}

async function apagarComando() {
  const c = textos.comandoEditando;
  const categoria = textos.categoria;
  const r = await api().comandos_apagar(categoria, c.id);
  $("#lb-comando").close();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarComandos(r);
  mostrarToast(`Texto apagado: ${c.nome}`, {
    acoes: [["Desfazer", async () => aplicarComandos(await api().comandos_restaurar(categoria, r.apagado, r.posicao))]],
  });
}

async function moverComando(id, passo) {
  const r = await api().comandos_mover(textos.categoria, id, passo);
  aplicarComandos(r);
  $(`[data-acao="lb-comando-mover"][data-id="${id}"][data-passo="${passo}"]`)?.focus();
}

function abrirCategoria(c) {
  textos.categoriaEditando = c;
  $("#lb-categoria-titulo").textContent = c ? "Renomear categoria" : "Nova categoria";
  $("#lb-categoria-campo").value = c ? c.nome : "";
  $("#lb-categoria-erro").hidden = true;
  $("#lb-categoria").showModal();
  $("#lb-categoria-campo").focus();
}

async function salvarCategoria(e) {
  e.preventDefault();
  const r = await api().comandos_salvar_categoria($("#lb-categoria-campo").value,
    textos.categoriaEditando ? textos.categoriaEditando.id : null);
  if (r.erro) {
    $("#lb-categoria-erro").textContent = r.erro;
    $("#lb-categoria-erro").hidden = false;
    return;
  }
  $("#lb-categoria").close();
  textos.categoria = r.salva.id;
  aplicarComandos(r);
}

async function apagarCategoria() {
  const cat = categoriaAtual();
  const r = await api().comandos_apagar_categoria(cat.id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarComandos(r);
  const qtd = cat.comandos.length ? ` (com ${plural(cat.comandos.length, "texto", "textos")})` : "";
  mostrarToast(`Categoria apagada: ${cat.nome}${qtd}`, {
    acoes: [["Desfazer", async () => {
      const volta = await api().comandos_restaurar_categoria(r.apagada, r.posicao);
      textos.categoria = r.apagada.id;
      aplicarComandos(volta);
    }]],
  });
}

async function moverCategoria(passo) {
  const id = textos.categoria;
  aplicarComandos(await api().comandos_mover_categoria(id, passo));
  $(`[data-acao="lb-categoria-mover"][data-passo="${passo}"]`)?.focus();
}
