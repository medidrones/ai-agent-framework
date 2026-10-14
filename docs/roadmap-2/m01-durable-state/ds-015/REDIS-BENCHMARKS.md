# Benchmarks Redis

## Ambiente

- Atlas: `1.0.1`
- Python: `3.13.15`
- Redis: `7.4.11`, imagem `redis:7.4-alpine`
- cliente Redis: `6.4.0`
- persistência: AOF habilitado, `appendfsync=always`
- eviction: `noeviction`
- host: Windows 11, 24 CPUs lógicas
- run id: `c319e7f2b7ff4b84a81e9ad2dcd6821f`
- janela: 13/10/2026 18:59–19:59, horário de Brasília

## Operações isoladas — payload de 1 KiB

| Operação | p95 (ms) | p99 (ms) | Throughput (ops/s) | Falhas |
| --- | ---: | ---: | ---: | ---: |
| save | 3,511 | 3,538 | 459,958 | 0 |
| read | 2,261 | 2,784 | 1.007,878 | 0 |
| optimistic update | 2,658 | 6,229 | 465,754 | 0 |
| atomic consume | 2,485 | 2,637 | 537,315 | 0 |
| lease acquire | 2,856 | 3,304 | 517,851 | 0 |
| lease renew | 3,160 | 3,748 | 574,109 | 0 |
| lease release | 2,864 | 4,283 | 628,575 | 0 |

O conjunto completo também mediu 16 KiB, 256 KiB e 1 MiB. Todas as amostras
ficaram dentro dos thresholds predefinidos e sem falhas inesperadas.

## Escalabilidade do workload misto

| Workers | p95 (ms) | p99 (ms) | Throughput (ciclos/s) | Falhas |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 6,794 | 6,794 | 140,566 | 0 |
| 10 | 32,946 | 32,946 | 296,327 | 0 |
| 50 | 79,715 | 80,755 | 536,750 | 0 |
| 100 | 123,864 | 129,340 | 686,792 | 0 |
| 250 | 285,026 | 293,915 | 726,488 | 0 |
| 500 | 533,686 | 542,696 | 769,313 | 0 |

## Contenção e durabilidade

Em 100 e 500 competidores, `consume`, compare-and-swap e lease produziram
exatamente um vencedor. Os demais resultados foram conflitos esperados: 99 e
499, respectivamente. Não houve consumo duplicado, lost update nem aceitação
de owner obsoleto.

O soak de 3.600,056 segundos concluiu 1.358.054 ciclos, com p95 de 176,724 ms,
p99 de 206,519 ms, 377,231 ciclos/s, crescimento de memória de 44.696.594 bytes
e zero tarefas órfãs. A injeção de falha por 60,024 segundos observou 670 falhas
controladas, recuperou o backend, concluiu 36.774 ciclos e não produziu nenhuma
confirmação falsa.

Os valores brutos, sem arredondamento, estão em `results/redis.json` e
`results/fault-redis.json`.
