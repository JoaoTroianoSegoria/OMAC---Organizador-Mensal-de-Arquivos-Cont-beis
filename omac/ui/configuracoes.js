/* OMAC — Configurações com mais de um campo: como ler as notas (formato do nome do arquivo e
 * descrição esperada) e as mensagens da nota com [variáveis].
 *
 * Diferente dos outros campos das Configurações, estes só valem ao clicar em Salvar: o formato
 * muda a leitura de todas as notas, e uma mensagem pela metade não pode ir para o WhatsApp.
 */
"use strict";

const ajustes = {
  editado: { leitura: false, nota: false, notas: false }, // a pessoa mexeu e ainda não salvou
  modelos: null, // {nota: {modelo, padrao, variaveis}, notas: {...}}
  timers: {},
};

modulos.configuracoes = {
  ligar() {
    $("#form-cfg-leitura").addEventListener("submit", (e) => { e.preventDefault(); salvarLeitura(); });
    $("#cfg-formato").addEventListener("input", () => { ajustes.editado.leitura = true; depois("teste", testarFormato); });
    $("#cfg-servico").addEventListener("input", () => { ajustes.editado.leitura = true; });
    for (const form of $$(".cfg-mensagem")) {
      const tipo = form.dataset.tipo;
      form.addEventListener("submit", (e) => { e.preventDefault(); salvarMensagem(tipo); });
      $(`#cfg-msg-${tipo}`).addEventListener("input", () => {
        ajustes.editado[tipo] = true;
        depois(tipo, () => mostrarPrevia(tipo));
      });
    }
  },
  aoAplicarConfig(cfg) {
    if (!ajustes.editado.leitura) preencherLeitura(cfg);
  },
};

Object.assign(acoes, {
  "cfg-variavel": (alvo) => inserirVariavel(alvo),
  "cfg-leitura-padrao": leituraPadrao,
  "cfg-msg-padrao": (alvo) => mensagemPadrao(alvo.dataset.tipo),
});

function depois(chave, fn, ms = 350) {
  clearTimeout(ajustes.timers[chave]);
  ajustes.timers[chave] = setTimeout(fn, ms);
}

async function carregarConfiguracoes() {
  if (!ajustes.editado.leitura) preencherLeitura(estado.cfg);
  testarFormato();
  const r = await api().mensagens_modelos();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarModelosDeMensagem(r);
}

/* Põe a variável onde está o cursor do campo (ou no fim), como se tivesse sido digitada. */
function inserirVariavel(botao) {
  const campo = $(`#${botao.closest("[data-alvo]").dataset.alvo}`);
  const texto = `[${botao.dataset.variavel}]`;
  const inicio = campo.selectionStart ?? campo.value.length;
  const fim = campo.selectionEnd ?? campo.value.length;
  campo.setRangeText(texto, inicio, fim, "end");
  campo.focus();
  campo.dispatchEvent(new Event("input", { bubbles: true }));
}

/* ---------- Como ler as notas ---------- */

function preencherLeitura(cfg) {
  if (!cfg) return;
  $("#cfg-formato").value = cfg.formato_arquivo;
  $("#cfg-servico").value = cfg.servico_esperado;
}

async function testarFormato() {
  const caixa = $("#cfg-formato-teste");
  const r = await api().notas_testar_formato($("#cfg-formato").value);
  caixa.className = "cfg-teste";
  if (r.erro) {
    caixa.classList.add("cfg-teste-erro");
    caixa.replaceChildren(r.erro);
    return;
  }
  if (r.sem_pasta) {
    caixa.replaceChildren("Escolha a pasta das notas para testar o formato.");
    return;
  }
  if (!r.total) {
    caixa.replaceChildren("A pasta das notas não tem nenhum PDF para testar.");
    return;
  }
  const tudo = r.entendidos === r.total;
  caixa.classList.add(tudo ? "cfg-teste-ok" : r.entendidos ? "cfg-teste-aviso" : "cfg-teste-erro");
  const partes = [texto("strong", `Entendi ${r.entendidos} de ${plural(r.total, "arquivo", "arquivos")} da pasta.`)];
  if (r.exemplos.length) {
    const ul = Object.assign(document.createElement("ul"), { className: "cfg-teste-lista" });
    for (const e of r.exemplos) ul.append(texto("li", `${e.arquivo} → nº ${e.numero}, ${e.nome}`));
    partes.push(ul);
  }
  if (r.fora.length) {
    partes.push(texto("span", r.entendidos ? "Fora do formato (o OMAC usa o nome que está dentro da nota):" : "Nenhum arquivo bate com o formato. Exemplos da pasta:"));
    const ul = Object.assign(document.createElement("ul"), { className: "cfg-teste-lista" });
    for (const nome of r.fora) ul.append(texto("li", nome));
    partes.push(ul);
  }
  caixa.replaceChildren(...partes);
}

async function salvarLeitura() {
  const r = await api().notas_salvar_regras($("#cfg-formato").value, $("#cfg-servico").value);
  if (r.erro) {
    $("#cfg-leitura-erro").textContent = r.erro;
    $("#cfg-leitura-erro").hidden = false;
    return;
  }
  $("#cfg-leitura-erro").hidden = true;
  ajustes.editado.leitura = false;
  estado.cfg = r.config;
  aplicarConfig();
  testarFormato();
  mostrarToast("Salvo. As notas vão ser lidas de novo com o formato novo.");
}

async function leituraPadrao() {
  const r = await api().notas_regras_padrao();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  $("#cfg-formato").value = r.formato;
  $("#cfg-servico").value = r.servico;
  ajustes.editado.leitura = true;
  testarFormato();
  mostrarToast("Voltou ao padrão. Clique em Salvar para valer.");
}

/* ---------- Mensagens com variáveis ---------- */

function aplicarModelosDeMensagem(r) {
  ajustes.modelos = r;
  for (const tipo of ["nota", "notas"]) {
    const m = r[tipo];
    $(`#cfg-msg-${tipo}-variaveis`).replaceChildren(...m.variaveis.map((v) => {
      const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq", textContent: `[${v.nome}]` });
      b.dataset.acao = "cfg-variavel";
      b.dataset.variavel = v.nome;
      b.title = v.descricao;
      return b;
    }));
    if (!ajustes.editado[tipo]) $(`#cfg-msg-${tipo}`).value = m.modelo;
    mostrarPrevia(tipo);
  }
}

async function mostrarPrevia(tipo) {
  const r = await api().mensagens_previa(tipo, $(`#cfg-msg-${tipo}`).value);
  if (r.erro) return;
  $(`#cfg-msg-${tipo}-previa`).textContent = r.texto;
  const erro = $(`#cfg-msg-${tipo}-erro`);
  erro.hidden = !r.desconhecidas.length;
  erro.textContent = r.desconhecidas.length
    ? `Não conheço ${r.desconhecidas.map((v) => `[${v}]`).join(", ")}. Use os botões para pôr as variáveis certas.` : "";
}

async function salvarMensagem(tipo) {
  const r = await api().mensagens_salvar(tipo, $(`#cfg-msg-${tipo}`).value);
  if (r.erro) {
    $(`#cfg-msg-${tipo}-erro`).textContent = r.erro;
    $(`#cfg-msg-${tipo}-erro`).hidden = false;
    return;
  }
  ajustes.editado[tipo] = false;
  estado.cfg = r.config;
  aplicarModelosDeMensagem(r);
  mostrarToast(tipo === "nota" ? "Mensagem de uma nota salva." : "Mensagem de várias notas salva.");
}

async function mensagemPadrao(tipo) {
  const r = await api().mensagens_padrao(tipo);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  ajustes.editado[tipo] = false;
  estado.cfg = r.config;
  aplicarModelosDeMensagem(r);
  mostrarToast("A mensagem voltou ao texto padrão.");
}
