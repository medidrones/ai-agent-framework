# Baseline de performance

Medição local em 2026-10-08; não é SLA. Ambiente: Atlas 1.0.1, Python 3.13.15
nos testes, Windows 11 Pro 10.0.26200, Intel i9-12900KS (24 processadores
lógicos), aproximadamente 64 GiB RAM, PostgreSQL 16.14 e Redis 7.4.11.

PostgreSQL, 100 amostras (`benchmark_ds012_postgresql_recovery.py`):

| Operação | Mediana | P95 |
| --- | ---: | ---: |
| save | 1,900 ms | 3,778 ms |
| discovery | 1,127 ms | 2,773 ms |
| acquire + release de lease | 3,935 ms | 6,488 ms |
| consumo atômico | 1,834 ms | 2,682 ms |

Redis, 1.000 consumos e 300 operações fenced
(`benchmark_redis_atomic_resume.py`): consumo mediano 1,466 ms/P95 7,697 ms;
lease + consumo mediano 3,411 ms/P95 4,602 ms. Contenção com 100 operações:
15,042 ms, 6.648,10 ops/s, um vencedor e 99 conflitos controlados.

Os cenários funcionais de multiprocess, contenção, HITL e reconciliação são
exercitados pelas baterias correspondentes. Resultados de um backend não são
extrapolados para o outro.
