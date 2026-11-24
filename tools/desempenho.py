"""Mede o desempenho da tela do OMAC nos 4 modos (visual × reduzir animações), CPU 4× mais lenta.

    python tools/desempenho.py .            # a tela de omac/ui (arquivos separados)
    python tools/desempenho.py . build/tela # a tela junta, como vai no .exe (tools/juntar_tela.py)

Precisa do Playwright (pip install playwright && playwright install chromium). Roteiro igual
nos 4 modos: abrir, 16 trocas de tela, rolagem do Início e das Configurações, 6 cliques no olho.
No GitHub Actions a tabela também sai nas anotações da execução, para comparar versões.
Referência (1.10.2, PC de desenvolvimento): bonito 5,7% de quadros travados e 1874 ms no total;
otimizado 0% e 1252 ms.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

RAIZ = Path(sys.argv[1]).resolve()
TELA = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else RAIZ / "omac" / "ui"
sys.path.insert(0, str(RAIZ))
PONTE = """
window.pywebview = { api: new Proxy({}, { get: (_, nome) =>
  (...args) => window._omac_chamar(nome, JSON.stringify(args)).then(JSON.parse) }) };
"""
# Grava o intervalo entre quadros enquanto a página roda.
QUADROS = """
window._q = []; (function f(t){ if (window._ult) window._q.push(t - window._ult); window._ult = t; requestAnimationFrame(f); })();
"""
MODOS = [("bonito", False), ("bonito", True), ("otimizado", False), ("otimizado", True)]
VIEWS = ["relatorio", "resumo", "atendimentos", "tratamentos", "contatos", "lembretes", "config", "inicio"]


def main():
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_CONFIG_HOME"] = tmp
        os.environ["APPDATA"] = tmp
        from omac.app import Api
        from tests.fabrica import criar_pasta_exemplo

        pasta = criar_pasta_exemplo(Path(tmp) / "NFS-e 2026")
        api = Api()
        api._cfg.update({"pasta_notas": str(pasta), "pasta_extratos": str(pasta / "Extratos"),
                         "assistente_nome": "Exemplo", "lembrete_fechamento_dia": 0, "abrir_em": "inicio"})
        hoje = date.today()
        for i in range(25):
            api.atendimentos_salvar({"nome": f"Paciente Exemplo {i}", "data": hoje.isoformat(), "valor": "180,00",
                                     "tratamento": "Limpeza", "forma": "pix_pj"})
        for i in range(12):
            api.contatos_salvar({"nome": f"Orto Exemplo {i}", "orto": True, "valor": "250,00", "situacao": "ativo"})
        with api._contas() as d:
            d["ultima_abertura"] = hoje.isoformat()

        def chamar(metodo, args):
            return json.dumps(getattr(api, metodo)(*json.loads(args)))

        resultados = []
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            for visual, reduzir in MODOS:
                api._cfg.update({"visual": visual, "reduzir_movimento": reduzir, "tema": "claro"})
                pagina = nav.new_page(viewport={"width": 1366, "height": 768})
                cdp = pagina.context.new_cdp_session(pagina)
                cdp.send("Performance.enable")
                cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
                pagina.expose_function("_omac_chamar", chamar)
                pagina.add_init_script(PONTE + QUADROS)
                t0 = time.perf_counter()
                pagina.goto((TELA / "index.html").as_uri())
                pagina.wait_for_selector(".ini-cartao")
                abrir = (time.perf_counter() - t0) * 1000
                pagina.wait_for_timeout(1500)
                antes = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
                pagina.evaluate("window._q = []")

                trocas = []
                for _ in range(2):
                    for v in VIEWS:
                        t = pagina.evaluate(f"""async () => {{
                          const t0 = performance.now();
                          document.querySelector('.menu-item[data-view="{v}"]').click();
                          await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                          return performance.now() - t0; }}""")
                        trocas.append(t)
                        pagina.wait_for_timeout(350)
                for v in ("inicio", "config"):
                    pagina.click(f'.menu-item[data-view="{v}"]')
                    pagina.wait_for_timeout(400)
                    for _ in range(12):
                        pagina.mouse.move(800, 400)
                        pagina.mouse.wheel(0, 300)
                        pagina.wait_for_timeout(60)
                    for _ in range(12):
                        pagina.mouse.wheel(0, -300)
                        pagina.wait_for_timeout(60)
                pagina.click('.menu-item[data-view="atendimentos"]')
                pagina.wait_for_timeout(400)
                olho = []
                for _ in range(6):
                    olho.append(pagina.evaluate("""async () => { const t0 = performance.now();
                      document.querySelector('#view-atendimentos .olho').click();
                      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                      return performance.now() - t0; }"""))
                depois = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
                q = pagina.evaluate("window._q")
                q = sorted(q)
                d = {k: (depois[k] - antes[k]) * 1000 for k in ("ScriptDuration", "LayoutDuration",
                                                                 "RecalcStyleDuration", "TaskDuration")}
                resultados.append({
                    "modo": f"{visual}{' + reduzir' if reduzir else ''}", "abrir": abrir,
                    "troca_media": statistics.mean(trocas), "troca_pior": max(trocas),
                    "quadro_mediano": statistics.median(q), "quadro_p95": q[int(len(q) * .95)],
                    "quadros_lentos": sum(x > 50 for x in q) / len(q) * 100,
                    "olho": statistics.mean(olho), **d,
                })
                pagina.close()
            nav.close()

    linhas = [f"{'modo':22}{'abrir':>7}{'troca méd':>10}{'pior':>8}{'quadro':>8}{'p95':>7}{'>50ms':>7}{'olho':>7}"
          f"{'script':>8}{'layout':>8}{'estilo':>8}{'total':>8}"]
    for r in resultados:
        linhas.append(f"{r['modo']:22}{r['abrir']:7.0f}{r['troca_media']:10.0f}{r['troca_pior']:8.0f}{r['quadro_mediano']:8.1f}"
              f"{r['quadro_p95']:7.0f}{r['quadros_lentos']:6.1f}%{r['olho']:7.0f}{r['ScriptDuration']:8.0f}"
              f"{r['LayoutDuration']:8.0f}{r['RecalcStyleDuration']:8.0f}{r['TaskDuration']:8.0f}")
    print("\n".join(linhas))
    if os.environ.get("GITHUB_ACTIONS"):
        resumo = " | ".join(f"{r['modo']}: {r['quadros_lentos']:.1f}% travados, {r['TaskDuration']:.0f} ms, "
                            f"abrir {r['abrir']:.0f} ms" for r in resultados)
        print(f"::notice title=Desempenho da tela::{resumo}")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write("### Desempenho da tela (CPU 4× mais lenta)\n\n```\n" + "\n".join(linhas) + "\n```\n")


main()
