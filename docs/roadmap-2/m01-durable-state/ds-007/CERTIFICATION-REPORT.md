# Relatório de certificação DS-007

## Identificação

- Roadmap: 2 — Ecosystem & Enterprise
- Módulo: M01 — Durable State
- Entrega: DS-007 — Checkpoint Expiration & Retention Policies
- Baseline: Atlas `1.0.1`
- DS-006: `COMPLETE`

## Resultado

A DS-007 introduz contratos tipados provider-neutral, migration 005, TTL/HITL,
tombstones transacionais sem payload e classificação read-only baseada no
relógio do PostgreSQL. Nenhum purge físico novo foi implementado.

## Acceptance gates

| Gate | Estado | Evidência |
| --- | --- | --- |
| DS007-G01 — DS-006 certificada | PASS | relatório DS-006 `COMPLETE` |
| DS007-G02 — contrato de expiração | PASS | contratos core e ADR-007 |
| DS007-G03 — políticas de retenção | PASS | política tipada e versionada |
| DS007-G04 — TTL | PASS | validações positivas e negativas |
| DS007-G05 — autoridade PostgreSQL | PASS | `clock_timestamp()` nas operações protegidas |
| DS007-G06 — consumo expirado | PASS | teste PostgreSQL real |
| DS007-G07 — instante limite | PASS | igualdade rejeitada |
| DS007-G08 — pós-consumo | PASS | tombstone transacional com prazo |
| DS007-G09 — pós-expiração | PASS | registro preservado e classificado |
| DS007-G10 — terminais | PASS | categoria e janela dedicada testadas |
| DS007-G11 — HITL longo | PASS | TTL específico e regressão HITL |
| DS007-G12 — leases | PASS | lease ativo bloqueia purge |
| DS007-G13 — recovery | PASS | tentativa ativa bloqueia e regressão DS-006 |
| DS007-G14 — fencing | PASS | consumo leased e regressões preservados |
| DS007-G15 — replay | PASS | digest único e tombstone sem payload |
| DS007-G16 — classificação | PASS | seis decisões, sem `DELETE` |
| DS007-G17 — mudança de política | PASS | expansão estende; redução não encurta |
| DS007-G18 — isolamento | PASS | filtro SQL por tenant e execução |
| DS007-G19 — cancellation | PASS | `CancelledError` não é convertido |
| DS007-G20 — segurança | PASS | Bandit, pip-audit e fail-closed |
| DS007-G21 — PostgreSQL | PASS | 69 testes reais |
| DS007-G22 — performance | PASS | mediana 1,227 ms; p95 2,546 ms; n=30 |
| DS007-G23 — compatibilidade 1.x | PASS | APIs aditivas e regressão integral |
| DS007-G24 — quality gates | PASS | lint, format, mypy, pytest e builds |
| DS007-G25 — documentação | PASS | 12 artefatos e ADR-007 |

## Limites preservados

- classificação não realiza purge físico;
- não há scheduler de limpeza;
- não há garantia exactly-once para efeitos externos;
- a DS-008 não foi iniciada.

## Decisão final

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-007

BASELINE                    1.0.1
TASK                        Checkpoint Expiration & Retention Policies

DS006 CERTIFICATION         PASS
EXPIRATION CONTRACT         PASS
TTL VALIDATION              PASS
POSTGRESQL TIME AUTHORITY   PASS
TEMPORAL BOUNDARIES         PASS
CONSUMED RETENTION          PASS
EXPIRED RETENTION           PASS
TERMINAL RETENTION          PASS
HITL EXPIRATION             PASS
LEASE INTEGRATION           PASS
RECOVERY INTEGRATION        PASS
FENCING INTEGRITY           PASS
REPLAY PROTECTION           PASS
PURGE CLASSIFICATION        PASS
POLICY CHANGES              PASS
MULTI_TENANT ISOLATION      PASS
SECURITY                    PASS
CANCELLATION                PASS
POSTGRESQL TESTS            PASS
PERFORMANCE BASELINE        PASS
BACKWARD COMPATIBILITY      PASS
QUALITY GATES               PASS
DOCUMENTATION               PASS

ACCEPTANCE GATES            25/25 PASS

TESTS PASSED                1259
TESTS FAILED                0
TESTS SKIPPED               0
POSTGRESQL TESTS            69
COVERAGE                    92.65%

CRITICAL GAPS               0
HIGH BLOCKING GAPS          0

FINAL DECISION              COMPLETE
NEXT TASK                   DS-008 (NOT STARTED)
```
