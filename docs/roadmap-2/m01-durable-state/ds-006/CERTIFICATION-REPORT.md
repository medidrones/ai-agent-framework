# Relatório de certificação DS-006

## Identificação

- Roadmap: 2 — Ecosystem & Enterprise
- Módulo: M01 — Durable State
- Entrega: DS-006 — Execution Recovery Coordinator
- Baseline: Atlas `1.0.1`
- Branch: `medicode/ds-006-execution-recovery`
- Data: 2026-10-08
- DS-005: `COMPLETE`

## Resultado

A DS-006 adiciona coordenação provider-neutral, descoberta PostgreSQL,
tentativas duráveis e continuidade HITL protegida por lease/fencing. O
coordinator revalida o estado depois de adquirir ownership e não fabrica
aprovação, não reativa checkpoint consumido e não reporta recuperação quando a
persistência final falha.

## Acceptance gates

| Gate | Estado | Evidência |
| --- | --- | --- |
| DS006-G01 — DS-005 certificada | PASS | relatório DS-005 `COMPLETE` |
| DS006-G02 — contratos de recovery | PASS | core tipado e provider-neutral |
| DS006-G03 — descoberta | PASS | lote, ordem estável, digest e tenant no PostgreSQL |
| DS006-G04 — elegibilidade | PASS | precheck e revalidação sob lease |
| DS006-G05 — terminais protegidos | PASS | filtro SQL e policy fail-closed |
| DS006-G06 — ownership exclusivo | PASS | corrida async com um vencedor |
| DS006-G07 — fencing | PASS | owner obsoleto rejeitado |
| DS006-G08 — revalidação | PASS | checkpoint carregado/restaurado após aquisição |
| DS006-G09 — restart | PASS | tentativa incompleta seguida pela tentativa 2 |
| DS006-G10 — HITL | PASS | resolver externo e runtime autorizado |
| DS006-G11 — replay safety | PASS | consumo atômico único preservado |
| DS006-G12 — tentativas limitadas | PASS | limite persistente entre instâncias |
| DS006-G13 — falhas | PASS | timeout, persistência e isolamento do lote |
| DS006-G14 — cancelamento | PASS | propagação, registro best effort e release |
| DS006-G15 — isolamento | PASS | candidato, execução e tenant isolados |
| DS006-G16 — segurança | PASS | Bandit e pip-audit sem findings |
| DS006-G17 — multiprocesso | PASS | dois processos spawn e um consumo |
| DS006-G18 — performance | PASS | 30 amostras por operação |
| DS006-G19 — compatibilidade 1.x | PASS | APIs antigas opcionais e instalação limpa 3.12 |
| DS006-G20 — quality gates | PASS | lint, format, mypy, pytest, cobertura e builds |
| DS006-G21 — evidências | PASS | doze artefatos e ADR-006 |

## Limites preservados

- somente HITL com decisão externa possui invoker oficial nesta entrega;
- não há scheduler, retry temporizado, retenção ou purge;
- não há garantia exactly-once para efeitos externos;
- uma tentativa incompleta é auditável e consome o limite configurado.

## Decisão final

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-006

BASELINE                    1.0.1
TASK                        Execution Recovery Coordinator

DS005 CERTIFICATION         PASS
RECOVERY CONTRACT           PASS
CANDIDATE DISCOVERY         PASS
ELIGIBILITY                 PASS
TERMINAL STATE SAFETY       PASS
EXCLUSIVE OWNERSHIP         PASS
FENCING                     PASS
STATE REVALIDATION          PASS
RESTART RECOVERY            PASS
HITL INTEGRATION            PASS
REPLAY PROTECTION           PASS
ATTEMPT LIMITS              PASS
FAILURE HANDLING            PASS
CANCELLATION                PASS
MULTI_PROCESS               PASS
SECURITY                    PASS
BACKWARD COMPATIBILITY      PASS
PERFORMANCE BASELINE        PASS
QUALITY GATES               PASS
DOCUMENTATION               PASS

TESTS PASSED                1245
TESTS FAILED                0
POSTGRESQL TESTS            62
COVERAGE                    92.57%

ACCEPTANCE GATES            21/21 PASS
CRITICAL GAPS               0
HIGH GAPS                   0

FINAL DECISION              COMPLETE
NEXT TASK                   DS-007 (NOT STARTED)
```
