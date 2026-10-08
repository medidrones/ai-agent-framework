# Baseline de performance

Ambiente local de certificação: Windows, PostgreSQL 16 Alpine em Docker,
conexão TCP local, pool assíncrono, 30 amostras por operação.

| Operação | Mediana | p95 | Amostras |
| --- | ---: | ---: | ---: |
| acquire/readquisição | 1,554 ms | 2,802 ms | 30 |
| renew | 1,551 ms | 2,590 ms | 30 |
| release | 1,464 ms | 1,928 ms | 30 |

O teste registra métricas com `perf_counter` e valida simultaneamente o avanço
monotônico das 30 gerações. Esses valores são referência local, não SLO de
produção; rede, contenção, fsync e configuração do banco alteram a latência.
