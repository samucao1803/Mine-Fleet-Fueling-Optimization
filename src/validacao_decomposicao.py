import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd
from scipy import sparse as sp
from scipy.optimize import Bounds, LinearConstraint, milp

PASTA_INST = "instances"
PASTA_RES = "results"
SAIDA = os.path.join(PASTA_RES, "validation", "validacao_decomposicao.csv")
SAIDA_SENS = os.path.join(PASTA_RES, "validation", "validacao_sensibilidade.csv")
ARQ_SENS = ["sensibilidade_custo_hora.csv", "sens_mina_media.csv", "sens_mina_grande.csv"]
TURNO_H = 12.0


def carregar(escala, seed):
    with open(os.path.join(PASTA_INST, f"inst_{escala}_{seed}.json")) as f:
        return json.load(f)


def sequencia(inst, k, r):
    """Consumo, fila e preco em cada chegada do caminhao k na rota r."""
    rota, cam = inst["rotas"][r], inst["caminhoes"][k]
    cons = [cam["c_carr"] * p["t_carr_h"] + cam["c_vazio"] * p["t_vazio_h"] for p in rota]
    n, total = len(rota), len(rota) * inst["C"]
    return ([cons[i % n] for i in range(total)],
            [rota[i % n]["fila_min"] for i in range(total)],
            [rota[i % n]["preco"] for i in range(total)])


def resolver_par(inst, k, r, custo_hora):
    """Abastecimento otimo do caminhao k na rota r: (custo, {chegada: litros})."""
    cam = inst["caminhoes"][k]
    cons, fila, preco = sequencia(inst, k, r)
    N = len(cons)
    ini, res, tanque = cam["nivel_inicial"], cam["reserva"], cam["tanque"]
    D = np.cumsum(cons)
    if D[-1] - (ini - res) <= 1e-9:
        return 0.0, {}

    m = N - 1                                  
    pi = np.array(preco[:m]) + custo_hora / 60 / inst["bombeio_L_por_min"]
    F = custo_hora / 60 * np.array(fila[:m])
    custo = np.r_[F, pi]                        
    M = tanque - res
    lin, col, val, lo, hi = [], [], [], [], []
    n_lin = 0
    for j in range(m):                          
        lin += [n_lin, n_lin]; col += [m + j, j]; val += [1, -M]
        lo.append(-np.inf); hi.append(0); n_lin += 1
    for i in range(N):                          
        for j in range(i):
            lin.append(n_lin); col.append(m + j); val.append(1)
        lo.append(res - ini + D[i]); hi.append(tanque - ini + D[i]); n_lin += 1
    for i in range(m):                          
        for j in range(i + 1):
            lin.append(n_lin); col.append(m + j); val.append(1)
        lo.append(-np.inf); hi.append(tanque - ini + D[i]); n_lin += 1

    A = sp.csr_matrix((val, (lin, col)), shape=(n_lin, 2 * m))
    s = milp(custo, constraints=LinearConstraint(A, lo, hi),
             integrality=np.r_[np.ones(m), np.zeros(m)],
             bounds=Bounds(np.zeros(2 * m), np.r_[np.ones(m), np.full(m, M)]),
             options={"mip_rel_gap": 1e-7, "time_limit": 60})
    if s.x is None:
        return np.inf, None
    return float(custo @ s.x), {j: float(s.x[m + j]) for j in range(m) if s.x[j] > 0.5}


def designar(custos, demanda):
    """Designacao de custo minimo com demanda minima por rota."""
    K, R = custos.shape
    A = sp.lil_matrix((K + R, K * R))
    for k in range(K):
        for r in range(R):
            A[k, k * R + r] = 1
            A[K + r, k * R + r] = 1
    lo = np.r_[np.ones(K), demanda]
    hi = np.r_[np.ones(K), np.full(R, np.inf)]
    c = custos.ravel()
    s = milp(c, constraints=LinearConstraint(A.tocsr(), lo, hi), integrality=np.ones(K * R),
             bounds=Bounds(0, 1), options={"mip_rel_gap": 0})
    return float(c @ s.x), s.x.reshape(K, R).argmax(1)


def resolver(inst, custo_hora):
    K, R = inst["K"], inst["R"]
    custos, planos = np.zeros((K, R)), {}
    for k in range(K):
        for r in range(R):
            custos[k, r], planos[k, r] = resolver_par(inst, k, r, custo_hora)
    z, rota = designar(custos, inst["demanda"])
    return z, rota, planos


def regra_simples(inst, k, r, custo_hora):
    """Para so quando o proximo trecho violaria a reserva e compra so o necessario."""
    cam = inst["caminhoes"][k]
    cons, fila, preco = sequencia(inst, k, r)
    nivel, resta, custo = cam["nivel_inicial"], sum(cons), 0.0
    for i in range(len(cons)):
        nivel -= cons[i]
        resta -= cons[i]
        if i < len(cons) - 1 and nivel - cons[i + 1] < cam["reserva"] - 1e-9:
            q = min(cam["tanque"] - nivel, max(0.0, resta - (nivel - cam["reserva"])))
            custo += (preco[i] + custo_hora / 60 / inst["bombeio_L_por_min"]) * q + custo_hora / 60 * fila[i]
            nivel += q
    return custo


def analisar(tarefa):
    escala, seed, ch = tarefa
    inst = carregar(escala, seed)
    t0 = time.time()
    z, rota, planos = resolver(inst, ch)
    tempo = time.time() - t0
    K, R, C = inst["K"], inst["R"], inst["C"]
    ciclo = np.array([sum(p["t_carr_h"] + p["t_vazio_h"] for p in rt) for rt in inst["rotas"]])
    dist = np.array([x["dist_km"] for x in inst["rotas_info"]])
    horas = ciclo[rota] * C
    consumo = fila = litros = 0.0
    finais, iniciais = [], []
    for k in range(K):
        cam, r = inst["caminhoes"][k], rota[k]
        cons, filas, _ = sequencia(inst, k, r)
        plano = planos[k, r]
        consumo += sum(cons)
        litros += sum(plano.values())
        fila += sum(ch / 60 * filas[j] for j in plano)
        final = cam["nivel_inicial"] - sum(cons) + sum(plano.values())
        finais.append((final - cam["reserva"]) / cam["tanque"])
        iniciais.append((cam["nivel_inicial"] - cam["reserva"]) / cam["tanque"])
    return {
        "escala": escala, "seed": seed, "custo_hora": ch, "K": K, "R": R, "C_": C, "z": z,
        "t_sub": tempo, "t_assign": 0.0, "stops": sum(len(planos[k, rota[k]]) for k in range(K)),
        "litros": litros, "consumo": consumo, "fila": fila,
        "frac_consumo_comprado": litros / consumo if consumo else 0.0,
        "finfrac": float(np.mean(finais)), "inifrac": float(np.mean(iniciais)),
        "h_max": float(horas.max()), "frac_gt12": float((horas > TURNO_H).mean()),
        "rotas_gt12": float((ciclo * C > TURNO_H).mean()),
        "top_share": float(np.bincount(rota, minlength=R).max() / K),
        "km_sol": float(np.median(2 * dist[rota])), "km_rotas": float((2 * dist).mean()),
        "g_opt": float(sum(regra_simples(inst, k, rota[k], ch) for k in range(K))),
    }


def resumo():
    base = pd.read_csv(os.path.join(PASTA_RES, "resultados.csv"))
    d = base.merge(pd.read_csv(SAIDA), on=["escala", "seed"])
    d["dif_pct"] = 100 * (d.custo_otimo - d.z) / d.z.where(d.z > 0)
    d["tempo_dec"] = d.t_sub + d.t_assign
    pi = 6.70 + 1500 / 60 / 600
    d["repor"] = d.consumo * pi + d.fila
    linhas = []
    for e, x in d.groupby("escala", sort=False):
        linhas.append({
            "escala": e,
            "dif_max_%": x.dif_pct.abs().max(),
            "tempo_max_s": x.tempo_dec.max(),
            "comprado_%": 100 * x.frac_consumo_comprado.mean(),
            "repor/custo": x.repor.sum() / x.z.sum(),
            "maior_rota_%": 100 * x.top_share.mean(),
            "rotas>12h_%": 100 * x.rotas_gt12.mean(),
            "caminhoes>12h_%": 100 * x.frac_gt12.mean(),
            "horas_max": x.h_max.max(),
            "ganho_sobre_regra_%": 100 * (x.g_opt.sum() - x.z.sum()) / x.g_opt.sum() if x.g_opt.sum() else 0.0,
        })
    pd.set_option("display.width", 220, "display.max_columns", 20)
    print(pd.DataFrame(linhas).round(2).to_string(index=False))
    print(f"\nganho total sobre a regra simples: {100 * (d.g_opt.sum() - d.z.sum()) / d.g_opt.sum():.2f}%")


def analisar_aberta(a):
    escala, seed, ch, gurobi, gap, plano_base = a
    z, _, _ = resolver(carregar(escala, seed), ch)
    return {"escala": escala, "seed": seed, "custo_hora": ch, "custo_gurobi": gurobi, "gap_gurobi": gap,
            "custo_decomposicao": z, "diferenca_pct": 100 * (gurobi - z) / z,
            "arrependimento_informado_pct": 100 * (plano_base - gurobi) / gurobi,
            "arrependimento_real_pct": 100 * (plano_base - z) / z}


def executar(funcao, tarefas, saida):
    linhas = []
    with Pool(os.cpu_count()) as p:
        for i, r in enumerate(p.imap_unordered(funcao, tarefas), 1):
            linhas.append(r)
            pd.DataFrame(linhas).to_csv(saida, index=False)
            print(f"[{i}/{len(tarefas)}] {r['escala']} seed={r['seed']}", flush=True)


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "resumo"
    if modo == "principal":
        d = pd.read_csv(os.path.join(PASTA_RES, "resultados.csv"))
        executar(analisar, [(e, int(s), 1500.0) for e, s in zip(d.escala, d.seed)], SAIDA)
        resumo()
    elif modo == "sensibilidade":
        S = pd.concat([pd.read_csv(os.path.join(PASTA_RES, f)) for f in ARQ_SENS])
        S = S[S.status != 2]
        executar(analisar_aberta, [(r.escala, int(r.seed), float(r.custo_hora), r.custo_otimo, r.gap,
                                    r.custo_plano_base) for r in S.itertuples()], SAIDA_SENS)
    elif modo == "resumo":
        resumo()
    else:
        sys.exit("modo invalido: use principal, sensibilidade ou resumo")
