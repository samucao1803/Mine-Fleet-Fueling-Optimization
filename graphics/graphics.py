#!/usr/bin/env python3
"""
Gera os graficos e a tabela-resumo do relatorio a partir do resultados.csv.

Uso:
    pip install pandas matplotlib numpy
    python gerar_graficos.py                         # le ./resultados.csv, grava em ./figuras
    python gerar_graficos.py caminho/resultados.csv pasta_saida

Saidas (PNG 300 dpi + PDF vetorial de cada figura):
    fig1_tempo_vs_binarias   tempo de solucao x variaveis binarias (saturacao)
    fig2_tempo_rotas_ciclos  efeito de rotas x ciclos no tempo (mesmos 40 caminhoes)
    fig3_resolvidas          instancias resolvidas ao otimo x limite de tempo, por escala
    fig4_gap_final           gap final das instancias que nao fecharam
    fig5_custo_escala        custo otimo do turno por escala
    fig6_custo_diario        custo diario nos perfis de mina x tamanho da frota
    fig7_tempo_perfis        tempo nos perfis de mina x nº de rotas e caminhoes
    fig8_normalizado         custo e paradas por caminhao-ciclo (compara escalas)
    fig9_custo_vs_paradas    custo do turno x nº de paradas para abastecer
    tabela_resumo.csv / tabela_resumo.md / tabela_resumo.tex
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

CSV = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("resultados.csv")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("figuras")
OUT.mkdir(parents=True, exist_ok=True)

LIMITE_S = 600.0          # limite de tempo do Gurobi usado nos experimentos
OTIMO, LIMITE = 2, 9      # codigos de status do Gurobi

# ----------------------------------------------------------------- estilo
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
GRID, SURFACE = "#e6e5e1", "#ffffff"
BLUE, ORANGE = "#2a78d6", "#eb6834"      # series 1 e 2 (paleta validada, ordem fixa)

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "text.color": INK, "axes.labelcolor": INK2, "axes.edgecolor": MUTED,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "legend.frameon": False,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
})

NOMES = {
    "pequena": "Pequena\n5×2×4", "media": "Média\n15×3×6", "grande": "Grande\n40×3×8",
    "realista": "Realista\n40×3×20", "realista_12r": "Realista 12 rotas\n40×12×20",
    "mina_media": "Mina média\n(perfil)", "mina_grande": "Mina grande\n(perfil)",
}
ORDEM = list(NOMES)
SINT = ["pequena", "media", "grande", "realista", "realista_12r"]
MINA = ["mina_media", "mina_grande"]


def curto(e):
    return NOMES[e].replace("\n", " ")


def salvar(fig, nome):
    fig.savefig(OUT / f"{nome}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{nome}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("ok:", nome)


def fmt_g(v, _=None):
    return f"{v:g}".replace(".", ",")


def vc(txt):
    """troca ponto decimal por virgula (pt-BR) em numeros ja formatados"""
    return txt.replace(".", ",")


def fmt_milhar(x, _=None):
    return f"{x:,.0f}".replace(",", ".")


# ----------------------------------------------------------------- dados
d = pd.read_csv(CSV)
d["familia"] = np.where(d.escala.isin(MINA), "Perfis de mina (K, R, C sorteados)", "Escalas sintéticas")
d["fechou"] = d.status == OTIMO
d["gap_pct"] = d.gap * 100
d["tempo_plot"] = d.tempo_s.clip(lower=1e-3)
assert d.verificada.all(), "ha linhas com verificada=False: resolva antes de usar os numeros"

COR = {"Escalas sintéticas": BLUE, "Perfis de mina (K, R, C sorteados)": ORANGE}

# =========================================================== FIG 1: saturacao
fig, ax = plt.subplots(figsize=(6.6, 4.2))
for fam, g in d.groupby("familia"):
    ok, lim = g[g.fechou], g[~g.fechou]
    ax.scatter(ok.n_bin, ok.tempo_plot, s=34, color=COR[fam], edgecolor=SURFACE,
               linewidth=0.8, zorder=3)
    ax.scatter(lim.n_bin, lim.tempo_plot, s=60, marker="X", color=COR[fam],
               edgecolor=SURFACE, linewidth=0.8, zorder=4)
ax.axhline(LIMITE_S, color=INK2, lw=1, ls="--", zorder=2)
ax.text(d.n_bin.min() * 1.05, LIMITE_S * 1.18, "limite de 600 s", color=INK2, fontsize=8)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Variáveis binárias (escala log)")
ax.set_ylabel("Tempo de solução, s (escala log)")
ax.yaxis.set_major_formatter(FuncFormatter(fmt_g))
ax.xaxis.set_major_formatter(FuncFormatter(fmt_milhar))
ax.set_title("Tempo de solução × tamanho do modelo")
h = [Line2D([], [], marker="o", ls="", color=BLUE, label="Escalas sintéticas"),
     Line2D([], [], marker="o", ls="", color=ORANGE, label="Perfis de mina"),
     Line2D([], [], marker="o", ls="", color=MUTED, label="ótimo (status 2)"),
     Line2D([], [], marker="X", ls="", color=MUTED, markersize=8, label="limite de tempo (status 9)")]
ax.legend(handles=h, loc="lower right", fontsize=8)
salvar(fig, "fig1_tempo_vs_binarias")

# =========================================== FIG 2: rotas x ciclos (K = 40)
esc2 = ["grande", "realista", "realista_12r"]
rot2 = {"grande": "3 rotas\n8 ciclos", "realista": "3 rotas\n20 ciclos", "realista_12r": "12 rotas\n20 ciclos"}
fig, ax = plt.subplots(figsize=(5.4, 4.2))
rng = np.random.default_rng(0)
for i, e in enumerate(esc2):
    g = d[d.escala == e]
    med = g.tempo_s.median()
    ax.hlines(med, i - 0.28, i + 0.28, color=INK, lw=2, zorder=4)
    x = i + rng.uniform(-0.17, 0.17, len(g))
    for fechou, m, s in [(True, "o", 36), (False, "X", 64)]:
        gg = g[g.fechou == fechou]
        xx = x[np.where(g.fechou.values == fechou)[0]]
        ax.scatter(xx, gg.tempo_plot, marker=m, s=s, color=BLUE,
                   edgecolor=SURFACE, linewidth=0.8, zorder=3)
    lbl = f"mediana ≥ {med:.0f} s" if med >= LIMITE_S else (f"mediana {med:.0f} s" if med >= 10 else vc(f"mediana {med:.1f} s"))
    ax.text(i + 0.32, med, lbl, va="center", fontsize=8, color=INK2)
ax.axhline(LIMITE_S, color=INK2, lw=1, ls="--")
ax.text(-0.45, LIMITE_S * 1.15, "limite de 600 s", fontsize=8, color=INK2)
ax.set_yscale("log"); ax.set_xlim(-0.5, 2.95)
ax.set_xticks(range(3)); ax.set_xticklabels([rot2[e] for e in esc2])
ax.set_ylabel("Tempo de solução, s (escala log)")
ax.yaxis.set_major_formatter(FuncFormatter(fmt_g))
ax.set_title("Mesma frota (40 caminhões): rotas × ciclos")
ax.grid(axis="x", visible=False)
ax.legend(handles=[Line2D([], [], marker="o", ls="", color=MUTED, label="ótimo"),
                   Line2D([], [], marker="X", ls="", color=MUTED, markersize=8, label="limite de tempo")],
          loc="lower right", fontsize=8)
salvar(fig, "fig2_tempo_rotas_ciclos")

# ======================================================= FIG 3: resolvidas
cont = d.groupby("escala").fechou.agg(["sum", "count"]).reindex(ORDEM)
cont["nao"] = cont["count"] - cont["sum"]
fig, ax = plt.subplots(figsize=(6.4, 3.6))
y = np.arange(len(ORDEM))[::-1]
ax.barh(y, cont["sum"], color=BLUE, height=0.62, label="ótimo (status 2)", edgecolor=SURFACE, linewidth=1.5)
ax.barh(y, cont["nao"], left=cont["sum"], color=INK2, height=0.62,
        label="limite de 600 s (status 9)", edgecolor=SURFACE, linewidth=1.5)
for yi, (_, r) in zip(y, cont.iterrows()):
    ax.text(10.25, yi, f"{int(r['sum'])}/{int(r['count'])}", va="center", fontsize=8.5, color=INK)
ax.set_yticks(y); ax.set_yticklabels([curto(e) for e in ORDEM], fontsize=8.5)
ax.set_xlim(0, 11); ax.set_xticks(range(0, 11, 2))
ax.set_xlabel("Instâncias (10 seeds por escala)")
ax.set_title("Instâncias resolvidas ao ótimo")
ax.grid(axis="y", visible=False)
ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.18), ncol=2, fontsize=8)
salvar(fig, "fig3_resolvidas")

# ========================================================= FIG 4: gap final
nf = d[~d.fechou].copy()
nf["rot"] = nf.apply(lambda r: f"{curto(r.escala)} · seed {int(r.seed)}", axis=1)
nf = nf.sort_values("gap_pct")
fig, ax = plt.subplots(figsize=(6.4, 3.4))
cores = [ORANGE if e in MINA else BLUE for e in nf.escala]
ax.barh(nf.rot, nf.gap_pct, color=cores, height=0.62)
for yi, v in enumerate(nf.gap_pct):
    ax.text(v + 0.015, yi, f"{v:.2f}%".replace(".", ","), va="center", fontsize=8.5)
ax.set_xlim(0, nf.gap_pct.max() * 1.18)
ax.xaxis.set_major_formatter(FuncFormatter(fmt_g))
ax.set_xlabel("Gap de otimalidade ao final dos 600 s (%)")
ax.set_title("Gap final das instâncias que não fecharam")
ax.grid(axis="y", visible=False)
ax.tick_params(axis="y", labelsize=8)
salvar(fig, "fig4_gap_final")

# ================================================== FIG 5: custo por escala
fig, ax = plt.subplots(figsize=(6.6, 4.0))
rng = np.random.default_rng(1)
for i, e in enumerate(ORDEM):
    g = d[d.escala == e]
    cor = ORANGE if e in MINA else BLUE
    c = g.custo_otimo.where(g.custo_otimo > 0)
    ax.scatter(i + rng.uniform(-0.15, 0.15, len(g)), c, s=26, color=cor, alpha=0.75,
               edgecolor=SURFACE, linewidth=0.6, zorder=3)
    ax.hlines(g.custo_otimo.mean(), i - 0.28, i + 0.28, color=INK, lw=2, zorder=4)
    zeros = int((g.custo_otimo == 0).sum())
    if zeros:
        ax.text(i, 3e2, f"{zeros} seeds\ncom custo 0", ha="center", fontsize=7.5, color=INK2)
ax.set_yscale("log"); ax.set_ylim(2e2, 1e6)
ax.set_xticks(range(len(ORDEM)))
ax.set_xticklabels([NOMES[e].replace("Realista 12 rotas", "Realista\n12 rotas") for e in ORDEM], fontsize=7.5)
ax.set_ylabel("Custo ótimo do turno, R$ (escala log)")
ax.yaxis.set_major_formatter(FuncFormatter(fmt_milhar))
ax.grid(axis="x", visible=False)
ax.set_title("Custo do turno por escala (traço = média)")
salvar(fig, "fig5_custo_escala")

# ================================================= FIG 6: custo diario minas
m = d[d.escala.isin(MINA)].copy()
fig, ax = plt.subplots(figsize=(6.4, 4.0))
for e, mk in [("mina_media", "o"), ("mina_grande", "s")]:
    g = m[m.escala == e]
    ax.scatter(g.K, g.custo_dia, s=48, marker=mk, color=ORANGE,
               edgecolor=SURFACE, linewidth=0.8, zorder=3,
               label=curto(e))
for _, r in m.iterrows():
    if not r.fechou:
        ax.scatter(r.K, r.custo_dia, s=130, facecolor="none", edgecolor=INK, linewidth=1.1, zorder=4)
ax.set_xlabel("Caminhões na frota (K)")
ax.set_ylabel("Custo diário, R$ (turno × turnos/dia)")
ax.yaxis.set_major_formatter(FuncFormatter(fmt_milhar))
ax.set_title("Custo diário nos perfis de mina")
h, l = ax.get_legend_handles_labels()
h.append(Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor=INK, markersize=10))
l.append("contorno preto = não fechou em 600 s")
ax.legend(h, l, loc="upper left", fontsize=8)
salvar(fig, "fig6_custo_diario")

# ============================================ FIG 7: tempo nos perfis (R, K)
fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.8), sharey=True)
for ax, col, rot in [(axs[0], "R", "Rotas (R)"), (axs[1], "K", "Caminhões (K)")]:
    for e, mk in [("mina_media", "o"), ("mina_grande", "s")]:
        g = m[m.escala == e]
        ax.scatter(g[col][g.fechou], g.tempo_plot[g.fechou], s=36, marker=mk, color=ORANGE,
                   edgecolor=SURFACE, linewidth=0.8, zorder=3)
        ax.scatter(g[col][~g.fechou], g.tempo_plot[~g.fechou], s=64, marker="X",
                   color=ORANGE, edgecolor=SURFACE, linewidth=0.8, zorder=4)
    ax.axhline(LIMITE_S, color=INK2, lw=1, ls="--")
    ax.set_yscale("log"); ax.set_xlabel(rot)
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_g))
axs[0].set_ylabel("Tempo de solução, s (escala log)")
axs[0].text(axs[0].get_xlim()[0] + 0.4, LIMITE_S * 1.15, "limite 600 s", fontsize=8, color=INK2)
fig.suptitle("Perfis de mina: tempo de solução × rotas e × caminhões", x=0.07, ha="left", fontsize=10, fontweight="bold")
axs[1].legend(handles=[Line2D([], [], marker="o", ls="", color=MUTED, label="mina média"),
                       Line2D([], [], marker="s", ls="", color=MUTED, label="mina grande"),
                       Line2D([], [], marker="X", ls="", color=MUTED, markersize=8, label="limite de tempo")],
              loc="lower right", fontsize=8)
salvar(fig, "fig7_tempo_perfis")


# ============================ FIG 8: custo e paradas normalizados por caminhao-ciclo
d["custo_kc"] = d.custo_otimo / (d.K * d.C)
d["paradas_kc"] = d.n_paradas / (d.K * d.C)
fig, axs = plt.subplots(1, 2, figsize=(8.0, 3.9))
rng = np.random.default_rng(2)
for ax, col, ylab, ttl in [(axs[0], "custo_kc", "R$ por caminhão por ciclo", "Custo normalizado"),
                           (axs[1], "paradas_kc", "paradas por caminhão por ciclo", "Paradas normalizadas")]:
    for i, e in enumerate(ORDEM):
        g = d[d.escala == e]
        cor = ORANGE if e in MINA else BLUE
        ax.scatter(i + rng.uniform(-0.15, 0.15, len(g)), g[col], s=24, color=cor, alpha=0.75,
                   edgecolor=SURFACE, linewidth=0.6, zorder=3)
        ax.hlines(g[col].mean(), i - 0.3, i + 0.3, color=INK, lw=2, zorder=4)
    ax.set_xticks(range(len(ORDEM)))
    ax.set_xticklabels(["Peq.", "Média", "Grande", "Real.", "Real.\n12 r.", "Mina\nmédia", "Mina\ngrande"], fontsize=7.5)
    ax.set_ylabel(ylab); ax.set_title(ttl)
    ax.grid(axis="x", visible=False)
    ax.set_ylim(bottom=0)
axs[0].yaxis.set_major_formatter(FuncFormatter(fmt_milhar))
axs[1].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.2f}".replace(".", ",")))
fig.text(0.01, -0.02, "Traço preto = média das 10 seeds. Cada ponto é uma instância.", fontsize=8, color=INK2)
fig.tight_layout()
salvar(fig, "fig8_normalizado")

# ============================ FIG 9: custo x paradas
x = d[d.n_paradas > 0]
rho = x[["custo_otimo", "n_paradas"]].corr(method="spearman").iloc[0, 1]
c_med = (x.custo_otimo / x.n_paradas).median()
fig, ax = plt.subplots(figsize=(5.6, 4.2))
for fam, g in x.groupby("familia"):
    ax.scatter(g.n_paradas, g.custo_otimo, s=34, color=COR[fam], edgecolor=SURFACE, linewidth=0.8,
               zorder=3, label="Perfis de mina" if "mina" in fam else "Escalas sintéticas")
xs = np.array([0, x.n_paradas.max() * 1.05])
ax.plot(xs, c_med * xs, color=INK2, ls="--", lw=1, zorder=2,
        label=f"mediana: R$ {fmt_milhar(c_med)} por parada")
ax.set_xlim(0, xs[1]); ax.set_ylim(bottom=0)
ax.set_xlabel("Paradas para abastecer no turno")
ax.set_ylabel("Custo ótimo do turno, R$")
ax.yaxis.set_major_formatter(FuncFormatter(fmt_milhar))
ax.set_title(f"Custo × número de paradas (Spearman {rho:.2f})".replace(".", ","))
ax.legend(loc="upper left", fontsize=8)
salvar(fig, "fig9_custo_vs_paradas")

# ============================================================ tabela-resumo
def lim_str(v, atingiu):
    return vc(f"≥ {v:.1f}" if atingiu else f"{v:.2f}")


linhas = []
for e in ORDEM:
    g = d[d.escala == e]
    r0 = g.iloc[0]
    n_lim = int((~g.fechou).sum())
    tmed = g.tempo_s.mean()
    tmd = g.tempo_s.median()
    linhas.append({
        "Escala": curto(e),
        "Caminhões (K)": f"{g.K.min()}–{g.K.max()}" if g.K.nunique() > 1 else f"{int(r0.K)}",
        "Rotas (R)": f"{g.R.min()}–{g.R.max()}" if g.R.nunique() > 1 else f"{int(r0.R)}",
        "Ciclos (C)": f"{g.C.min()}–{g.C.max()}" if g.C.nunique() > 1 else f"{int(r0.C)}",
        "Binárias (média)": fmt_milhar(g.n_bin.mean()),
        "Ótimas": f"{int(g.fechou.sum())}/{len(g)}",
        "Tempo médio (s)": lim_str(tmed, n_lim > 0),
        "Tempo mediano (s)": f"≥ {LIMITE_S:.0f}" if tmd >= LIMITE_S - 1 else vc(f"{tmd:.2f}"),
        "Tempo máx (s)": f"≥ {g.tempo_s.max():.0f}" if n_lim else vc(f"{g.tempo_s.max():.2f}"),
        "Gap máx (%)": vc(f"{g.gap_pct.max():.2f}") if n_lim else "≤ 0,01",
        "Custo médio (R$)": fmt_milhar(g.custo_otimo.mean()),
        "Custo/cam./ciclo (R$)": fmt_milhar(g.custo_kc.mean()),
        "Paradas/cam./ciclo": vc(f"{g.paradas_kc.mean():.3f}"),
        "Desvio (R$)": fmt_milhar(g.custo_otimo.std()),
    })
tab = pd.DataFrame(linhas)
tab.to_csv(OUT / "tabela_resumo.csv", index=False, encoding="utf-8-sig")
try:
    (OUT / "tabela_resumo.md").write_text(tab.to_markdown(index=False), encoding="utf-8")
except ImportError:      # 'tabulate' nao instalado: monta a tabela manualmente
    cab = "| " + " | ".join(tab.columns) + " |\n|" + "---|" * len(tab.columns) + "\n"
    corpo = "".join("| " + " | ".join(map(str, r)) + " |\n" for r in tab.values)
    (OUT / "tabela_resumo.md").write_text(cab + corpo, encoding="utf-8")
(OUT / "tabela_resumo.tex").write_text(
    tab.to_latex(index=False, escape=True, column_format="l" + "r" * (len(tab.columns) - 1)),
    encoding="utf-8")
print("ok: tabela_resumo (.csv .md .tex)")
print(tab.to_string(index=False))