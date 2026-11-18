#!/usr/bin/env python3

import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

PASTA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("figuras_sens")
OUT.mkdir(parents=True, exist_ok=True)
ARQS = {"realista": "sensibilidade_custo_hora.csv", "mina_media": "sens_mina_media.csv",
        "mina_grande": "sens_mina_grande.csv"}
NOME = {"realista": "Realista (40×3×20)", "mina_media": "Mina média (perfil)",
        "mina_grande": "Mina grande (perfil)"}
VALORES = [1500.0, 5000.0, 15000.0]
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
BLUE, ORANGE, TEAL = "#2a78d6", "#eb6834", "#4a9d8f"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "text.color": INK,
    "axes.labelcolor": INK2, "axes.edgecolor": MUTED, "xtick.color": INK2, "ytick.color": INK2,
    "axes.facecolor": "white", "figure.facecolor": "white",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left"})


def vc(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",")


def mil(v, _=None):
    return f"{v:,.0f}".replace(",", ".")


def salvar(fig, nome):
    fig.savefig(OUT / f"{nome}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{nome}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("ok:", nome)


# ---------------------------------------------------------------- dados
d = pd.concat([pd.read_csv(PASTA / f) for f in ARQS.values()], ignore_index=True)
assert d.verificada.all(), "ha solucao nao verificada"
assert d.confere_base.dropna().all(), "caso-base nao confere com resultados.csv"
base = d[d.e_base].set_index(["escala", "seed"])
idx = pd.MultiIndex.from_frame(d[["escala", "seed"]])
for c in ["custo_otimo", "n_paradas", "litros_por_parada", "litros_total"]:
    d[c + "_rel"] = d[c].values / base[c].reindex(idx).values
d["fila_pct"] = 100 * d.custo_fila / d.custo_otimo
d["comb_pct"] = 100 * d.custo_combustivel / d.custo_otimo
d["bomb_pct"] = 100 * d.custo_bombeio / d.custo_otimo
d["aberta"] = d.status != 2
d["arr"] = d.arrependimento_pct.clip(lower=0)      # ruido numerico (~1e-9) vira 0
escalas = [e for e in ARQS if e in set(d.escala)]


def paineis(n=3, w=3.6, h=3.4):
    fig, axs = plt.subplots(1, n, figsize=(w * n, h), sharey=True)
    return fig, np.atleast_1d(axs)


# ---- sens1: composicao do custo
fig, axs = paineis(len(escalas), 3.4, 3.6)
for ax, e in zip(axs, escalas):
    g = d[d.escala == e].groupby("custo_hora")[["comb_pct", "bomb_pct", "fila_pct"]].median()
    x = np.arange(len(VALORES))
    b = np.zeros(len(VALORES))
    for col, cor, rot in [("comb_pct", BLUE, "Combustível"), ("bomb_pct", TEAL, "Bombeio (tempo)"),
                          ("fila_pct", ORANGE, "Fila (tempo)")]:
        v = g.loc[VALORES, col].values
        ax.bar(x, v, bottom=b, color=cor, width=0.62, label=rot)
        if col != "bomb_pct":
            for xi, vi, bi in zip(x, v, b):
                ax.text(xi, bi + vi / 2, vc(vi, 0) + "%", ha="center", va="center", color="white",
                        fontsize=8, fontweight="bold")
        b += v
    ax.set_xticks(x, [mil(v) for v in VALORES])
    ax.set_xlabel("Custo da hora parada (R$/h)")
    ax.set_title(NOME[e])
    ax.grid(axis="x", visible=False)
axs[0].set_ylabel("Participação no custo ótimo (%, mediana)")
axs[-1].legend(loc="upper center", bbox_to_anchor=(-0.9, -0.22), ncol=3)
fig.suptitle("Quanto maior o custo da hora parada, maior a parcela do custo de tempo",
             x=0.01, ha="left", fontsize=11, fontweight="bold", y=1.02)
salvar(fig, "sens1_composicao_custo")

# ---- sens2: custo relativo ao caso-base
fig, axs = paineis(len(escalas))
for ax, e in zip(axs, escalas):
    s = d[d.escala == e]
    for sd, gs in s.groupby("seed"):
        gs = gs.sort_values("custo_hora")
        ax.plot(gs.custo_hora, gs.custo_otimo_rel, color=MUTED, lw=0.8, alpha=0.5)
    m = s.groupby("custo_hora").custo_otimo_rel.median()
    ax.plot(m.index, m.values, color=BLUE, lw=2.2, marker="o", label="Mediana")
    ab = s[s.aberta]
    ax.scatter(ab.custo_hora, ab.custo_otimo_rel, facecolor="white", edgecolor=ORANGE, s=34, zorder=5,
               lw=1.4, label="Não fechou (limite de tempo)")
    ax.set_xscale("log")
    ax.set_xticks(VALORES, [mil(v) for v in VALORES])
    ax.minorticks_off()
    ax.set_xlabel("Custo da hora parada (R$/h)")
    ax.set_title(NOME[e])
axs[0].set_ylabel("Custo ótimo ÷ custo com R$ 1.500/h")
axs[0].legend(loc="upper left")
salvar(fig, "sens2_custo_relativo")

# ---- sens3: paradas e litros por parada
fig, axs = plt.subplots(1, 2, figsize=(8.2, 3.6))
cores = {"realista": BLUE, "mina_media": ORANGE, "mina_grande": TEAL}
for e in escalas:
    s = d[d.escala == e]
    for ax, col in zip(axs, ["n_paradas_rel", "litros_por_parada_rel"]):
        m = s.groupby("custo_hora")[col].median()
        ax.plot(range(3), m.loc[VALORES].values, marker="o", color=cores[e], lw=2, label=NOME[e])
for ax, t in zip(axs, ["Nº de paradas (relativo ao caso-base)", "Litros por parada (relativo ao caso-base)"]):
    ax.set_xticks(range(3), [mil(v) for v in VALORES])
    ax.set_xlabel("Custo da hora parada (R$/h)")
    ax.set_title(t)
    ax.axhline(1, color=MUTED, lw=0.8, ls="--")
axs[0].legend(loc="lower left")
salvar(fig, "sens3_paradas_litros")

# ---- sens4: arrependimento
fig, axs = paineis(len(escalas))
rng = np.random.default_rng(0)
for ax, e in zip(axs, escalas):
    s = d[(d.escala == e) & (~d.e_base)]
    for i, v in enumerate(VALORES[1:]):
        t = s[s.custo_hora == v]
        xs = i + rng.uniform(-0.12, 0.12, len(t))
        f = t[~t.aberta]; a = t[t.aberta]
        ax.scatter(xs[(~t.aberta).values], f.arr, color=BLUE, s=30, zorder=4)
        ax.scatter(xs[t.aberta.values], a.arr, facecolor="white", edgecolor=ORANGE, s=34, lw=1.4, zorder=5)
        ax.hlines(t.arr.median(), i - 0.25, i + 0.25, color=INK, lw=2, zorder=6)
    ax.set_xticks(range(2), [mil(v) for v in VALORES[1:]])
    ax.set_xlim(-0.5, 1.5)
    ax.set_xlabel("Custo da hora parada (R$/h)")
    ax.set_title(NOME[e])
axs[0].set_ylabel("Custo extra de manter o plano de R$ 1.500/h (%)")
axs[-1].legend(handles=[Line2D([], [], marker="o", ls="", color=BLUE, label="Instância (ótimo)"),
                        Line2D([], [], marker="o", ls="", mfc="white", mec=ORANGE, mew=1.4,
                               label="Não fechou (valor mínimo)"),
                        Line2D([], [], color=INK, lw=2, label="Mediana")], loc="upper left")
salvar(fig, "sens4_arrependimento")

# ---- sens5: tempo de solucao
fig, axs = paineis(len(escalas))
for ax, e in zip(axs, escalas):
    s = d[d.escala == e]
    lim = s.tempo_s.max() if s.aberta.any() else None
    for sd, gs in s.groupby("seed"):
        gs = gs.sort_values("custo_hora")
        ax.plot(gs.custo_hora, gs.tempo_s, color=MUTED, lw=0.8, alpha=0.5)
    m = s.groupby("custo_hora").tempo_s.median()
    ax.plot(m.index, m.values, color=BLUE, lw=2.2, marker="o", label="Mediana")
    ab = s[s.aberta]
    ax.scatter(ab.custo_hora, ab.tempo_s, facecolor="white", edgecolor=ORANGE, s=34, lw=1.4, zorder=5,
               label="Atingiu o limite")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xticks(VALORES, [mil(v) for v in VALORES]); ax.minorticks_off()
    ax.set_xlabel("Custo da hora parada (R$/h)")
    ax.set_title(NOME[e])
axs[0].set_ylabel("Tempo de solução (s)")
axs[0].legend(loc="upper left")
salvar(fig, "sens5_tempo")

# ---- tabela
L = []
for e in escalas:
    for v in VALORES:
        t = d[(d.escala == e) & (d.custo_hora == v)]
        L.append({"Escala": NOME[e], "R$/h": mil(v), "n": len(t), "Ótimas": f"{(t.status == 2).sum()}/{len(t)}",
                  "Tempo mediano (s)": vc(t.tempo_s.median(), 1), "Gap máx (%)": vc(100 * t.gap.max(), 2),
                  "Custo ÷ base": vc(t.custo_otimo_rel.median(), 2), "Fila (%)": vc(t.fila_pct.median(), 0),
                  "Paradas (med.)": vc(t.n_paradas.median(), 1),
                  "L/parada ÷ base": vc(t.litros_por_parada_rel.median(), 2),
                  "Extra plano base (% med.)": "–" if v == VALORES[0] else vc(t.arr.median(), 2),
                  "Extra plano base (% máx.)": "–" if v == VALORES[0] else vc(t.arr.max(), 2)})
T = pd.DataFrame(L)
T.to_csv(OUT / "tabela_sensibilidade.csv", index=False, encoding="utf-8-sig")
cab = list(T.columns)
md = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
md += ["| " + " | ".join(str(x) for x in r) + " |" for r in T.values]
(OUT / "tabela_sensibilidade.md").write_text("\n".join(md), encoding="utf-8")
T.to_latex(OUT / "tabela_sensibilidade.tex", index=False, escape=True)
print(T.to_string(index=False))
