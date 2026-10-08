# Relatório de certificação — DS-012

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-012

BASELINE                     1.0.1
TASK                         Failure & Crash Recovery Certification
BASELINE COMMIT              2187bcd999f470a3553048ad6fb5b3c4497c68b1

DS011 CERTIFICATION          PASS (28/28)
FAILURE TAXONOMY             PASS
CRASH CONSISTENCY            PASS
POSTGRESQL RECOVERY          PASS
POSTGRESQL AMBIGUOUS COMMIT  PASS
REDIS RECOVERY               PASS_WITH_DECLARED_LIMITS
REDIS AMBIGUOUS COMMAND      PASS
HITL SAFETY                  PASS
REPLAY PROTECTION            PASS
OWNERSHIP                    PASS
FENCING                      PASS
CONCURRENT RECOVERY          PASS
SIDE EFFECT RECONCILIATION   PASS
IDEMPOTENCY                  PASS
ATTEMPT LIMITS               PASS
DEADLINES                    PASS
CANCELLATION                 PASS
RESOURCE CLEANUP             PASS
FAULT INJECTION              PASS
SECURITY                     PASS
TENANT ISOLATION             PASS
POSTGRESQL TESTS             PASS
REDIS TESTS                  PASS
PERFORMANCE BASELINE         PASS
BACKWARD COMPATIBILITY       PASS
QUALITY GATES                PASS
DOCUMENTATION                PASS

ACCEPTANCE GATES             31/31 PASS

TESTS PASSED                 1408
TESTS FAILED                 0
TESTS SKIPPED                0
COVERAGE                     92.68%

CRITICAL GAPS                0
HIGH BLOCKING GAPS           0
MANDATORY TEST FAILURES      0

FINAL DECISION               COMPLETE
M01 PROGRESS                 12/16
NEXT TASK                    DS-013
```

## Gates

| Gate | Evidência | Estado |
| --- | --- | --- |
| G01 | relatório DS-011, 28/28 | PASS |
| G02 | `failure_recovery.py` e testes parametrizados | PASS |
| G03–G05 | crash abrupto, restart, consumo e tombstone | PASS |
| G06–G07 | PostgreSQL real e reconciliação fail-closed | PASS |
| G08–G09 | Redis AOF real e `reconcile_consumption` | PASS |
| G10–G13 | HITL real, rejeição, 100 resumes e replay | PASS |
| G14–G16 | leases, fencing e multiprocess | PASS |
| G17–G18 | efeito externo e idempotência condicional | PASS |
| G19–G23 | attempts, deadlines, cancellation, cleanup e faults | PASS |
| G24–G25 | segurança e tenant filter/namespaces | PASS |
| G26–G27 | suítes reais PostgreSQL/Redis | PASS |
| G28 | benchmarks reproduzíveis | PASS |
| G29 | API aditiva, fixture v1 e wheel Python 3.12 | PASS |
| G30 | sync, lint, format, typing, pytest e build | PASS |
| G31 | 15 artefatos documentais | PASS |

## Limites preservados

Não se declara exactly-once universal. Redis depende da configuração de
persistência e da topologia; Sentinel/Cluster não foram certificados. PostgreSQL
standalone não certifica failover ou replicação assíncrona. Side effect externo sem
reconciliação confiável permanece bloqueado. Esses limites evitam garantias
fictícias e não reduzem os gates da topologia declarada.
