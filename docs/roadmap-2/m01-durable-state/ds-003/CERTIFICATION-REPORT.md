# Relatório de certificação DS-003

## Identificação

- Roadmap: 2 — Ecosystem & Enterprise
- Módulo: M01 — Durable State
- Entrega: DS-003 — Checkpoint Optimistic Concurrency
- Baseline: Atlas `1.0.1`
- Commit-base integrado: `31e63364a580d13687e76df18071c1bce7846013`
- Branch: `medicode/ds-003-checkpoint-optimistic-concurrency`
- Data: 2026-10-08
- DS-001: `CERTIFIED`
- DS-002: `COMPLETE`

## Resultado

A DS-003 adiciona compare-and-swap por revisão ao adapter PostgreSQL. A revisão
de armazenamento é independente do `checkpoint_version`, inicia em 1 e avança
atomicamente no SQL. Escritores concorrentes com a mesma revisão não produzem
lost update: somente um confirma, enquanto os demais recebem
`CheckpointConcurrencyConflictError` com informações seguras.

A extensão é aditiva. `CheckpointStore`, `ExecutionCheckpoint`, `consume()` e
`AgentRuntime` não foram modificados. Aplicações 1.x existentes mantêm o
comportamento certificado pela DS-002.

## Gates de aceitação

| Gate | Estado | Evidência |
| --- | --- | --- |
| DS003-G01 — DS-002 certificada | PASS | relatório DS-002 com `FINAL DECISION COMPLETE` |
| DS003-G02 — estratégia de versão | PASS | `VERSIONING-SEMANTICS.md` e ADR-003 |
| DS003-G03 — compare-and-swap | PASS | SQL condicionado por token, revisão e identidade |
| DS003-G04 — lost updates impedidos | PASS | testes async e multiprocess com um único vencedor |
| DS003-G05 — conflitos tipados | PASS | erro aditivo com ID e revisões seguras |
| DS003-G06 — concorrência entre processos | PASS | dois processos `spawn` e pools independentes |
| DS003-G07 — update/consume race | PASS | conexões independentes e barreira PostgreSQL |
| DS003-G08 — rollback | PASS | falha por trigger preservou payload e revisão |
| DS003-G09 — cancelamento | PASS | `CancelledError`, rollback e cleanup comprovados |
| DS003-G10 — replay safety | PASS | consumido não pode ser atualizado ou reativado |
| DS003-G11 — compatibilidade 1.x | PASS | capability somente no adapter; core inalterado |
| DS003-G12 — security review | PASS | SQL parametrizado, erros seguros e Bandit sem findings |
| DS003-G13 — quality gates | PASS | 1.190 testes, 92,87%, Ruff, mypy e builds |
| DS003-G14 — documentação | PASS | oito artefatos obrigatórios e ADR-003 |

## Decisões e limitações

- `checkpoint_version` permanece reservado ao formato do payload.
- `revision` é privada à persistência PostgreSQL e não foi adicionada ao core.
- Não há retry automático de conflito.
- Consumido, desconhecido e expirado preservam a semântica segura de not found
  quando a API 1.x não permite distinção.
- A garantia depende do uso da API do adapter; acesso SQL direto deve ser
  protegido por menor privilégio.
- CAS protege estado persistido, mas não cria exactly-once para efeitos
  externos.
- A DS-004 não foi iniciada.

## Decisão final

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-003

BASELINE                  1.0.1
TASK                      Checkpoint Optimistic Concurrency

DS002 CERTIFICATION       PASS
VERSIONING                PASS
COMPARE_AND_SWAP          PASS
LOST_UPDATE_PROTECTION    PASS
CONFLICT_ERRORS           PASS
MULTI_PROCESS             PASS
UPDATE_CONSUME_RACE       PASS
ROLLBACK                  PASS
CANCELLATION              PASS
REPLAY_SAFETY             PASS
BACKWARD_COMPATIBILITY    PASS
SECURITY                  PASS
QUALITY_GATES             PASS

TESTS PASSED              1190
TESTS FAILED              0
POSTGRESQL TESTS          30
COVERAGE                  92.87%

FINAL DECISION            COMPLETE
NEXT TASK                 DS-004 (NOT STARTED)
```
