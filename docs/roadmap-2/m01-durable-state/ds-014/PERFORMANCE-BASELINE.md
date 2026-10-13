# Baseline de performance

Medição em 2026-10-13, kind/Kubernetes 1.31.2, dez pods worker, PostgreSQL
16.10 e Redis 7.4.5 standalone:

| Carga | Resultado | Média | p95 |
| --- | --- | ---: | ---: |
| 100 aprovações sequenciais | 100 completed | 242,319 ms | 512,155 ms |
| 100 rejeições sequenciais | 100 rejected | 388,814 ms | 601,457 ms |
| 100 resumes concorrentes | 1/99 | 3.095,704 ms total | n/a |
| suspensões long-lived | 50 preservadas | n/a | n/a |
| workers | 10 disponíveis | n/a | n/a |

Os valores são baseline técnica local, não SLO de produção.
