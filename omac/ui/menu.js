/* OMAC — menu lateral em grupos (Financeiro, Atendimento…), que a pessoa organiza.
 *
 * Os botões das telas continuam no index.html; aqui eles só são postos dentro dos grupos.
 * A ordem fica em estado.cfg.menu: [{ nome: "Financeiro", itens: ["relatorio", "resumo"] }, ...].
 * Vazio = MENU_PADRAO. Uma tela que não está em grupo nenhum (uma tela nova de uma versão
 * mais nova) entra no fim do último grupo. O Início fica sempre em cima e as Configurações
 * sempre embaixo. Para não arrastar sem querer, só dá para mudar em "Organizar menu".
 */
"use strict";

const MENU_PADRAO = [
  { nome: "Financeiro", itens: ["relatorio", "resumo"] },
  { nome: "Atendimento", itens: ["atendimentos", "tratamentos", "contatos"] },
  { nome: "Outros", itens: ["lembretes", "modelos"] },
];
const menuLateral = { editando: false, arrastando: null, desenhado: "" };

modulos.menu = {
  aoAplicarConfig() { if (!menuLateral.editando) desenharMenu(); },
  ligar() {
    const nav = $("#menu");
    // Organizando, clicar num item não troca de tela (a captura chega antes do clique do botão).
    nav.addEventListener("click", (e) => {
      if (menuLateral.editando && e.target.closest(".menu-item")) e.stopPropagation();
    }, true);
    nav.addEventListener("dragstart", (e) => {
      const item = e.target.closest(".menu-item");
      if (!menuLateral.editando || !item) return;
      menuLateral.arrastando = item;
      item.classList.add("menu-arrastando");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", item.dataset.view);
    });
    nav.addEventListener("dragover", (e) => {
      if (!menuLateral.arrastando) return;
      e.preventDefault();
      soltarPerto(e.target, e.clientY);
    });
    nav.addEventListener("drop", (e) => { if (menuLateral.arrastando) e.preventDefault(); });
    nav.addEventListener("dragend", () => {
      menuLateral.arrastando?.classList.remove("menu-arrastando");
      menuLateral.arrastando = null;
      guardarMenu();
    });
    nav.addEventListener("keydown", (e) => {
      const item = e.target.closest(".menu-item");
      if (!menuLateral.editando || !item || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
      e.preventDefault();
      moverComTeclado(item, e.key === "ArrowUp" ? -1 : 1);
    });
    nav.addEventListener("change", (e) => { if (e.target.matches(".menu-grupo-nome")) guardarMenu(); });
  },
};

Object.assign(acoes, {
  "menu-organizar": () => organizarMenu(!menuLateral.editando),
  "menu-concluir": () => organizarMenu(false),
  "menu-novo-grupo": novoGrupo,
  "menu-apagar-grupo": (alvo) => apagarGrupo(alvo.closest(".menu-grupo")),
  "menu-padrao": () => {
    mudarConfig({ menu: [] });
    desenharMenu();
  },
});

/* Os grupos salvos, conferidos com as telas que existem nesta versão. */
function gruposDoMenu() {
  const telas = botoesDoMenu();
  const salvos = estado.cfg.menu && estado.cfg.menu.length ? estado.cfg.menu : MENU_PADRAO;
  const usadas = new Set();
  const grupos = salvos.map((g) => ({
    nome: g.nome,
    itens: g.itens.filter((v) => telas.has(v) && !usadas.has(v) && usadas.add(v)),
  }));
  const faltando = [...telas.keys()].filter((v) => !usadas.has(v));
  if (faltando.length) {
    if (!grupos.length) grupos.push({ nome: "", itens: [] });
    grupos[grupos.length - 1].itens.push(...faltando);
  }
  return grupos;
}

/* As telas que entram nos grupos: todas do menu, menos o Início (fixo em cima). */
function botoesDoMenu() {
  return new Map($$("#menu .menu-item[data-view]").filter((b) => b.dataset.view !== "inicio")
    .map((b) => [b.dataset.view, b]));
}

function desenharMenu() {
  const grupos = gruposDoMenu();
  const chave = JSON.stringify([grupos, menuLateral.editando]);
  if (chave === menuLateral.desenhado) return; // nada mudou: não mexe no menu à toa
  menuLateral.desenhado = chave;

  const telas = botoesDoMenu();
  const nav = $("#menu");
  const html = document.documentElement;
  if (menuLateral.editando) html.dataset.menuEditando = "1"; else delete html.dataset.menuEditando;
  nav.classList.toggle("menu-editando", menuLateral.editando);
  $("#menu-organizar").setAttribute("aria-pressed", String(menuLateral.editando));

  const blocos = grupos.map((g) => {
    const grupo = Object.assign(document.createElement("div"), { className: "menu-grupo" });
    grupo.setAttribute("role", "group");
    grupo.append(tituloDoGrupo(g.nome));
    if (g.nome) grupo.setAttribute("aria-label", g.nome);
    for (const v of g.itens) {
      const b = telas.get(v);
      b.draggable = menuLateral.editando;
      grupo.append(b);
    }
    // Grupo sem nenhuma tela só aparece organizando (para dar onde soltar).
    grupo.hidden = !g.itens.length && !menuLateral.editando;
    return grupo;
  });
  const inicio = $('#menu .menu-item[data-view="inicio"]');
  const [topo, fim] = menuLateral.editando ? barrasDeEdicao() : [];
  nav.replaceChildren(...[topo, inicio, ...blocos, fim].filter(Boolean));
}

function tituloDoGrupo(nome) {
  const cab = Object.assign(document.createElement("div"), { className: "menu-grupo-titulo" });
  if (!menuLateral.editando) {
    if (nome) cab.append(Object.assign(document.createElement("span"), { textContent: nome }));
    return cab;
  }
  const campo = Object.assign(document.createElement("input"), {
    className: "menu-grupo-nome", type: "text", value: nome, maxLength: 30, placeholder: "Sem nome (só a linha)",
  });
  campo.setAttribute("aria-label", "Nome do grupo");
  const apagar = botaoIcone("menu-apagar-grupo", "i-lixeira", nome ? `Apagar o grupo ${nome}` : "Apagar este grupo");
  cab.append(campo, apagar);
  return cab;
}

/* Em cima, o Concluir (sempre à vista, mesmo com a janela baixa); embaixo, o resto. */
function barrasDeEdicao() {
  const botao = (acao, rotulo, classe = "btn btn-peq") => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: classe, textContent: rotulo });
    b.dataset.acao = acao;
    return b;
  };
  const topo = Object.assign(document.createElement("div"), { className: "menu-edicao menu-edicao-topo" });
  topo.append(texto("strong", "Organizando"), botao("menu-concluir", "Concluir", "btn btn-peq btn-primario"));
  topo.append(texto("p", "Arraste as telas (ou use as setas ↑ ↓) e troque os nomes dos grupos.", "dica"));
  const fim = Object.assign(document.createElement("div"), { className: "menu-edicao" });
  const novo = botao("menu-novo-grupo", "");
  novo.innerHTML = '<svg class="ic"><use href="#i-mais"/></svg><span>Novo grupo</span>';
  fim.append(novo, botao("menu-padrao", "Restaurar padrão"));
  return [topo, fim];
}

function organizarMenu(ligar) {
  if (!ligar && menuLateral.editando) guardarMenu();
  menuLateral.editando = ligar;
  desenharMenu();
  if (ligar) $("#menu .menu-grupo-nome")?.focus();
  else $("#menu-organizar").focus();
}

/* Organizando, a tela é a verdade: lê os grupos dela e salva. */
function lerMenuDaTela() {
  return $$("#menu .menu-grupo").map((g) => ({
    nome: (g.querySelector(".menu-grupo-nome")?.value || "").trim().replace(/\s+/g, " ").slice(0, 30),
    itens: [...g.querySelectorAll(".menu-item[data-view]")].map((b) => b.dataset.view),
  }));
}

function guardarMenu() {
  if (!menuLateral.editando) return;
  const grupos = lerMenuDaTela();
  menuLateral.desenhado = JSON.stringify([grupos, true]);
  if (JSON.stringify(grupos) !== JSON.stringify(gruposDoMenu())) mudarConfig({ menu: grupos });
}

/* Enquanto arrasta, o item já vai para o lugar: acima ou abaixo do item sob o mouse,
 * ou para o grupo (no começo, pelo título; no fim, pelo espaço vazio). */
function soltarPerto(alvo, y) {
  const item = menuLateral.arrastando;
  const outro = alvo.closest?.(".menu-grupo .menu-item");
  if (outro && outro !== item) {
    const caixa = outro.getBoundingClientRect();
    const depois = y > caixa.top + caixa.height / 2;
    if (depois ? outro.nextElementSibling !== item : outro.previousElementSibling !== item) {
      outro.parentNode.insertBefore(item, depois ? outro.nextElementSibling : outro);
    }
    return;
  }
  const grupo = alvo.closest?.(".menu-grupo");
  if (!grupo || outro) return;
  const titulo = grupo.querySelector(".menu-grupo-titulo");
  if (alvo.closest(".menu-grupo-titulo")) {
    if (titulo.nextElementSibling !== item) titulo.after(item);
  } else if (grupo.lastElementChild !== item) {
    grupo.append(item);
  }
}

function moverComTeclado(item, direcao) {
  // Na ordem da tela: título, itens, título, itens… Passar por um título troca de grupo.
  const todos = $$("#menu .menu-grupo .menu-item, #menu .menu-grupo-titulo");
  const vizinho = todos[todos.indexOf(item) + direcao];
  if (!vizinho) return;
  if (!vizinho.classList.contains("menu-grupo-titulo")) {
    if (direcao > 0) vizinho.after(item); else vizinho.before(item);
  } else if (direcao > 0) {
    vizinho.after(item); // desceu do fim de um grupo: entra no começo do de baixo
  } else {
    const anterior = vizinho.parentNode.previousElementSibling; // subiu do começo: fim do de cima
    if (!anterior?.classList.contains("menu-grupo")) return;
    anterior.append(item);
  }
  item.focus();
  guardarMenu();
}

function novoGrupo() {
  const grupos = lerMenuDaTela();
  grupos.push({ nome: "Novo grupo", itens: [] });
  mudarConfig({ menu: grupos });
  desenharMenu();
  const campos = $$("#menu .menu-grupo-nome");
  campos[campos.length - 1]?.select();
}

/* As telas do grupo apagado vão para o grupo de cima (ou o de baixo, se era o primeiro). */
function apagarGrupo(grupo) {
  const grupos = lerMenuDaTela();
  if (grupos.length <= 1) return mostrarToast("O menu precisa de pelo menos um grupo.");
  const i = $$("#menu .menu-grupo").indexOf(grupo);
  const [apagado] = grupos.splice(i, 1);
  grupos[Math.max(0, i - 1)].itens[i === 0 ? "unshift" : "push"](...apagado.itens);
  mudarConfig({ menu: grupos });
  desenharMenu();
}
