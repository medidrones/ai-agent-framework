# Benchmarks PostgreSQL

## Ambiente

- Atlas: `1.0.1`
- Python: `3.13.15`
- PostgreSQL: `16.14`, imagem `postgres:16-alpine`
- host: Windows 11, 24 CPUs lógicas
- banco isolado: `atlas_ds015_test`
- pool: mínimo 1, máximo 64 conexões
- run id: `223dd3cdf16c4646a49c32fcbf7a95eb`
- janela: 13/10/2026 18:40–19:40, horário de Brasília

## Operações isoladas — payload de 1 KiB

| Operação | p95 (ms) | p99 (ms) | Throughput (ops/s) | Falhas |
| --- | ---: | ---: | ---: | ---: |
| save | 2,775 | 5,268 | 470,332 | 0 |
| read | 2,346 | 3,084 | 725,835 | 0 |
| optimistic update | 4,655 | 6,271 | 423,783 | 0 |
| atomic consume | 2,127 | 5,312 | 531,086 | 0 |
| lease acquire | 2,709 | 3,477 | 483,080 | 0 |
| lease renew | 4,056 | 6,020 | 443,014 | 0 |
| lease release | 3,164 | 3,877 | 485,267 | 0 |

O conjunto completo também mediu 16 KiB, 256 KiB e 1 MiB. Todas as amostras
ficaram dentro dos thresholds predefinidos e sem falhas inesperadas.

## Escalabilidade do workload misto

| Workers | p95 (ms) | p99 (ms) | Throughput (ciclos/s) | Falhas |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 9,253 | 9,253 | 104,217 | 0 |
| 10 | 49,022 | 49,022 | 199,378 | 0 |
| 50 | 190,681 | 191,114 | 248,615 | 0 |
| 100 | 196,733 | 197,746 | 459,137 | 0 |
| 250 | 487,491 | 491,447 | 465,256 | 0 |
| 500 | 909,109 | 914,371 | 492,837 | 0 |

## Contenção e durabilidade

Em 100 e 500 competidores, `consume`, compare-and-swap e lease produziram
exatamente um vencedor. Os demais resultados foram conflitos esperados: 99 e
499, respectivamente. Não houve consumo duplicado, lost update nem aceitação
de owner obsoleto.

O soak de 3.600,073 segundos concluiu 1.096.355 ciclos, com p95 de 197,121 ms,
p99 de 233,160 ms, 304,537 ciclos/s, crescimento de memória de 36.219.069 bytes
e zero tarefas órfãs. A injeção de falha por 60,015 segundos observou 20 falhas
controladas, recuperou o backend, concluiu 45.649 ciclos e não produziu nenhuma
confirmação falsa.

Os valores brutos, sem arredondamento, estão em `results/postgresql.json` e
`results/fault-postgresql.json`.
