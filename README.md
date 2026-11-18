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
sensibilidade_custo_hora.py      experimento de sensibilidade ao custo da hora parada
graphics/
  graphics.py                    gera as figuras e a tabela-resumo a partir de results/resultados.csv
  fig*.png, tabela_resumo.*      figuras e tabela geradas
instances/                       instâncias geradas (inst_<escala>_<seed>.json)
results/
  resultados.csv                 saída dos experimentos principais (70 linhas)
  sensibilidade_*.csv / *.json   saída dos experimentos de sensibilidade
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

`sensibilidade_custo_hora.py`
- Importa o otimizador sem alterá-lo e reroda as mesmas instâncias trocando só o custo da hora
  parada (R$/h). Veja a seção "Sensibilidade ao custo da hora parada".

`graphics/graphics.py`
- Lê o `resultados.csv` e gera as figuras (PNG e PDF) e a tabela-resumo (CSV, Markdown e LaTeX).

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
O custo da hora parada (R$ 1.500/h) é uma estimativa. O experimento reroda as mesmas instâncias com
R$ 1.500, 5.000 e 15.000 por hora e registra o custo, a divisão do custo (combustível, bombeio e
fila), o número de paradas, os litros por parada e o "arrependimento": quanto custaria, no cenário
novo, reusar o plano de abastecimento ótimo do caso-base em vez de reotimizar.

```
python sensibilidade_custo_hora.py media --seeds 1-3                  # teste rápido
python sensibilidade_custo_hora.py                                    # realista, 10 seeds, 3 valores
python sensibilidade_custo_hora.py mina_media --saida results/sens_mina_media.csv
python sensibilidade_custo_hora.py mina_grande --apenas-fechadas --tempo 1800 \
       --saida results/sens_mina_grande.csv
```
Opções úteis: `--retomar` continua uma rodada interrompida, `--apenas-fechadas` usa só as seeds que o
caso-base resolveu ao ótimo, `--seeds` e `--valores` escolhem as seeds e os custos. O caso-base
(R$ 1.500/h) é conferido contra `results/resultados.csv`.

Status: em execução. Os resultados e a análise entram aqui quando terminarem.

## Status
- [x] Modelagem v3 (com `T = C·P`) e documento do projeto
- [x] Gerador calibrado com as faixas dos dados reais, testado em todas as escalas e perfis
- [x] Verificador testado com soluções gulosas (21 instâncias viáveis)
- [x] Modelo Gurobi testado (roda em todas as escalas e perfis; nenhuma instância inviável)
- [x] Verificador validado com soluções do Gurobi (70 de 70 verificadas)
- [x] Experimentos nas escalas e perfis (resultados.csv)
- [x] Figuras e tabela-resumo (`graphics/`)
- [ ] Sensibilidade ao custo da hora parada (em execução)
- [ ] Análise dos resultados e relatório

## Validação
1. Recalcular à mão o custo de um par caminhão-rota (como na seção 8 do PDF do exemplo). *(a fazer)*
2. Conferir que o verificador devolve `ok` em todas as rodadas do Gurobi. *(feito: 70 de 70)*
3. Comparar o Gurobi com uma enumeração das atribuições caminhão→rota em instâncias pequenas.
   *(a fazer)*

## Pendências
- Confirmar com o gerente a unidade do consumo (assumido L/h) e a distância (assumida como a de ida).
- Calibrar a taxa de bombeio com os litros por evento dos dados reais (hoje 600 L/min, estimado).
- Concluir a sensibilidade ao custo da hora parada e registrar a análise.
- Decidir como tratar, no relatório, as 8 instâncias que não fecharam em 600 s (reportar o gap ou
  rerodar com limite de tempo maior).
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
