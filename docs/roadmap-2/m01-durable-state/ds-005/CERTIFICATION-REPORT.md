# Relatório de certificação DS-005

## Identificação

- Roadmap: 2 — Ecosystem & Enterprise
- Módulo: M01 — Durable State
- Entrega: DS-005 — Checkpoint Lease & Ownership
- Baseline: Atlas `1.0.1`
- Branch: `medicode/ds-005-checkpoint-lease-ownership`
- Data: 2026-10-08
- DS-004: `COMPLETE`

## Resultado

A DS-005 implementa contrato provider-neutral e adapter PostgreSQL com
aquisição, renovação, release, expiração e readquisição atômicas. O contador de
fencing permanece durável após release e cada nova geração é estritamente
maior. CAS e consumo autorizado possuem variantes aditivas que validam owner,
token e expiração na mesma instrução SQL da mutação protegida.

## Acceptance gates

| Gate | Estado | Evidência |
| --- | --- | --- |
| DS005-G01 — DS-004 certificada | PASS | relatório DS-004 `COMPLETE` |
| DS005-G02 — contrato de lease | PASS | core provider-neutral e imutável |
| DS005-G03 — aquisição atômica | PASS | `INSERT ... ON CONFLICT` e PostgreSQL real |
| DS005-G04 — ownership exclusivo | PASS | concorrência com um vencedor |
| DS005-G05 — renovação | PASS | owner/token/expiração condicionais |
| DS005-G06 — liberação | PASS | release e double release controlado |
| DS005-G07 — expiração | PASS | relógio PostgreSQL e readquisição |
| DS005-G08 — fencing monotônico | PASS | 30 gerações e cenário de expiração |
| DS005-G09 — stale owner | PASS | CAS e consumo rejeitados atomicamente |
| DS005-G10 — multiprocesso | PASS | dois processos `spawn` e pools independentes |
| DS005-G11 — DS-003 preservada | PASS | CAS e conflitos de revisão |
| DS005-G12 — DS-004 preservada | PASS | consumo autorizado e replay |
| DS005-G13 — HITL preservado | PASS | regressão integral do runtime |
| DS005-G14 — segurança | PASS | Bandit, queries parametrizadas e erros seguros |
| DS005-G15 — cancellation | PASS | rollback e propagação |
| DS005-G16 — performance | PASS | 30 amostras por operação |
| DS005-G17 — compatibilidade | PASS | APIs 1.x preservadas e instalação limpa 3.12 |
| DS005-G18 — quality gates | PASS | lint, format, mypy, pytest, coverage e builds |
| DS005-G19 — evidências | PASS | onze artefatos e ADR-005 |

## Limites preservados

- não há garantia exactly-once para efeitos externos;
- owner ID não substitui identidade ou autorização;
- recuperação automática e coordenação pertencem à DS-006;
- stores 1.x e métodos PostgreSQL anteriores continuam válidos sem exigir lease.

## Decisão final

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-005

BASELINE                  1.0.1
TASK                      Checkpoint Lease & Ownership

DS004 CERTIFICATION       PASS
LEASE CONTRACT            PASS
ATOMIC ACQUIRE            PASS
EXCLUSIVE OWNERSHIP       PASS
RENEW                     PASS
RELEASE                   PASS
EXPIRATION                PASS
FENCING TOKENS            PASS
STALE OWNER REJECTION     PASS
MULTI_PROCESS             PASS
DS003 REGRESSION          PASS
DS004 REGRESSION          PASS
HITL REGRESSION           PASS
SECURITY                  PASS
CANCELLATION              PASS
PERFORMANCE BASELINE      PASS
BACKWARD COMPATIBILITY    PASS
QUALITY GATES             PASS

TESTS PASSED              1223
TESTS FAILED              0
POSTGRESQL TESTS          54
COVERAGE                  92.92%

FINAL DECISION            COMPLETE
NEXT TASK                 DS-006 (NOT STARTED)
```
