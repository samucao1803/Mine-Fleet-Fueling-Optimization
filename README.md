# Mine-Fleet-Fueling-Optimization

Trabalho de Pesquisa Operacional: otimização do abastecimento de uma frota de caminhões em mina.
O problema é modelado como programação linear inteira mista (PLIM) e resolvido com Python + Gurobi.

**Integrantes:** Samuel Lima Horta, Julia Martins dos Santos, Matheus Guedes Belloni

## Problema
Cada caminhão é alocado a uma rota (carga → descarga → volta) e decide em quais postos parar para
abastecer e quantos litros comprar. O objetivo é minimizar o custo total (combustível + tempo parado
com bombeio e fila), sem que o tanque chegue a um posto abaixo da reserva de segurança.

O modelo (versão 3) usa as variáveis `x[k,r]`, `y[k,t,r]`, `q[k,t,r]` e `v[k,t]`, com posições `t`
numeradas ao longo do turno: `T = C·P`, onde `C` é o número de ciclos e `P` o maior número de postos
entre as rotas. Com `T = C·P`, toda rota percorre exatamente `C` circuitos completos (ida carregado +
volta vazio). O modelo resolve um turno; nos perfis de mina, o custo diário é o custo do turno
multiplicado pelos turnos por dia (turnos tratados como idênticos e independentes).

## Arquivos
- `fleet_fueling_optmizer.py`: gerador de instâncias, modelo Gurobi, verificador e experimentos.

## Estrutura do script
- `PARAMS`, `ESCALAS`, `PERFIS`, `SEEDS`, `TEMPO_LIMITE_S`: faixas dos parâmetros, escalas e perfis de
  mina (itens pendentes de confirmação marcados com `TODO`).
- `gerar_instancia(K, R, C, seed)`: sorteia rotas, postos, caminhões e demanda, garantindo viabilidade
  (cada trecho cabe em tanque − reserva e o nível inicial cobre reserva + primeiro trecho).
- `amostrar_perfil(nome, seed)`: sorteia caminhões, rotas, ciclos e turnos/dia nas faixas de um perfil
  de mina.
- `diagnostico(inst)`: estatísticas do gerador (fração de caminhões que precisam abastecer, tempo de
  ciclo, tamanho aproximado do modelo). Não precisa do Gurobi.
- `construir_e_resolver(inst)`: monta o modelo v3 (restrições 1 a 8) e devolve status, custo, gap,
  tempo e tamanho do modelo.
- `verificar_solucao(inst, res)`: refaz níveis do tanque e custo sem usar o Gurobi, para detectar bugs.
- `rodar_experimentos()` e `tabela_resumo()`: percorrem escalas e perfis × seeds, gravam
  `resultados.csv` e imprimem a tabela do relatório (média e desvio por escala).

## Como rodar
Requer Python 3 e uma licença do Gurobi. A licença de tamanho limitado (instalada via pip) comporta,
em princípio, apenas as instâncias pequena e média; para as demais, use a licença acadêmica gratuita.

```
pip install gurobipy numpy
python fleet_fueling_optmizer.py diagnostico    # só o gerador (não precisa do Gurobi)
python fleet_fueling_optmizer.py teste          # uma instância 5x2x4
python fleet_fueling_optmizer.py experimentos   # todas as escalas e perfis x 10 seeds
```

## Calibração dos dados sintéticos
Faixas definidas a partir de dados operacionais agregados (os dados brutos são sigilosos e não devem
ser versionados).

| Parâmetro | Faixa |
|---|---|
| Distância origem → destino (ida; a volta é igual) | 1.000 a 13.318 m |
| Postos por rota | 1 ou 2 |
| Velocidade média carregado / vazio | 8–35 km/h / 12–45 km/h |
| Consumo carregado / vazio | 107,5–592 / 80,6–289 (L/h, a confirmar) |
| Capacidade do tanque | 500 a 5.300 L (sorteada junto com o consumo: caminhão maior consome mais) |
| Reserva de segurança | 10–15% do tanque |
| Nível inicial | 15–90% do tanque (elevado se não cobrir reserva + primeiro trecho) |
| Preço do combustível | R$ 6,70 (único) |
| Fila fixa por posto | 6 a 25 min (uniforme) |
| Custo da hora parada | R$ 1.500/h (estimativa: custo de posse e operação de caminhão de 150–240 t) |
| Taxa de bombeio | 600 L/min (estimativa: sistemas de abastecimento rápido operam entre 100 e 1.300 L/min) |

Dinâmica do tanque: cada rota é um circuito de comprimento 2d (ida carregado, volta vazio) com os
postos em pontos aleatórios; cada trecho entre postos tem uma parte carregada e outra vazia. O consumo do
trecho é a taxa de consumo (L/h) vezes as horas percorridas (km ÷ velocidade média da rota).

## Instâncias
Dados sintéticos com seed fixa, 10 seeds por escala.

| Escala | Caminhões × rotas × ciclos |
|---|---|
| Pequena | 5 × 2 × 4 |
| Média | 15 × 3 × 6 |
| Grande | 40 × 3 × 8 |
| Realista | 40 × 3 × 20 |
| Realista (12 rotas) | 40 × 12 × 20 |

Perfis de mina (cada seed sorteia uma combinação nas faixas):

| Perfil | Caminhões | Rotas ativas | Ciclos/turno | Turnos/dia |
|---|---|---|---|---|
| Mina de médio porte | 10–30 | 3–8 | 8–20 | 2–3 |
| Mina de grande porte | 30–100 | 8–20 | 7–20 | 2–3 |

Demanda mínima: pelo menos 1 caminhão por rota, com total limitado à metade da frota nos perfis.

## Status
- [x] Modelagem v3 (com `T = C·P`) e documento do projeto
- [x] Gerador calibrado com as faixas dos dados reais, testado em todas as escalas e perfis
- [x] Verificador testado com soluções gulosas (21 instâncias viáveis)
- [ ] Modelo Gurobi testado
- [ ] Verificador validado com soluções do Gurobi
- [ ] Experimentos nas escalas e perfis
- [ ] Tabela de resultados e análise

## Validação (a fazer)
1. Recalcular à mão o custo de um par caminhão-rota (como na seção 8 do PDF do exemplo).
2. Conferir que o verificador devolve `ok` em todas as rodadas do Gurobi.
3. Comparar o Gurobi com uma enumeração das atribuições caminhão→rota em instâncias pequenas.

## Pendências
- Confirmar com o gerente a unidade do consumo (assumido L/h) e a distância (assumida como a de ida).
- Calibrar a taxa de bombeio com os litros por evento dos dados reais (hoje 600 L/min, estimado).
- Rodar a sensibilidade do custo da hora parada (ex.: R$ 1.500, 5.000 e 15.000).
- Confirmar o número de seeds (proposta: 10) e o limite de tempo do Gurobi (proposta: 600 s).
- Medir o tempo de solução dos perfis de mina, principalmente o de grande porte (até cerca de 30 mil
  variáveis binárias).

## Estrutura do código (docstring do script)

```
Estrutura:
  A. gerar_instancia()      -> dados sinteticos reprodutiveis (seed fixa), calibrados
                               com as faixas dos dados reais
  B. construir_e_resolver() -> modelo Gurobi com posicoes t (x, y, q, v)
  C. verificar_solucao()    -> checagem independente da solucao
  D. rodar_experimentos()   -> loop escalas x seeds -> resultados.csv
  E. tabela_resumo()        -> tabela do relatorio (media/desvio por escala)

Uso:
  python fleet_fueling_optmizer.py diagnostico    # so o gerador (nao precisa do Gurobi)
  python fleet_fueling_optmizer.py teste          # uma instancia pequena (5x2x4)
  python fleet_fueling_optmizer.py experimentos   # escalas + perfis de mina x N seeds
```