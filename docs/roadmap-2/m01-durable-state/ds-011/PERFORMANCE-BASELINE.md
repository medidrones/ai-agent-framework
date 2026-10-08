# Baseline de performance

Ambiente: Python 3.13.15, redis-py 6.4.0, Redis 7.4.11 standalone, AOF
`appendfsync always`, `noeviction`, Windows local, Atlas 1.0.1. Medições em
2026-10-08; não constituem SLA.

| Operação | Amostras | Mediana | P95 |
| --- | ---: | ---: | ---: |
| consumo atômico | 1.000 | 1,435 ms | 2,802 ms |
| acquire + consumo fenced | 300 | 3,152 ms | 3,974 ms |

Contenção com 100 workers: 17,995 ms, 5.556,94 operações/s, 1 vencedor e 99
conflitos controlados. Script reproduzível:
`scripts/benchmark_redis_atomic_resume.py`.
