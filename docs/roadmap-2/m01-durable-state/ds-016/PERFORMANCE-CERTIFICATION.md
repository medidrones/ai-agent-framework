# Certificação consolidada de performance

Evidência primária: JSONs versionados em `../ds-015/results/` e metodologia em
`../ds-015/BENCHMARK-METHODOLOGY.md`.

| Métrica | PostgreSQL | Redis | Gate |
| --- | ---: | ---: | --- |
| p95, 50 workers | 190,681 ms | 79,715 ms | PASS |
| p95, 100 workers | 196,733 ms | 123,864 ms | PASS |
| p95, 250 workers | 487,491 ms | 285,026 ms | PASS |
| p95, 500 workers | 909,109 ms | 533,686 ms | PASS |
| p99 do soak | 233,160 ms | 206,519 ms | PASS |
| ciclos em 60 min | 1.096.355 | 1.358.054 | PASS |

Os thresholds eram p95 abaixo de 1.000 ms e p99 abaixo de 2.000 ms. Ambos os
backends permaneceram abaixo dos limites, sem erro inesperado ou violação de
segurança. A matriz cobriu payloads de 1 KiB a 1 MiB e concorrência de 1 a 500.

Esta é a primeira baseline consolidada no ambiente documentado; seus números
não constituem SLA universal de produção.

**Decisão:** `PERFORMANCE = VERIFIED`; `SOAK = PASS`.
