
import argparse
import copy
import csv
import json
import sys
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_fueling_optimizer as ffo

VALORES_PADRAO = (1500.0, 5000.0, 15000.0)
ESCALA_PADRAO = "realista"
TOL_BASE = 1e-3            # tolerancia 
STATUS_OTIMO = 2           # codigo do Gurobi para "otimo"

CAMPOS = ["escala", "seed", "K", "R", "C", "turnos_dia", "custo_hora", "e_base",
          "status", "tempo_s", "gap", "n_bin",
          "custo_otimo", "custo_dia", "custo_combustivel", "custo_bombeio", "custo_fila",
          "n_paradas", "litros_total", "litros_por_parada", "caminhoes_abastecem",
          "custo_plano_base", "arrependimento", "arrependimento_pct",
          "verificada", "msg_verificacao", "confere_base"]


def decompor_custo(inst, sol):
    """Custo de uma solucao (rota, paradas) no custo_hora de `inst`, separado em partes.
    Usa derivados() do otimizador, para nao duplicar as formulas de pi e F."""
    pi, F, _ = ffo.derivados(inst)
    P = max(len(rt) for rt in inst["rotas"])
    comb = bombeio = fila = litros = 0.0
    abastecem = set()
    for chave, lit in sol["paradas"].items():
        k, t, r = map(int, chave.split(","))
        p = (t - 1) % P
        preco = inst["rotas"][r][p]["preco"]
        comb += preco * lit
        bombeio += (pi[r][p] - preco) * lit
        fila += F[r][p]
        litros += lit
        abastecem.add(k)
    n = len(sol["paradas"])
    return {"combustivel": comb, "bombeio": bombeio, "fila": fila,
            "total": comb + bombeio + fila, "n_paradas": n, "litros": litros,
            "caminhoes_abastecem": len(abastecem)}


def carregar_base(caminho):
    """(escala, seed) -> (custo_otimo, status) do resultados.csv do caso-base."""
    if not caminho or not Path(caminho).exists():
        return {}
    ref = {}
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        for l in csv.DictReader(f):
            if l["custo_otimo"]:
                ref[(l["escala"], int(l["seed"]))] = (float(l["custo_otimo"]), int(l["status"]))
    return ref


def carregar_existente(saida, saida_sol):
    """Para --retomar: o que ja foi feito (escala, seed, custo_hora), se o caso-base foi
    verificado, e as solucoes gravadas."""
    feitas, base_ok = set(), {}
    with open(saida, newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        if leitor.fieldnames != CAMPOS:
            sys.exit(f"{saida} tem colunas diferentes das deste script; use outro --saida ou apague o arquivo.")
        for l in leitor:
            feitas.add((l["escala"], int(l["seed"]), float(l["custo_hora"])))
            if l["e_base"] == "True":
                base_ok[(l["escala"], int(l["seed"]))] = l["verificada"] == "True"
    solucoes = json.load(open(saida_sol)) if Path(saida_sol).exists() else {}
    return feitas, base_ok, solucoes


def rodar_sensibilidade(escalas, valores, seeds, saida, saida_sol, tempo_limite,
                        base_csv=None, resolver=None, retomar=False, apenas_fechadas=False):
    """`resolver` existe para testes (substitui o Gurobi); por padrao usa o modelo do projeto."""
    resolver = resolver or ffo.construir_e_resolver
    base = float(ffo.PARAMS["custo_hora_parado"])
    ordem = [base] + sorted(float(v) for v in set(valores) if float(v) != base)  # base sempre 1o
    ref = carregar_base(base_csv)
    if apenas_fechadas and not ref:
        sys.exit("--apenas-fechadas precisa do results/resultados.csv do caso-base (use --base).")
    Path(saida).parent.mkdir(parents=True, exist_ok=True)

    continuar = retomar and Path(saida).exists()
    feitas, base_ok, solucoes = carregar_existente(saida, saida_sol) if continuar else (set(), {}, {})

    # casos a rodar (escala/seed), ja com os filtros aplicados
    trabalho, pulados = [], []
    for nome, seed, K, R, C, dmax, turnos in ffo.casos(seeds):
        if nome not in escalas:
            continue
        if apenas_fechadas and ref.get((nome, seed), (None, None))[1] != STATUS_OTIMO:
            pulados.append(f"{nome} seed={seed}")
            continue
        trabalho.append((nome, seed, K, R, C, dmax, turnos))
    if pulados:
        print(f"puladas (nao fecharam ao otimo no caso-base): {', '.join(pulados)}")
    total = sum((n, s, ch) not in feitas for n, s, *_ in trabalho for ch in ordem)
    print(f"{len(trabalho)} instancias x {len(ordem)} custos; {total} resolucoes a fazer "
          f"(limite {tempo_limite:g} s cada)\n")

    feito, t_ini = 0, time.time()
    problemas = {"fora_do_otimo": 0, "nao_verificada": 0, "nao_confere": 0}
    with open(saida, "a" if continuar else "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if not continuar:
            w.writeheader()
        for nome, seed, K, R, C, dmax, turnos in trabalho:
            inst0 = ffo.gerar_instancia(K, R, C, seed, demanda_max_total=dmax)
            sol_base = None
            for ch in ordem:
                if (nome, seed, ch) in feitas:               # retomada: ja feito
                    if ch == base and base_ok.get((nome, seed)):
                        sol_base = solucoes.get(f"{nome}|{seed}|{ch:g}")
                    continue
                inst = copy.deepcopy(inst0)                  # mesmos dados; so o custo_hora muda
                inst["custo_hora"] = float(ch)
                res = resolver(inst, tempo_limite=tempo_limite)
                ok, msg = ffo.verificar_solucao(inst, res)

                linha = {"escala": nome, "seed": seed, "K": K, "R": R, "C": C,
                         "turnos_dia": turnos, "custo_hora": ch, "e_base": ch == base,
                         "status": res["status"], "tempo_s": round(res["tempo_s"], 3),
                         "gap": res["gap"], "n_bin": res["n_bin"],
                         "custo_otimo": res["custo"], "verificada": ok,
                         "msg_verificacao": "" if ok else msg}
                if res["custo"] is not None and turnos:
                    linha["custo_dia"] = res["custo"] * turnos
                if res["sol"] is not None:
                    d = decompor_custo(inst, res["sol"])
                    linha.update({
                        "custo_combustivel": d["combustivel"], "custo_bombeio": d["bombeio"],
                        "custo_fila": d["fila"], "n_paradas": d["n_paradas"],
                        "litros_total": d["litros"],
                        "litros_por_parada": d["litros"] / d["n_paradas"] if d["n_paradas"] else None,
                        "caminhoes_abastecem": d["caminhoes_abastecem"]})
                    solucoes[f"{nome}|{seed}|{ch:g}"] = res["sol"]
                    if ch == base:
                        sol_base = res["sol"] if ok else None
                        if (nome, seed) in ref:
                            r0 = ref[(nome, seed)][0]
                            linha["confere_base"] = bool(abs(res["custo"] - r0) <= TOL_BASE * max(1.0, r0))
                    elif sol_base is not None:
                        c_base = decompor_custo(inst, sol_base)["total"]
                        arr = c_base - res["custo"]
                        linha["custo_plano_base"] = c_base
                        linha["arrependimento"] = arr
                        linha["arrependimento_pct"] = 100.0 * arr / res["custo"] if res["custo"] else None
                w.writerow(linha)
                f.flush()
                with open(saida_sol, "w") as fs:             # a cada resolucao: nada se perde se parar
                    json.dump(solucoes, fs)

                feito += 1
                problemas["fora_do_otimo"] += res["status"] != STATUS_OTIMO
                problemas["nao_verificada"] += not ok
                problemas["nao_confere"] += not linha.get("confere_base", True)
                print(f"[{feito}/{total}, {time.time() - t_ini:.0f} s] {nome} seed={seed} custo_hora={ch:g}: "
                      f"custo={res['custo']} paradas={linha.get('n_paradas')} status={res['status']} "
                      f"gap={res['gap']} tempo={res['tempo_s']:.1f}s verificada={ok}"
                      + ("" if ok else f" ({msg})")
                      + ("" if linha.get("confere_base", True) else "  <<< NAO CONFERE com resultados.csv"))

    print(f"\nresumo desta rodada: {feito} resolucoes | fora do otimo (status != 2): "
          f"{problemas['fora_do_otimo']} | nao verificadas: {problemas['nao_verificada']} | "
          f"caso-base nao confere: {problemas['nao_confere']}")
    return saida


def _seeds(txt):
    """'1-10' ou '1,2,5' -> lista de inteiros."""
    out = []
    for parte in txt.split(","):
        if "-" in parte:
            a, b = parte.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(parte))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sensibilidade ao custo da hora parada")
    ap.add_argument("escalas", nargs="*", default=[ESCALA_PADRAO],
                    help="escalas/perfis de fleet_fueling_optimizer (padrao: realista)")
    ap.add_argument("--valores", default=",".join(f"{v:g}" for v in VALORES_PADRAO),
                    help="custos da hora parada em R$/h, separados por virgula")
    ap.add_argument("--seeds", default=f"{min(ffo.SEEDS)}-{max(ffo.SEEDS)}")
    ap.add_argument("--tempo", type=float, default=ffo.TEMPO_LIMITE_S, help="limite do Gurobi por resolucao (s)")
    ap.add_argument("--saida", default="results/sensibilidade_custo_hora.csv")
    ap.add_argument("--base", default="results/resultados.csv",
                    help="resultados.csv do caso-base, para conferir (ignorado se nao existir)")
    ap.add_argument("--apenas-fechadas", action="store_true",
                    help="so as seeds que o caso-base resolveu ao otimo (status 2)")
    ap.add_argument("--retomar", action="store_true",
                    help="continua uma rodada interrompida, sem refazer o que ja esta no CSV de saida")
    a = ap.parse_args()

    validas = list(ffo.ESCALAS) + list(ffo.PERFIS)
    for e in a.escalas:
        if e not in validas:
            sys.exit(f"escala '{e}' desconhecida. Opcoes: {', '.join(validas)}")
    t0 = time.time()
    saida = rodar_sensibilidade(
        a.escalas, [float(v) for v in a.valores.split(",")], _seeds(a.seeds), a.saida,
        a.saida.replace(".csv", "_solucoes.json"), a.tempo, base_csv=a.base,
        retomar=a.retomar, apenas_fechadas=a.apenas_fechadas)
    print(f"concluido em {time.time() - t0:.0f} s -> {saida}")
