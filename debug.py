import json, fleet_fueling_optimizer as a
inst = json.load(open("inst_mina_grande_10.json"))
res = a.construir_e_resolver(inst)
print(a.verificar_solucao(inst, res))
print(res["x_frac_max"], res["y_frac_max"], res["q_sem_parada"])