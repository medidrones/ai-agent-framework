# Relatório de certificação — DS-013

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-013

BASELINE                    1.0.1
TASK                        Kubernetes Restart & Pod Recovery
BASELINE COMMIT             2b47559c90df8423d7f5fb3c68f1ee08b2980529

DS012 CERTIFICATION         PASS (31/31)
KUBERNETES HOST             PASS
CONTAINER IMAGE             PASS
DEPLOYMENT                  PASS
READINESS                   PASS
LIVENESS                    PASS
GRACEFUL SHUTDOWN           PASS
POD CRASH RECOVERY          PASS
CONTAINER RESTART           PASS
POD REPLACEMENT             PASS
ROLLING DEPLOYMENT          PASS
HORIZONTAL SCALING          PASS
LEASE / OWNERSHIP           PASS
FENCING                     PASS
POSTGRESQL RECOVERY         PASS
REDIS RECOVERY              PASS_WITH_DECLARED_LIMITS
HITL SAFETY                 PASS
REPLAY PROTECTION           PASS
CONCURRENT RECOVERY         PASS
NETWORK FAILURE HANDLING    PASS
DEADLINES / CANCELLATION    PASS
RESOURCE CLEANUP            PASS
KUBERNETES SECURITY         PASS
SECRET HANDLING             PASS
TENANT ISOLATION            PASS
PERFORMANCE BASELINE        PASS
BACKWARD COMPATIBILITY      PASS
QUALITY GATES               PASS
DOCUMENTATION               PASS

ACCEPTANCE GATES            32/32 PASS

TESTS PASSED                1414
TESTS FAILED                0
TESTS SKIPPED               0
COVERAGE                    92.68%

CRITICAL GAPS               0
HIGH BLOCKING GAPS          0
MANDATORY TEST FAILURES     0

FINAL DECISION              COMPLETE
M01 PROGRESS                13/16
NEXT TASK                   DS-014
```

## Acceptance gates

| Gate | Evidência | Estado |
| --- | --- | --- |
| G01 | DS-012 `COMPLETE`, 31/31 | PASS |
| G02–G04 | host público, wheel-based image e Deployment real | PASS |
| G05–G06 | readiness dependente e liveness local | PASS |
| G07–G10 | SIGTERM, pod kill, container restart e replacement | PASS |
| G11–G12 | rolling update e scale out/in reais | PASS |
| G13–G15 | owner único, lease e fencing | PASS |
| G16 | PostgreSQL 16.10 real, restart e reconciliação | PASS |
| G17 | Redis 7.4.5 AOF/noeviction, limites declarados | PASS |
| G18–G20 | pending, approve único e reject sem efeito | PASS |
| G21–G22 | replay e recovery concorrente | PASS |
| G23 | falha dos backends e NetworkPolicy | PASS |
| G24 | deadline `timed_out`; cancellation `cancelled` | PASS |
| G25 | namespace isolado e cleanup verificado | PASS |
| G26–G27 | SecurityContext/RBAC/NetworkPolicy e secret scan | PASS |
| G28 | tenant diferente sem tentativa | PASS |
| G29 | benchmark reproduzível, 10 amostras | PASS |
| G30 | API Atlas 1.x preservada; nenhuma alteração no core | PASS |
| G31 | sync, ruff, format, mypy, 1.414 testes e builds | PASS |
| G32 | 17 documentos e evidências verificáveis | PASS |

## Matriz DS013-T01–T50

Os testes T01–T09 foram cobertos por deploy, probes, SIGTERM, kill, restart,
replacement e rolling. T10 foi limitado às revisões compatíveis do host sobre
Atlas 1.0.1, sem ampliar a matriz entre releases. T11–T18 cobriram scale,
concorrência, lease/fencing e falhas/restarts PostgreSQL. T19–T25 cobriram Redis,
HITL e consumo único. T26–T35 cobriram controles do runtime, cleanup, segurança,
tenant, regressões e compatibilidade. T36–T50 foram exercitados por concorrência
multi-pod, stale fencing nas regressões reais, crash após efeito, rolling/scale
com pending, perda real de DNS, partição PostgreSQL durante lease, readiness,
liveness independente, grace period zero, observabilidade best-effort,
isolamento de tenant e imagem instalada exclusivamente por wheels.

## Limites preservados

Não se declara exactly-once universal. A garantia de efeito depende de chave de
idempotência/reconciliação. Redis foi certificado somente em standalone com AOF
`always` e `noeviction`; Sentinel, Cluster e failover físico não foram testados.
PostgreSQL standalone não certifica HA ou replicação. O cluster kind tem um nó e
não representa falha física de nó. A coexistência mixed-version foi limitada a
revisões do host compatíveis com Atlas 1.0.1. Nenhum scanner de imagem compatível
estava instalado; o scan opcional não substitui os controles e testes executados.
