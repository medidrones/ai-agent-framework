# Relatório de certificação DS-004

## Identificação

- Roadmap: 2 — Ecosystem & Enterprise
- Módulo: M01 — Durable State
- Entrega: DS-004 — Atomic Resume Consumption & Replay Protection
- Baseline: Atlas `1.0.1`
- Branch: `medicode/ds-004-atomic-resume-consumption`
- Data: 2026-10-08
- DS-003: `COMPLETE`

## Resultado

A DS-004 introduz consumo autorizado transacional sem alterar o contrato
`CheckpointStore`. O adapter PostgreSQL valida modalidade, decisão e políticas
de identidade depois do `DELETE ... RETURNING` e antes do commit. Falha de
validação, payload inválido ou cancelamento provoca rollback; concorrentes
observam no máximo um commit vencedor.

O runtime detecta a capability estruturalmente. Stores 1.x permanecem
compatíveis pelo caminho histórico. A garantia termina no consumo da autorização
e não declara exactly-once para efeitos externos.

## Gates

| Gate | Estado | Evidência |
| --- | --- | --- |
| DS004-G01 — DS-003 certificada | PASS | relatório DS-003 |
| DS004-G02 — contrato público preservado | PASS | capability estrutural opcional |
| DS004-G03 — ponto de linearização | PASS | `LINEARIZATION-POINT.md` |
| DS004-G04 — consumo atômico | PASS | dez consumidores, um vencedor |
| DS004-G05 — multiprocesso | PASS | processos e pools independentes |
| DS004-G06/G07 — replay | PASS | token consumido não reutilizável |
| DS004-G08 — autorização | PASS | decisão/identidade antes do commit |
| DS004-G09 — ferramenta após aprovação | PASS | integração HITL real |
| DS004-G10 — falhas transacionais | PASS | rollback e restart |
| DS004-G11 — cancellation | PASS | cancelamento sob row lock |
| DS004-G12 — HITL | PASS | approve, reject e concorrência |
| DS004-G13 — compatibilidade 1.x | PASS | fallback para stores legados |
| DS004-G14 — segurança | PASS | Bandit e revisão sem vazamento |
| DS004-G15 — performance | PASS | baseline local registrada |
| DS004-G16 — quality gates | PASS | 1.204 testes e 92,91% |
| DS004-G17 — evidências | PASS | onze artefatos obrigatórios |

## Limitações preservadas

- não há exactly-once para ferramentas ou efeitos externos;
- perda de conexão após o commit pode produzir resultado ambíguo;
- o validator padrão confere o request, enquanto identidade/tenant/papéis
  exigem validator injetado pela aplicação;
- stores sem `consume_authorized()` preservam a semântica histórica 1.x;
- não há reativação automática depois de crash pós-consumo;
- desconhecido, expirado e já consumido permanecem externamente indistinguíveis
  por segurança e compatibilidade com a ADR-002; conflito de revisão continua
  sendo responsabilidade da capability CAS da DS-003;
- leases, ownership e recuperação coordenada pertencem à DS-005.

## Decisão final

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-004

BASELINE                  1.0.1
TASK                      Atomic Resume Consumption

DS003 CERTIFICATION       PASS
ATOMIC CONSUMPTION        PASS
REPLAY PROTECTION         PASS
MULTI_PROCESS             PASS
HITL INTEGRATION          PASS
TRANSACTION SAFETY        PASS
CANCELLATION              PASS
SECURITY                  PASS
BACKWARD COMPATIBILITY    PASS
PERFORMANCE BASELINE      PASS
QUALITY GATES             PASS

TESTS PASSED              1204
TESTS FAILED              0
POSTGRESQL TESTS          34
COVERAGE                  92.91%

FINAL DECISION            COMPLETE
NEXT TASK                 DS-005 (NOT STARTED)
```
