# Baseline de performance

Medição em 2026-10-10, kind/Kubernetes v1.31.2, um nó, Docker Desktop 29.8.1,
Python 3.12.15, Atlas 1.0.1, PostgreSQL 16.10, Redis 7.4.5 e dois workers.

| Métrica | Resultado |
| --- | ---: |
| Recovery PostgreSQL, mediana de 10 | 1.700,207 ms |
| Recovery PostgreSQL, p95 | 1.800,735 ms |
| Pod replacement + readiness | 5.967,324 ms |
| Scale out 2 → 3 | 6.005,274 ms |
| Scale in 3 → 2 | 174,601 ms |
| Rolling update | 6.052,535 ms |
| Crash, lease e recovery | 3.485,666 ms |
| Falhas observadas | 0 |

São medições locais reproduzíveis, não objetivos de serviço nem SLA.
