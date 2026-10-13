# Relatório de certificação — DS-014

## Identificação

- Roadmap: 2 — Ecosystem & Enterprise
- Módulo: M01 — Durable State
- Tarefa: DS-014 — Durable HITL Certification
- Baseline: Atlas 1.0.1
- Commit-base: `a4b5f4b039f2d19286ed67c0ef8ebb10f79ea35e`
- DS-013: `COMPLETE`, 32/32 gates
- Data: 2026-10-13

## Acceptance gates

| Gate | Evidência | Estado |
| --- | --- | --- |
| G01–G04 | DS-013, arquitetura, contrato e estados | PASS |
| G05–G09 | suspensão, persistência, restart e approve/reject | PASS |
| G10–G14 | identidade, autorização e binding integral | PASS |
| G15–G18 | token, expiração, sigilo e replay | PASS |
| G19–G22 | decisões concorrentes, idempotência e atomic resume | PASS |
| G23–G25 | lease, fencing e stale worker | PASS |
| G26–G27 | PostgreSQL e Redis reais | PASS |
| G28 | Kubernetes restart/rolling/multi-pod | PASS |
| G29 | expiração, retenção e tombstones | PASS |
| G30 | falhas, reconciliação e side effects | PASS |
| G31 | auditoria durável e segurança | PASS |
| G32 | performance e 55 cenários obrigatórios | PASS |
| G33 | compatibilidade, quality gates e documentação | PASS |

## Resultado formal

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-014

BASELINE                     1.0.1
TASK                         Durable HITL Certification

DS013 CERTIFICATION          PASS (32/32)
DURABLE SUSPENSION           PASS
DECISION PERSISTENCE         PASS
HOST IDENTITY               PASS
AUTHORIZATION                PASS
SCOPE BINDING                PASS
RESUME TOKEN SECURITY        PASS
EXPIRATION                   PASS
CONCURRENT DECISIONS         PASS
IDEMPOTENCY                  PASS
ATOMIC RESUME                PASS
REPLAY PROTECTION            PASS
LEASE / OWNERSHIP            PASS
FENCING                      PASS
POSTGRESQL HITL              PASS
REDIS HITL                   PASS_WITH_DECLARED_LIMITS
KUBERNETES HITL              PASS
FAILURE RECONCILIATION       PASS
SIDE EFFECT SAFETY           PASS
CANCELLATION / DEADLINES     PASS
DURABLE AUDIT                PASS
SECURITY                     PASS
PERFORMANCE BASELINE         PASS
BACKWARD COMPATIBILITY       PASS
QUALITY GATES                PASS
DOCUMENTATION                PASS

ACCEPTANCE GATES             33/33 PASS
MANDATORY SCENARIOS          55/55 PASS
TESTS PASSED                 1442
TESTS FAILED                 0
TESTS SKIPPED                0
COVERAGE                     92.68%

CRITICAL GAPS                0
HIGH BLOCKING GAPS           0
MANDATORY TEST FAILURES      0

FINAL DECISION               COMPLETE
M01 PROGRESS                 14/16
NEXT TASK                    DS-015 (NOT STARTED)
```

## Limitações preservadas

Não se declara exactly-once universal. Identidade é autenticada pelo host; o
Atlas não fornece IdP ou UI. Redis foi certificado apenas em standalone com AOF
`always` e `noeviction`. PostgreSQL e o cluster kind não certificam HA físico.
Efeito externo sem idempotência ou reconciliação confiável permanece bloqueado.
