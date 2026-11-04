# Mine-Fleet-Fueling-Optimization

Trabalho de Pesquisa Operacional: otimização do abastecimento de uma frota de caminhões em mina.
O problema é modelado como programação linear inteira mista (PLIM) e resolvido com Python + Gurobi.

**Integrantes:** Julia Martins dos Santos, Matheus Guedes Belloni, Samuel Lima Horta

## Problema
Cada caminhão é alocado a uma rota (carga → descarga → volta) e decide em quais postos parar para
abastecer e quantos litros comprar. O objetivo é minimizar o custo total (combustível + tempo parado
com bombeio e fila), sem que o tanque chegue a um posto abaixo da reserva de segurança.
O modelo (versão 3) usa as variáveis `x[k,r]`, `y[k,t,r]`, `q[k,t,r]` e `v[k,t]`, com posições `t`
numeradas ao longo do turno.

## Arquivos
- `fleet_fueling_optmizer.py`: gerador de instâncias, modelo Gurobi, verificador e experimentos.

## Estrutura do script
- `PARAMS`, `ESCALAS`, `SEEDS`, `TEMPO_LIMITE_S`: faixas e decisões em aberto (marcadas com `TODO`).
- `gerar_instancia(K, R, C, seed)`: sorteia rotas, postos, caminhões e demanda, garantindo viabilidade
  (cada trecho cabe em tanque − reserva e o nível inicial cobre o primeiro trecho).
- `construir_e_resolver(inst)`: monta o modelo v3 (restrições 1 a 8) e devolve status, custo, gap,
  tempo e tamanho do modelo.
- `verificar_solucao(inst, res)`: refaz níveis do tanque e custo sem usar o Gurobi, para detectar bugs.
- `rodar_experimentos()` e `tabela_resumo()`: percorrem escalas × seeds, gravam `resultados.csv` e
  imprimem a tabela do relatório (média e desvio por escala).

## Como rodar
Requer Python 3 e uma licença do Gurobi. A licença de tamanho limitado (instalada via pip) não comporta
as instâncias média e grande; use a licença acadêmica gratuita.

```
pip install gurobipy numpy
python abastecimento_mina.py teste          # uma instância 5x2x4
python abastecimento_mina.py experimentos   # 3 escalas x 10 seeds
```

## Instâncias
Dados sintéticos com seed fixa (os dados operacionais reais são sigilosos e não devem ser versionados).
- Pequena: 5 caminhões / 2 rotas / 4 ciclos
- Média: 15 caminhões / 3 rotas / 6 ciclos
- Grande: 40 caminhões / 3 rotas / 8 ciclos

## Status
- [x] Modelagem v3 e documento do projeto
- [x] Gerador de instâncias testado (3 escalas × 10 seeds)
- [ ] Modelo Gurobi testado
- [ ] Verificador validado
- [ ] Experimentos nas 3 escalas
- [ ] Tabela de resultados e análise

## Validação (a fazer)
1. Recalcular à mão o custo de um par caminhão-rota (como na seção 8 do PDF do exemplo).
2. Conferir que o verificador devolve `ok` em todas as rodadas.
3. Comparar o Gurobi com uma enumeração das atribuições caminhão→rota em instâncias pequenas.

## Decisões em aberto (grupo e gerência)
- Distância dos trechos: manter 30–70 km (justificando no texto) ou usar valores realistas (5–10 km)?
- Número de postos por rota (3 a 4?) e se o comprimento da rota é sorteado.
- Faixa do nível inicial (ex.: 25–40% do tanque), que define se abastecer é uma decisão real.
- Número de seeds e limite de tempo do Gurobi.
- Incluir ou não instâncias extra-grandes.
- Calibração dos parâmetros com dados reais agregados (pedir ao gerente).
