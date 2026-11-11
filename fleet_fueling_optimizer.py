"""
Abastecimento de Frota em Mina - Script

"""
import csv
import json
import statistics
import sys
import time

import numpy as np


# PARAMETROS DE CALIBRACAO (faixas dos dados reais providos pela Hexagon Mining)

PARAMS = {
    "postos_por_rota": (1, 2),
    "dist_km": (1.0, 13.318),           # distancia da origem -> destino 
    "vel_carregado_kmh": (8.0, 35.0),   # velocidade media carregado por rota
    "vel_vazio_kmh": (12.0, 45.0),      # velocidade media vazio por rota
    "preco_litro": (6.70, 6.70),        # preco unico em R$/L
    "fila_min": (6.0, 25.0),            # fila fixa por posto
    "tanque_L": (500.0, 5300.0),        # capacidade do tanque
    "cons_carregado_Lh": (107.5, 592.0),   # consumo carregado L/H
    "cons_vazio_Lh": (80.6, 289.0),        # consumo vazio L/H
    "ruido_porte": 0.10,                # Desvio do consumo em relacao ao porte do tanque
    "reserva_pct": (0.10, 0.15),        # Reserva de capacidade minima do tanque
    "nivel_inicial_pct": (0.15, 0.90),  # Nivel inicial do tanque
    "demanda_por_rota": (1, 3),         # Demanda de caminhões por rota
    "custo_hora_parado": 1500.0,        # Custo da hora parada R$/h estimado.
    "bombeio_L_por_min": 600.0, # Taxa de bombeio L/mim estimado
}

# escala no formato: caminhoes, rotas, ciclos, demanda_minima_total_maxima
ESCALAS = {
    "pequena": (5, 2, 4, 4),
    "media": (15, 3, 6, 9),
    "grande": (40, 3, 8, 12),
    "realista": (40, 3, 20, 12),
    "realista_12r": (40, 12, 20, 12),
}

# perfis de mina, com K, R, C e turnos/dia sorteados nas faixas 
PERFIS = {
    "mina_media": {"K": (10, 30), "R": (3, 8), "C": (8, 20), "turnos": (2, 3)},
    "mina_grande": {"K": (30, 100), "R": (8, 20), "C": (7, 20), "turnos": (2, 3)},
}
SEEDS = range(1, 11)          #  10 seeds por escala
TEMPO_LIMITE_S = 600          #  600 s por rodada


def amostrar_perfil(nome, seed):
    """Sorteia (K, R, C, turnos, demanda_max_total) nas faixas do perfil de mina."""
    f = PERFIS[nome]
    rng = np.random.default_rng([seed, list(PERFIS).index(nome) + 1])
    K, R, C, turnos = (int(rng.integers(f[c][0], f[c][1] + 1)) for c in ("K", "R", "C", "turnos"))
    return K, R, C, turnos, max(R, K // 2)      # demanda total ate metade da frota 


def casos(seeds=SEEDS):
    """Todos os casos de teste: (nome, seed, K, R, C, demanda_max, turnos_dia)."""
    for nome, (K, R, C, dmax) in ESCALAS.items():
        for s in seeds:
            yield nome, s, K, R, C, dmax, None
    for nome in PERFIS:
        for s in seeds:
            K, R, C, turnos, dmax = amostrar_perfil(nome, s)
            yield nome, s, K, R, C, dmax, turnos



# GERADOR DE INSTANCIAS

def gerar_instancia(K, R, C, seed, demanda_max_total=None, params=PARAMS):
    rng = np.random.default_rng(seed)
    u = lambda faixa: float(rng.uniform(*faixa))

    # calcula as rotas (Ida e volta)
    rotas, rotas_info = [], []
    for r in range(R):
        n = int(rng.integers(params["postos_por_rota"][0], params["postos_por_rota"][1] + 1))
        d = u(params["dist_km"])
        vc, vv = u(params["vel_carregado_kmh"]), u(params["vel_vazio_kmh"])
        L = 2.0 * d
        a = float(rng.uniform(0.0, L))                  
        gaps = rng.dirichlet([4.0] * n) * L             

        def carr_ate(x):                                
            m, rem = divmod(x, L)
            return m * d + min(rem, d)

        pos = [a]
        for p in range(1, n):
            pos.append(pos[-1] + gaps[p])
        trechos = [(pos[-1], a + L)] + [(pos[p - 1], pos[p]) for p in range(1, n)]

        postos = []
        for (ini, fim) in trechos:
            km_c = carr_ate(fim) - carr_ate(ini)
            km_v = (fim - ini) - km_c
            postos.append({
                "km_carr": km_c, "km_vazio": km_v,
                "t_carr_h": km_c / vc, "t_vazio_h": km_v / vv,
                "preco": u(params["preco_litro"]),
                "fila_min": u(params["fila_min"]),
            })
        rotas.append(postos)
        rotas_info.append({"dist_km": d, "v_carr": vc, "v_vazio": vv, "n_postos": n})

    # demanda minima por rota 
    lo, hi = params["demanda_por_rota"]
    demanda = [int(rng.integers(lo, hi + 1)) for _ in range(R)]
    teto = min(K, demanda_max_total if demanda_max_total else K)
    while sum(demanda) > teto and max(demanda) > 1:
        i = int(rng.choice([r for r in range(R) if demanda[r] > 1]))
        demanda[i] -= 1

    # caminhoes
    def cons_trecho(cam, p):
        return cam["c_carr"] * p["t_carr_h"] + cam["c_vazio"] * p["t_vazio_h"]

    lo_t, hi_t = params["tanque_L"]
    lo_c, hi_c = params["cons_carregado_Lh"]
    lo_v, hi_v = params["cons_vazio_Lh"]
    rejeicoes = ajustados = 0
    caminhoes = []
    for k in range(K):
        for _ in range(1000):
            s = float(rng.uniform())                    # porte do caminhao
            sc = float(np.clip(s + rng.normal(0, params["ruido_porte"]), 0, 1))
            sv = float(np.clip(s + rng.normal(0, params["ruido_porte"]), 0, 1))
            tanque = lo_t + s * (hi_t - lo_t)
            cam = {
                "tanque": tanque,
                "c_carr": lo_c + sc * (hi_c - lo_c),
                "c_vazio": lo_v + sv * (hi_v - lo_v),
                "reserva": u(params["reserva_pct"]) * tanque,
            }
            maior = max(cons_trecho(cam, p) for rt in rotas for p in rt)
            if maior <= tanque - cam["reserva"]:
                break
            rejeicoes += 1
        else:
            raise RuntimeError("nao foi possivel gerar caminhao viavel; revise as faixas")
        
        primeiro = max(cons_trecho(cam, rt[0]) for rt in rotas)
        desejado = u(params["nivel_inicial_pct"]) * tanque
        minimo = cam["reserva"] + primeiro
        cam["nivel_inicial"] = min(tanque, max(desejado, minimo))
        ajustados += desejado < minimo
        caminhoes.append(cam)

    return {
        "K": K, "R": R, "C": C, "seed": seed,
        "rotas": rotas, "rotas_info": rotas_info,
        "caminhoes": caminhoes, "demanda": demanda,
        "custo_hora": params["custo_hora_parado"],
        "bombeio_L_por_min": params["bombeio_L_por_min"],
        "diag_gen": {"rejeicoes": rejeicoes, "nivel_ajustado": int(ajustados)},
    }


def derivados(inst):
    """pi[r][p] (R$/L com bombeio), F[r][p] (R$/parada pela fila), cons[k][r][p] (L)."""
    ch, bomb = inst["custo_hora"], inst["bombeio_L_por_min"]
    pi = [[p["preco"] + ch / 60.0 / bomb for p in rt] for rt in inst["rotas"]]
    F = [[ch / 60.0 * p["fila_min"] for p in rt] for rt in inst["rotas"]]
    cons = []
    for cam in inst["caminhoes"]:
        cons.append([
            [cam["c_carr"] * p["t_carr_h"] + cam["c_vazio"] * p["t_vazio_h"] for p in rt]
            for rt in inst["rotas"]
        ])
    return pi, F, cons


def diagnostico(inst):
    """Estatisticas do gerador (nao usa o Gurobi): quanto os caminhoes precisam abastecer."""
    K, R, C = inst["K"], inst["R"], inst["C"]
    P = max(len(rt) for rt in inst["rotas"])
    T = C * P
    _, _, cons = derivados(inst)

    def consumo_horizonte(k, r):                        
        n = len(inst["rotas"][r])
        return sum(cons[k][r][(t - 1) % P] for t in range(1, T + 1) if (t - 1) % P < n)

    precisa = 0
    for k, cam in enumerate(inst["caminhoes"]):
        folga = cam["nivel_inicial"] - cam["reserva"]
        precisa += min(consumo_horizonte(k, r) for r in range(R)) > folga
    ciclo_h = [sum(p["t_carr_h"] + p["t_vazio_h"] for p in rt) for rt in inst["rotas"]]
    ciclo_L = [sum(cons[k][r]) for k in range(K) for r in range(R)]
    n_postos_total = sum(len(rt) for rt in inst["rotas"])
    return {
        "frac_precisa_abast": precisa / K,
        "tempo_ciclo_h": statistics.mean(ciclo_h),
        "consumo_ciclo_L": statistics.mean(ciclo_L),
        "rejeicoes": inst["diag_gen"]["rejeicoes"],
        "frac_nivel_ajustado": inst["diag_gen"]["nivel_ajustado"] / K,
        "n_bin_aprox": K * R + K * C * n_postos_total,
    }



# MODELO GUROBI 

def construir_e_resolver(inst, tempo_limite=TEMPO_LIMITE_S, gap=1e-4, log=False):
    import gurobipy as gp
    from gurobipy import GRB

    K, R, C = inst["K"], inst["R"], inst["C"]
    n_postos = [len(rt) for rt in inst["rotas"]]
    P = max(n_postos)                  
    T = C * P                          
    pi, F, cons = derivados(inst)

    def p_of(t):                       
        return (t - 1) % P

    def c_of(k, r, t):                 
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
    
    idx = [(k, t, r) for k in range(K) for r in range(R)
           for t in range(1, T) if p_of(t) < n_postos[r]]
    y = m.addVars(idx, vtype=GRB.BINARY, name="y")
    q = m.addVars(idx, lb=0.0, name="q")
    for (k, t, r) in idx:
        q[k, t, r].UB = U[k]
    v = m.addVars(K, range(1, T + 1), name="v")
    for k in range(K):
        for t in range(1, T + 1):
            v[k, t].LB = cam[k]["reserva"]     
            v[k, t].UB = cam[k]["tanque"]      

    # objetivo
    m.setObjective(
        gp.quicksum(pi[r][p_of(t)] * q[k, t, r] + F[r][p_of(t)] * y[k, t, r]
                    for (k, t, r) in idx),
        GRB.MINIMIZE)

    for k in range(K):
        # balanco
        m.addConstr(v[k, 1] == cam[k]["nivel_inicial"]
                    - gp.quicksum(c_of(k, r, 1) * x[k, r] for r in range(R)))
        for t in range(2, T + 1):
            compra = gp.quicksum(q[k, t - 1, r] for r in range(R) if (k, t - 1, r) in q)
            m.addConstr(v[k, t] == v[k, t - 1] + compra
                        - gp.quicksum(c_of(k, r, t) * x[k, r] for r in range(R)))
        #  nao enche alem do tanque
        for t in range(1, T):
            compra = gp.quicksum(q[k, t, r] for r in range(R) if (k, t, r) in q)
            m.addConstr(v[k, t] + compra <= cam[k]["tanque"])
        #  alocacao unica
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

        #adicionado para ver problemas do false
        res["x_frac_max"] = max(min(x[k, r].X, 1 - x[k, r].X) for k in range(K) for r in range(R))
        res["y_frac_max"] = max((min(y[i].X, 1 - y[i].X) for i in idx), default=0.0)
        res["q_sem_parada"] = sum(q[i].X for i in idx if y[i].X <= 0.5)
        
    return res



# C. VERIFICADOR INDEPENDENTE (nao usa o Gurobi)

def verificar_solucao(inst, res, tol=0.05):
    """Reconstroi niveis e custo a partir de (rota, paradas) e confere restricoes."""
    if res["sol"] is None:
        return False, "sem solucao"
    K, C = inst["K"], inst["C"]
    P = max(len(rt) for rt in inst["rotas"])
    T = C * P
    pi, F, cons = derivados(inst)
    rota = res["sol"]["rota"]
    paradas = {tuple(map(int, kk.split(","))): lit for kk, lit in res["sol"]["paradas"].items()}

    # demanda e alocacao unica 
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
                return False, f"caminhao {k} abaixo da reserva em t={t} (deficit {cam['reserva'] - nivel:.6f} L)"
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



# EXPERIMENTOS  /  TABELA

CAMPOS = ["escala", "seed", "K", "R", "C", "T", "n_bin", "n_cont", "n_restr",
          "status", "tempo_s", "custo_otimo", "turnos_dia", "custo_dia", "gap",
          "n_paradas", "frac_precisa_abast", "verificada"]


def rodar_experimentos(saida="resultados.csv"):
    with open(saida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for nome, seed, K, R, C, dmax, turnos in casos():
            inst = gerar_instancia(K, R, C, seed, demanda_max_total=dmax)
            with open(f"inst_{nome}_{seed}.json", "w") as fi:
                json.dump(inst, fi)
            diag = diagnostico(inst)
            res = construir_e_resolver(inst)
            ok, msg = verificar_solucao(inst, res)
            P = max(len(rt) for rt in inst["rotas"])
            custo_dia = res["custo"] * turnos if (turnos and res["custo"] is not None) else None
            w.writerow({
                "escala": nome, "seed": seed, "K": K, "R": R, "C": C,
                "T": C * P, "n_bin": res["n_bin"], "n_cont": res["n_cont"],
                "n_restr": res["n_restr"], "status": res["status"],
                "tempo_s": round(res["tempo_s"], 3),
                "custo_otimo": res["custo"], "turnos_dia": turnos, "custo_dia": custo_dia,
                "gap": res["gap"], "n_paradas": res.get("n_paradas"),
                "frac_precisa_abast": round(diag["frac_precisa_abast"], 3),
                "verificada": ok,
            })
            f.flush()
            print(f"{nome} seed={seed} ({K}x{R}x{C}): custo={res['custo']} "
                  f"tempo={res['tempo_s']:.2f}s verificada={ok} ({msg})")


def _faixa(valores):
    lo, hi = min(valores), max(valores)
    return f"{lo}" if lo == hi else f"{lo}-{hi}"


def tabela_resumo(entrada="resultados.csv"):
    linhas = list(csv.DictReader(open(entrada)))
    print("| Instancia | KxRxC | Bin./Cont. | Restr. | Tempo medio (s) | Desvio | Custo medio (R$/turno) | Gap max |")
    print("|---|---|---|---|---|---|---|---|")
    for nome in list(ESCALAS) + list(PERFIS):
        L = [l for l in linhas if l["escala"] == nome and l["custo_otimo"]]
        if not L:
            continue
        tempos = [float(l["tempo_s"]) for l in L]
        custos = [float(l["custo_otimo"]) for l in L]
        gaps = [float(l["gap"]) for l in L]
        dp = statistics.stdev(tempos) if len(tempos) > 1 else 0.0
        dims = "x".join(_faixa([int(l[c]) for l in L]) for c in ("K", "R", "C"))
        print(f"| {nome} | {dims} "
              f"| {statistics.mean(int(l['n_bin']) for l in L):.0f}/"
              f"{statistics.mean(int(l['n_cont']) for l in L):.0f} "
              f"| {statistics.mean(int(l['n_restr']) for l in L):.0f} "
              f"| {statistics.mean(tempos):.2f} | {dp:.2f} "
              f"| {statistics.mean(custos):,.2f} | {max(gaps):.4%} |")


def tabela_diagnostico():
    dados = {}
    for nome, seed, K, R, C, dmax, _ in casos():
        dados.setdefault(nome, []).append(
            (K, R, C, diagnostico(gerar_instancia(K, R, C, seed, demanda_max_total=dmax))))
    print("| Escala | KxRxC | Precisa abastecer | Ciclo (h) | Consumo/ciclo (L) | Binarias (aprox.) | Rejeicoes/inst. | Nivel inicial ajustado |")
    print("|---|---|---|---|---|---|---|---|")
    for nome, L in dados.items():
        D = [d for *_, d in L]
        mm = lambda c: statistics.mean(d[c] for d in D)
        dims = "x".join(_faixa([x[i] for x in L]) for i in range(3))
        print(f"| {nome} | {dims} | {mm('frac_precisa_abast'):.0%} | {mm('tempo_ciclo_h'):.2f} "
              f"| {mm('consumo_ciclo_L'):.0f} | {min(d['n_bin_aprox'] for d in D):,}-"
              f"{max(d['n_bin_aprox'] for d in D):,} | {mm('rejeicoes'):.1f} "
              f"| {mm('frac_nivel_ajustado'):.0%} |")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "teste"
    if modo == "diagnostico":
        tabela_diagnostico()
    elif modo == "teste":
        inst = gerar_instancia(5, 2, 4, seed=1, demanda_max_total=4)
        print("diagnostico:", diagnostico(inst))
        r = construir_e_resolver(inst, log=False)
        print({k: v for k, v in r.items() if k != "sol"})
        print("verificacao:", verificar_solucao(inst, r))
    elif modo == "experimentos":
        rodar_experimentos()
        tabela_resumo()