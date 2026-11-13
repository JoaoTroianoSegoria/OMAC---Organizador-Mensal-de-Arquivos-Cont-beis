/* OMAC — resumo do ano: faturamento das notas, extrato e ficha, mês a mês.
 *
 * O gráfico é de uma série só (faturamento), então não tem legenda: o título diz o que é.
 * Cada barra tem dica ao passar o mouse ou focar pelo teclado, e a tabela embaixo é a
 * versão em texto do mesmo gráfico. Mês sem nota lida fica sem barra, nunca com zero.
 */
"use strict";

const resumoAno = { ano: new Date().getFullYear(), dados: null };

modulos.resumo = {
  aoMostrar: carregarResumo,
  carregar: carregarResumo,
  ligar() {
    $("#rs-ano").addEventListener("change", (e) => {
      resumoAno.ano = Number(e.target.value);
      carregarResumo();
    });
  },
};

async function carregarResumo() {
  const r = await api().resumo_ano(resumoAno.ano);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  resumoAno.dados = r;
  desenharResumo();
}

const emReais = (centavos) => (centavos == null ? "" : real.format(centavos / 100));

function listaDeMeses(numeros) {
  const nomes = numeros.map((m) => MESES[m - 1].toLowerCase());
  return nomes.length > 1 ? `${nomes.slice(0, -1).join(", ")} e ${nomes[nomes.length - 1]}` : nomes[0];
}

function desenharResumo() {
  const r = resumoAno.dados;
  $("#rs-ano").replaceChildren(...r.anos.map((a) => new Option(String(a), String(a))));
  $("#rs-ano").value = String(r.ano);

  const faixa = $("#rs-sem-notas");
  if (!r.notas_lidas) {
    faixa.hidden = false;
    $("#rs-sem-notas-texto").textContent = "Escolha a pasta das notas em Notas fiscais para ver o faturamento.";
  } else if (r.sem_notas.length) {
    faixa.hidden = false;
    // Em 2026 as notas antes de agosto estão no formato antigo, que o OMAC não lê.
    const antigas = r.ano === 2026 && r.sem_notas.every((m) => m < 8) ? " As notas antes de agosto de 2026 estão no formato antigo." : "";
    $("#rs-sem-notas-texto").textContent =
      `Sem notas lidas em ${listaDeMeses(r.sem_notas)} de ${r.ano}. Esses meses ficam em branco.${antigas}`;
  } else {
    faixa.hidden = true;
  }

  $("#rs-total").textContent = emReais(r.faturamento_centavos) || "—";
  $("#rs-media").textContent = emReais(r.media_centavos) || "—";
  $("#rs-media-rotulo").textContent = r.meses_na_media
    ? `Média por mês (${r.meses_na_media} ${r.meses_na_media === 1 ? "mês" : "meses"})` : "Média por mês";
  $("#rs-melhor").textContent = r.melhor ? MESES[r.melhor - 1] : "—";
  $("#rs-pior").textContent = r.pior ? MESES[r.pior - 1] : "—";
  const c = r.comparacao;
  $("#rs-comparacao").textContent = c
    ? `${MESES[c.mes - 1]} faturou ${Math.abs(c.variacao).toLocaleString("pt-BR")}% ${c.variacao >= 0 ? "a mais" : "a menos"} que ${MESES[c.anterior - 1].toLowerCase()}.`
    : "";

  desenharBarras($("#rs-grafico"), r.meses, { ano: r.ano, destaque: r.melhor });

  $("#rs-corpo").replaceChildren(...r.meses.map((m) => {
    const tr = document.createElement("tr");
    const th = Object.assign(document.createElement("th"), { scope: "row", textContent: m.nome });
    tr.append(th,
      celula(m.notas ? String(m.notas) : "", "c-valor"),
      celula(emReais(m.faturamento_centavos), "c-valor"),
      celula(emReais(m.entradas_centavos), "c-valor"),
      celula(emReais(m.saidas_centavos), "c-valor"),
      celula(emReais(m.recebido_centavos), "c-valor"),
      celula(emReais(m.pendente_centavos), "c-valor"));
    return tr;
  }));
}

/* Barras de faturamento por mês. Também usado no cartão do Início, em tamanho menor. */
function desenharBarras(caixa, meses, { ano, destaque = null, compacto = false } = {}) {
  const hoje = new Date();
  const maior = Math.max(1, ...meses.map((m) => m.faturamento_centavos || 0));
  // Linhas de grade em valores redondos, discretas: o dado é a barra.
  const passo = Math.pow(10, Math.floor(Math.log10(maior / 100))) * 100;
  const topo = Math.ceil(maior / passo) * passo;
  const grade = compacto ? [] : [0.5, 1].map((f) => topo * f);

  const area = Object.assign(document.createElement("div"), { className: `rs-barras${compacto ? " rs-compacto" : ""}` });
  area.setAttribute("role", "list");
  for (const valor of grade) {
    const linha = Object.assign(document.createElement("div"), { className: "rs-grade" });
    // A base das barras fica acima do nome do mês (1.6rem), e o topo 1.6rem abaixo do alto da área.
    linha.style.bottom = `calc(1.6rem + (100% - 3.2rem) * ${valor / topo})`;
    linha.append(Object.assign(document.createElement("span"), { textContent: real.format(valor / 100).replace(",00", "") }));
    area.append(linha);
  }
  for (const m of meses) {
    const emAndamento = ano === hoje.getFullYear() && m.mes === hoje.getMonth() + 1;
    const col = Object.assign(document.createElement("div"), { className: "rs-coluna" });
    col.setAttribute("role", "listitem");
    const valor = m.faturamento_centavos;
    const texto = valor == null
      ? `${m.nome}: sem notas lidas`
      : `${m.nome}: ${real.format(valor / 100)}${emAndamento ? " (mês em andamento)" : ""}`;
    const barra = Object.assign(document.createElement("div"), { className: "rs-barra" });
    if (valor == null) {
      barra.classList.add("rs-vazia");
    } else {
      barra.style.height = `${Math.max(1.5, (valor / topo) * 100)}%`;
      if (emAndamento) barra.classList.add("rs-andamento");
      // Rótulo direto só no mês de destaque, para não encher o gráfico de números.
      if (!compacto && m.mes === destaque) {
        barra.append(Object.assign(document.createElement("span"), { className: "rs-rotulo", textContent: real.format(valor / 100) }));
      }
    }
    col.tabIndex = 0;
    col.setAttribute("aria-label", texto);
    col.dataset.dica = texto;
    col.append(Object.assign(document.createElement("div"), { className: "rs-trilho" }));
    col.firstChild.append(barra);
    col.append(Object.assign(document.createElement("span"), {
      className: "rs-mes", textContent: MESES[m.mes - 1].slice(0, 3),
    }));
    area.append(col);
  }
  const dica = Object.assign(document.createElement("div"), { className: "rs-dica", hidden: true });
  dica.setAttribute("role", "tooltip");
  area.append(dica);
  const mostrar = (col) => {
    dica.textContent = col.dataset.dica;
    dica.hidden = false;
    const a = area.getBoundingClientRect();
    const c = col.getBoundingClientRect();
    dica.style.left = `${Math.min(Math.max(0, c.left - a.left + c.width / 2 - dica.offsetWidth / 2), a.width - dica.offsetWidth)}px`;
  };
  area.addEventListener("mouseover", (e) => { const col = e.target.closest(".rs-coluna"); if (col) mostrar(col); });
  area.addEventListener("focusin", (e) => { const col = e.target.closest(".rs-coluna"); if (col) mostrar(col); });
  area.addEventListener("mouseleave", () => { dica.hidden = true; });
  area.addEventListener("focusout", () => { dica.hidden = true; });
  caixa.replaceChildren(area);
}
