# Baseline de performance

Execução local em PostgreSQL 16.14 Alpine, Python 3.13.15, Atlas 1.0.1, 24 CPUs,
`batch_size=1000`, três amostras por cenário:

| Registros | Workers | Mediana (ms) | p95 (ms) | Throughput mediano (reg/s) |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 2 | 329,80 | 339,20 | 303,22 |
| 100 | 5 | 228,08 | 242,11 | 438,44 |
| 1.000 | 2 | 1.360,93 | 3.773,66 | 734,79 |
| 1.000 | 5 | 2.032,77 | 3.389,39 | 491,94 |
| 10.000 | 2 | 22.198,85 | 29.310,90 | 450,47 |
| 10.000 | 5 | 6.486,85 | 7.960,86 | 1.541,58 |

Todas as amostras removeram exatamente o volume preparado. A distribuição foi
feita por `SKIP LOCKED`; não houve exclusão duplicada. Estes números são
baseline, não SLA. Reprodução:

```bash
python scripts/benchmark_postgresql_purge.py --dsn <banco_test> \
  --confirm-test-database --samples 3 --sizes 100 1000 10000 \
  --workers 2 5 --batch-size 1000
```
