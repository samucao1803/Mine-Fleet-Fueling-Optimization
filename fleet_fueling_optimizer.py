"""
Abastecimento de Frota em Mina - modelo v3 generalizado (esqueleto funcional)

Estrutura:
  A. gerar_instancia()      -> dados sinteticos reprodutiveis (seed fixa)
  B. construir_e_resolver() -> modelo Gurobi com posicoes t (x, y, q, v)
  C. verificar_solucao()    -> checagem independente da solucao
  D. rodar_experimentos()   -> loop escalas x seeds -> resultados.csv
  E. tabela_resumo()        -> tabela do relatorio (media/desvio por escala)

Uso:
  python abastecimento_mina.py teste          # uma instancia pequena
  python abastecimento_mina.py experimentos   # 3 escalas x N seeds
"""
import csv
import json
import statistics
import sys
import time

import numpy as np

# ---------------------------------------------------------------------------
# PARAMETROS DE CALIBRACAO  (TODO: ajustar com os dados reais / gerente)
# ---------------------------------------------------------------------------
PARAMS = {
    "postos_por_rota": (3, 4),        # TODO decisao 2
    "km_trecho": (30.0, 70.0),        # TODO decisao 1 (exemplo usa 30-70 km)
    "preco_litro": (5.50, 6.20),      # R$/L
    "fila_min": (5.0, 25.0),          # min
    "tanque_L": (3000.0, 5000.0),
    "cons_carregado": (3.0, 4.5),     # L/km
    "cons_vazio": (1.8, 2.5),         # L/km
    "reserva_pct": (0.10, 0.15),
    "nivel_inicial_pct": (0.25, 0.40),  # TODO decisao 3
    "demanda_por_rota": (1, 3),
    "custo_hora_parado": 1500.0,      # R$/h  TODO confirmar origem
    "bombeio_L_por_min": 400.0,       # TODO calibrar com litros/evento
}

# escala: (caminhoes, rotas, ciclos, demanda_minima_total_maxima)
ESCALAS = {
    "pequena": (5, 2, 4, 4),
    "media": (15, 3, 6, 9),
    "grande": (40, 3, 8, 12),
}
SEEDS = range(1, 11)          # TODO decisao 4
TEMPO_LIMITE_S = 600          # TODO decisao 4


# ---------------------------------------------------------------------------
# A. GERADOR DE INSTANCIAS
# ---------------------------------------------------------------------------
def gerar_instancia(K, R, C, seed, demanda_max_total=None, params=PARAMS):
    rng = np.random.default_rng(seed)
    u = lambda faixa: float(rng.uniform(*faixa))

    # rotas e postos (trecho p = percurso feito para chegar ao posto p)
    rotas = []
    for r in range(R):
        n = int(rng.integers(params["postos_por_rota"][0], params["postos_por_rota"][1] + 1))
        n_vazio = n // 2          # primeiros trechos vazios, demais carregados
        postos = []
        for p in range(n):
            postos.append({
                "km": u(params["km_trecho"]),
                "estado": "vazio" if p < n_vazio else "carregado",
                "preco": u(params["preco_litro"]),
                "fila_min": u(params["fila_min"]),
            })
        rotas.append(postos)

    # demanda minima por rota (soma <= demanda_max_total e <= K)
    lo, hi = params["demanda_por_rota"]
    demanda = [int(rng.integers(lo, hi + 1)) for _ in range(R)]
    teto = min(K, demanda_max_total if demanda_max_total else K)
    while sum(demanda) > teto and max(demanda) > 1:
        i = int(rng.choice([r for r in range(R) if demanda[r] > 1]))
        demanda[i] -= 1

    # caminhoes (garante viabilidade: todo trecho cabe em tanque - reserva)
    def cons_trecho(cam, p_dict):
        c = cam["c_carr"] if p_dict["estado"] == "carregado" else cam["c_vazio"]
        return p_dict["km"] * c

    caminhoes = []
    for k in range(K):
        for _ in range(1000):
            tanque = u(params["tanque_L"])
            cam = {
                "tanque": tanque,
                "c_carr": u(params["cons_carregado"]),
                "c_vazio": u(params["cons_vazio"]),
                "reserva": u(params["reserva_pct"]) * tanque,
            }
            maior = max(cons_trecho(cam, p) for rt in rotas for p in rt)
            if maior <= tanque - cam["reserva"]:
                break
        else:
            raise RuntimeError("nao foi possivel gerar caminhao viavel; revise as faixas")
        # nivel inicial deve cobrir ao menos o 1o trecho de qualquer rota + reserva
        primeiro = max(cons_trecho(cam, rt[0]) for rt in rotas)
        cam["nivel_inicial"] = min(
            tanque, max(u(params["nivel_inicial_pct"]) * tanque, cam["reserva"] + primeiro)
        )
        caminhoes.append(cam)

    return {
        "K": K, "R": R, "C": C, "seed": seed,
        "rotas": rotas, "caminhoes": caminhoes, "demanda": demanda,
        "custo_hora": params["custo_hora_parado"],
        "bombeio_L_por_min": params["bombeio_L_por_min"],
    }


def derivados(inst):
    """pi[r][p] (R$/L com bombeio), F[r][p] (R$/parada pela fila), cons[k][r][p] (L)."""
    ch, bomb = inst["custo_hora"], inst["bombeio_L_por_min"]
    pi = [[p["preco"] + ch / 60.0 / bomb for p in rt] for rt in inst["rotas"]]
    F = [[ch / 60.0 * p["fila_min"] for p in rt] for rt in inst["rotas"]]
    cons = []
    for cam in inst["caminhoes"]:
        cons.append([
            [p["km"] * (cam["c_carr"] if p["estado"] == "carregado" else cam["c_vazio"])
             for p in rt] for rt in inst["rotas"]
        ])
    return pi, F, cons


# ---------------------------------------------------------------------------
# B. MODELO GUROBI (v3)
# ---------------------------------------------------------------------------
def construir_e_resolver(inst, tempo_limite=TEMPO_LIMITE_S, gap=1e-4, log=False):
    import gurobipy as gp
    from gurobipy import GRB

    K, R, C = inst["K"], inst["R"], inst["C"]
    n_postos = [len(rt) for rt in inst["rotas"]]
    P = max(n_postos)                  # posicoes por ciclo
    T = C * P + 1                      # ultima posicao = chegada final
    pi, F, cons = derivados(inst)

    def p_of(t):                       # indice do posto na posicao t (1..T)
        return (t - 1) % P

    def c_of(k, r, t):                 # consumo do trecho que chega em t (0 se posicao vazia)
        p = p_of(t)
        return cons[k][r][p] if p < n_postos[r] else 0.0

    m = gp.Model("abastecimento_v3")
    m.Params.OutputFlag = 1 if log else 0
    m.Params.TimeLimit = tempo_limite
    m.Params.MIPGap = gap
    m.Params.Threads = 1
    m.Params.Seed = 0

    cam = inst["caminhoes"]
    U = [c["tanque"] - c["reserva"] for c in cam]

    x = m.addVars(K, R, vtype=GRB.BINARY, name="x")
    # y, q apenas onde existe posto: t = 1..T-1 e p(t) < n_postos[r]
    idx = [(k, t, r) for k in range(K) for r in range(R)
           for t in range(1, T) if p_of(t) < n_postos[r]]
    y = m.addVars(idx, vtype=GRB.BINARY, name="y")
    q = m.addVars(idx, lb=0.0, name="q")
    for (k, t, r) in idx:
        q[k, t, r].UB = U[k]
    v = m.addVars(K, range(1, T + 1), name="v")
    for k in range(K):
        for t in range(1, T + 1):
            v[k, t].LB = cam[k]["reserva"]     # (2) reserva
            v[k, t].UB = cam[k]["tanque"]      # (3) capacidade

    # objetivo
    m.setObjective(
        gp.quicksum(pi[r][p_of(t)] * q[k, t, r] + F[r][p_of(t)] * y[k, t, r]
                    for (k, t, r) in idx),
        GRB.MINIMIZE)

    for k in range(K):
        # (1) balanco
        m.addConstr(v[k, 1] == cam[k]["nivel_inicial"]
                    - gp.quicksum(c_of(k, r, 1) * x[k, r] for r in range(R)))
        for t in range(2, T + 1):
            compra = gp.quicksum(q[k, t - 1, r] for r in range(R) if (k, t - 1, r) in q)
            m.addConstr(v[k, t] == v[k, t - 1] + compra
                        - gp.quicksum(c_of(k, r, t) * x[k, r] for r in range(R)))
        # (5) nao enche alem do tanque
        for t in range(1, T):
            compra = gp.quicksum(q[k, t, r] for r in range(R) if (k, t, r) in q)
            m.addConstr(v[k, t] + compra <= cam[k]["tanque"])
        # (6) alocacao unica
        m.addConstr(x.sum(k, "*") == 1)
    for (k, t, r) in idx:
        m.addConstr(q[k, t, r] <= U[k] * y[k, t, r])   # (4)
        m.addConstr(y[k, t, r] <= x[k, r])             # (8)
    for r in range(R):
        m.addConstr(x.sum("*", r) >= inst["demanda"][r])  # (7)

    t0 = time.time()
    m.optimize()
    tempo = time.time() - t0

    res = {
        "status": int(m.Status), "tempo_s": tempo,
        "n_bin": int(m.NumBinVars), "n_cont": int(m.NumVars - m.NumBinVars),
        "n_restr": int(m.NumConstrs),
        "custo": None, "gap": None, "sol": None,
    }
    if m.SolCount > 0:
        res["custo"] = float(m.ObjVal)
        res["gap"] = float(m.MIPGap)
        res["sol"] = {
            "rota": [max(range(R), key=lambda r: x[k, r].X) for k in range(K)],
            "paradas": {f"{k},{t},{r}": float(q[k, t, r].X)
                        for (k, t, r) in idx if y[k, t, r].X > 0.5},
        }
        res["n_paradas"] = len(res["sol"]["paradas"])
    return res


# ---------------------------------------------------------------------------
# C. VERIFICADOR INDEPENDENTE (nao usa o Gurobi)
# ---------------------------------------------------------------------------
def verificar_solucao(inst, res, tol=1e-4):
    """Reconstroi niveis e custo a partir de (rota, paradas) e confere restricoes."""
    if res["sol"] is None:
        return False, "sem solucao"
    K, C = inst["K"], inst["C"]
    P = max(len(rt) for rt in inst["rotas"])
    T = C * P + 1
    pi, F, cons = derivados(inst)
    rota = res["sol"]["rota"]
    paradas = {tuple(map(int, kk.split(","))): lit for kk, lit in res["sol"]["paradas"].items()}

    # demanda e alocacao unica (ja implicita em 'rota')
    for r in range(inst["R"]):
        if sum(1 for k in range(K) if rota[k] == r) < inst["demanda"][r]:
            return False, f"demanda da rota {r} nao atendida"

    custo = 0.0
    for k in range(K):
        r, cam = rota[k], inst["caminhoes"][k]
        nivel = cam["nivel_inicial"]
        for t in range(1, T + 1):
            p = (t - 1) % P
            nivel -= cons[k][r][p] if p < len(inst["rotas"][r]) else 0.0
            if nivel < cam["reserva"] - tol:
                return False, f"caminhao {k} abaixo da reserva em t={t}"
            if nivel > cam["tanque"] + tol:
                return False, f"caminhao {k} acima do tanque em t={t}"
            lit = paradas.get((k, t, r), 0.0)
            if lit:
                if nivel + lit > cam["tanque"] + tol:
                    return False, f"caminhao {k} enche alem do tanque em t={t}"
                nivel += lit
                custo += pi[r][p] * lit + F[r][p]
    if abs(custo - res["custo"]) > 1e-3 * max(1.0, res["custo"]):
        return False, f"custo difere: {custo:.2f} vs {res['custo']:.2f}"
    return True, "ok"


# ---------------------------------------------------------------------------
# D. EXPERIMENTOS  /  E. TABELA
# ---------------------------------------------------------------------------
CAMPOS = ["escala", "seed", "K", "R", "C", "T", "n_bin", "n_cont", "n_restr",
          "status", "tempo_s", "custo_otimo", "gap", "n_paradas", "verificada"]


def rodar_experimentos(saida="resultados.csv"):
    with open(saida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for nome, (K, R, C, dmax) in ESCALAS.items():
            for seed in SEEDS:
                inst = gerar_instancia(K, R, C, seed, demanda_max_total=dmax)
                with open(f"inst_{nome}_{seed}.json", "w") as fi:
                    json.dump(inst, fi)
                res = construir_e_resolver(inst)
                ok, msg = verificar_solucao(inst, res)
                P = max(len(rt) for rt in inst["rotas"])
                w.writerow({
                    "escala": nome, "seed": seed, "K": K, "R": R, "C": C,
                    "T": C * P + 1, "n_bin": res["n_bin"], "n_cont": res["n_cont"],
                    "n_restr": res["n_restr"], "status": res["status"],
                    "tempo_s": round(res["tempo_s"], 3),
                    "custo_otimo": res["custo"], "gap": res["gap"],
                    "n_paradas": res.get("n_paradas"), "verificada": ok,
                })
                f.flush()
                print(f"{nome} seed={seed}: custo={res['custo']} "
                      f"tempo={res['tempo_s']:.2f}s verificada={ok} ({msg})")


def tabela_resumo(entrada="resultados.csv"):
    linhas = list(csv.DictReader(open(entrada)))
    print("| Instancia | KxRxC | Bin./Cont. | Restr. | Tempo medio (s) | Desvio | Custo medio (R$) | Gap max |")
    print("|---|---|---|---|---|---|---|---|")
    for nome in ESCALAS:
        L = [l for l in linhas if l["escala"] == nome and l["custo_otimo"]]
        if not L:
            continue
        tempos = [float(l["tempo_s"]) for l in L]
        custos = [float(l["custo_otimo"]) for l in L]
        gaps = [float(l["gap"]) for l in L]
        dp = statistics.stdev(tempos) if len(tempos) > 1 else 0.0
        print(f"| {nome} | {L[0]['K']}x{L[0]['R']}x{L[0]['C']} "
              f"| {statistics.mean(int(l['n_bin']) for l in L):.0f}/"
              f"{statistics.mean(int(l['n_cont']) for l in L):.0f} "
              f"| {statistics.mean(int(l['n_restr']) for l in L):.0f} "
              f"| {statistics.mean(tempos):.2f} | {dp:.2f} "
              f"| {statistics.mean(custos):,.2f} | {max(gaps):.4%} |")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "teste"
    if modo == "teste":
        inst = gerar_instancia(5, 2, 4, seed=1, demanda_max_total=4)
        r = construir_e_resolver(inst, log=False)
        print({k: v for k, v in r.items() if k != "sol"})
        print("verificacao:", verificar_solucao(inst, r))
    elif modo == "experimentos":
        rodar_experimentos()
        tabela_resumo()