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

## Estrutura do repositório
```
fleet_fueling_optimizer.py       gerador de instâncias, modelo Gurobi, verificador e experimentos
graphics/
  graphics.py                    figuras e tabela-resumo a partir de results/resultados.csv
  fig*.png, tabela_resumo.*      figuras e tabela geradas
sensibilidade/
  sensibilidade_custo_hora.py    experimento de sensibilidade ao custo da hora parada
  graficos_sensibilidade.py      figuras e tabela da sensibilidade
  sens1..sens5_*.png/.pdf        figuras geradas
  tabela_sensibilidade.*         tabela gerada (CSV, Markdown e LaTeX)
instances/                       instâncias geradas (inst_<escala>_<seed>.json, 70 arquivos)
results/
  resultados.csv                 saída dos experimentos principais (70 linhas)
  sensibilidade_custo_hora.csv   sensibilidade, escala realista (30 linhas)
  sens_mina_media.csv            sensibilidade, mina média (30 linhas)
  sens_mina_grande.csv           sensibilidade, mina grande (18 linhas)
  teste_sens.csv                 saída do teste rápido (pode ser apagada)
```
As instâncias são sintéticas e reprodutíveis: a mesma escala e a mesma seed sempre geram os mesmos
dados. O `rodar_experimentos()` grava cada `inst_<escala>_<seed>.json` na pasta atual; eles ficam
em `instances/` depois de movidos para lá.

## Estrutura dos scripts
`fleet_fueling_optimizer.py`
- `PARAMS`, `ESCALAS`, `PERFIS`, `SEEDS`, `TEMPO_LIMITE_S`: faixas dos parâmetros, escalas e perfis de
  mina.
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

`sensibilidade/sensibilidade_custo_hora.py`
- Importa o otimizador sem alterá-lo e reroda as mesmas instâncias trocando só o custo da hora
  parada (R$/h). Veja a seção "Sensibilidade ao custo da hora parada".

`graphics/graphics.py`
- Lê o `resultados.csv` e gera as figuras (PNG e PDF) e a tabela-resumo (CSV, Markdown e LaTeX).

`sensibilidade/graficos_sensibilidade.py`
- Lê os três CSV de sensibilidade em `results/` e gera 5 figuras (PNG e PDF) e a tabela da
  sensibilidade (CSV, Markdown e LaTeX).

## Como rodar
Requer Python 3 e uma licença do Gurobi. A licença de tamanho limitado (instalada via pip) comporta,
em princípio, apenas as instâncias pequena e média; para as demais, use a licença acadêmica gratuita.

```
pip install gurobipy numpy pandas matplotlib tabulate
python fleet_fueling_optimizer.py diagnostico    # só o gerador (não precisa do Gurobi)
python fleet_fueling_optimizer.py teste          # uma instância 5x2x4
python fleet_fueling_optimizer.py experimentos   # todas as escalas e perfis x 10 seeds -> resultados.csv
python graphics/graphics.py results/resultados.csv graphics    # figuras e tabela-resumo
```
Os comandos da sensibilidade estão na seção "Sensibilidade ao custo da hora parada".
O `experimentos` grava `resultados.csv` na pasta atual; mova-o para `results/`.

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

## Resultados dos experimentos principais
Segunda rodada (12/11/2026): 7 grupos × 10 seeds = 70 instâncias, limite de 600 s por instância.
- As 70 soluções passam no verificador independente (`verificada=True`).
- 62 instâncias foram resolvidas ao ótimo (status 2, gap ≤ 0,01%) e 8 atingiram o limite de tempo
  (status 9): 4 em `realista_12r` e 4 em `mina_grande`, com gap final entre 0,05% e 1,11%. O custo
  dessas 8 é a melhor solução encontrada.

| Escala | Ótimas | Tempo mediano (s) | Gap máx. |
|---|---|---|---|
| Pequena | 10/10 | 0,01 | ≤ 0,01% |
| Média | 10/10 | 0,05 | ≤ 0,01% |
| Grande | 10/10 | 0,30 | ≤ 0,01% |
| Realista | 10/10 | 3,60 | ≤ 0,01% |
| Realista (12 rotas) | 6/10 | 286 | 1,11% |
| Mina média | 10/10 | 1,48 | ≤ 0,01% |
| Mina grande | 6/10 | 188 | 0,64% |

Com 40 caminhões, a mediana do tempo é 0,3 s com 3 rotas e 8 ciclos, 3,6 s com 3 rotas e 20 ciclos e
286 s com 12 rotas e 20 ciclos. O gargalo é o número de rotas, mais do que o de ciclos. Os tempos
variam um pouco entre rodadas; perto do limite de 600 s, uma mesma instância pode ou não fechar.

## Sensibilidade ao custo da hora parada
O custo da hora parada (R$ 1.500/h) é uma estimativa. O experimento reroda as mesmas instâncias
(mesma seed) com R$ 1.500, 5.000 e 15.000 por hora, mudando só esse valor, e registra o custo, a
divisão do custo (combustível, bombeio e fila), o número de paradas, os litros por parada e o
"arrependimento": quanto custaria, no cenário novo, reusar o plano de abastecimento ótimo do
caso-base em vez de reotimizar.

```
python sensibilidade/sensibilidade_custo_hora.py media --seeds 1-3                  # teste rápido
python sensibilidade/sensibilidade_custo_hora.py realista --saida results/sensibilidade_custo_hora.csv
python sensibilidade/sensibilidade_custo_hora.py mina_media --saida results/sens_mina_media.csv
python sensibilidade/sensibilidade_custo_hora.py mina_grande --apenas-fechadas --tempo 1800 \
       --saida results/sens_mina_grande.csv
python sensibilidade/graficos_sensibilidade.py results sensibilidade               # figuras e tabela
```
Rode da raiz do repositório. Opções úteis: `--retomar` continua uma rodada interrompida,
`--apenas-fechadas` usa só as seeds que o caso-base resolveu ao ótimo, `--seeds` e `--valores`
escolhem as seeds e os custos. O caso-base (R$ 1.500/h) é conferido contra `results/resultados.csv`.

### Execução (18/11/2026)
- Realista (40×3×20): 10 seeds, limite de 600 s. Mina média: 10 seeds, 600 s. Mina grande: 6 seeds (as
  que fecharam no caso-base), limite de **1.800 s**. Total: 78 linhas.
- As 78 soluções passam no verificador (`verificada=True`) e o caso-base confere com o `resultados.csv`
  em todas as instâncias.
- 9 das 78 linhas não fecharam no limite de tempo (todas com R$ 5.000/h ou 15.000/h), com gap de até
  4,33% (realista), 7,22% (mina média) e 9,03% (mina grande). Nenhuma ficou inviável.

### Resultados (medianas por escala)
| Escala | R$/h | Ótimas | Tempo mediano (s) | Gap máx (%) | Custo ÷ base | Fila (%) | L/parada ÷ base | Extra plano base (% med.) |
|---|---|---|---|---|---|---|---|---|
| Realista (40×3×20) | 1.500 | 10/10 | 5,5 | 0,01 | 1,00 | 7 | 1,00 | – |
| Realista (40×3×20) | 5.000 | 10/10 | 92,6 | 0,01 | 1,18 | 20 | 1,01 | 0,02 |
| Realista (40×3×20) | 15.000 | 8/10 | 183,8 | 4,33 | 1,68 | 41 | 1,05 | 1,25 |
| Mina média (perfil) | 1.500 | 10/10 | 4,1 | 0,01 | 1,00 | 10 | 1,00 | – |
| Mina média (perfil) | 5.000 | 9/10 | 10,4 | 0,47 | 1,24 | 25 | 1,03 | 0,00 |
| Mina média (perfil) | 15.000 | 8/10 | 41,1 | 7,22 | 1,84 | 44 | 1,27 | 3,47 |
| Mina grande (perfil) | 1.500 | 6/6 | 74,1 | 0,01 | 1,00 | 12 | 1,00 | – |
| Mina grande (perfil) | 5.000 | 5/6 | 319,6 | 1,65 | 1,28 | 28 | 1,03 | 0,50 |
| Mina grande (perfil) | 15.000 | 3/6 | 1470,4 | 9,03 | 1,98 | 46 | 1,38 | 7,41 |

Colunas: "Custo ÷ base" é o custo ótimo dividido pelo custo com R$ 1.500/h na mesma instância; "Fila"
é a parcela do custo ótimo gasta com fila; "L/parada ÷ base" é a razão de litros por parada;
"Extra plano base" é o arrependimento (custo extra de manter o plano de R$ 1.500/h).

- **O custo cresce menos que proporcionalmente à hora parada.** Com a hora 3,3× e 10× mais cara, o
  custo mediano sobe 1,18× e 1,68× (realista), 1,24× e 1,84× (mina média), 1,28× e 1,98× (mina grande).
- **A parcela da fila sobe de 7–12% (R$ 1.500/h) para 41–46% (R$ 15.000/h).**
- **O número de paradas quase não muda** (mediana de 0,91 a 1,00 do caso-base); o que muda é o
  tamanho do abastecimento: os litros por parada sobem até 1,27× (mina média) e 1,38× (mina grande) a
  R$ 15.000/h. O modelo abastece menos vezes, em volumes maiores.
- **Reotimizar importa quando a hora parada é cara e a frota é grande.** A mediana do custo extra de
  manter o plano de R$ 1.500/h é de 0,02% a 5.000/h e 1,25% a 15.000/h no realista; 3,47% (máx. 20,2%)
  na mina média e 7,41% (máx. 10,4%) na mina grande a 15.000/h. Nas linhas que não fecharam, o valor
  é um limite inferior do arrependimento real.
- **O tempo de solução cresce com o custo da hora** (mediana da mina grande: 74 s, 320 s e 1.470 s),
  provavelmente porque, com a fila mais cara, há mais soluções de custo parecido para o solver separar.
- Figuras em `sensibilidade/`: `sens1_composicao_custo`, `sens2_custo_relativo`,
  `sens3_paradas_litros`, `sens4_arrependimento` e `sens5_tempo`.

## Status
- [x] Modelagem v3 (com `T = C·P`) e documento do projeto
- [x] Gerador calibrado com as faixas dos dados reais, testado em todas as escalas e perfis
- [x] Verificador testado com soluções gulosas (21 instâncias viáveis)
- [x] Modelo Gurobi testado (roda em todas as escalas e perfis; nenhuma instância inviável)
- [x] Verificador validado com soluções do Gurobi (70 de 70 verificadas)
- [x] Experimentos nas escalas e perfis (resultados.csv)
- [x] Figuras e tabela-resumo (`graphics/`)
- [x] Sensibilidade ao custo da hora parada (executada em 18/11/2026: 78 linhas, 78 verificadas)
- [x] Figuras e tabela da sensibilidade (`sensibilidade/`)

## Pendências
- Registrar o processador, a RAM e a versão do Gurobi usados nos experimentos.
- Comparar o ótimo com uma política simples de abastecimento (ex.: abastecer ao atingir a reserva).
- Escrever o relatório.

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
  python fleet_fueling_optimizer.py diagnostico    # so o gerador (nao precisa do Gurobi)
  python fleet_fueling_optimizer.py teste          # uma instancia pequena (5x2x4)
  python fleet_fueling_optimizer.py experimentos   # escalas + perfis de mina x N seeds
```
