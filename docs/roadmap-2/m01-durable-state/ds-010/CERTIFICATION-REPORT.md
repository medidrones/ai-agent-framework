# Relatório de certificação DS-010

## Identificação

- Roadmap: 2 — Ecosystem & Enterprise
- Módulo: M01 — Durable State
- Entrega: DS-010 — RedisCheckpointStore
- Baseline: Atlas `1.0.1`
- DS-009: `COMPLETE`, 28/28 gates
- Backend certificado: Redis 7.4.11 standalone com AOF e `noeviction`

## Resultado

A DS-010 adicionou um backend Redis opcional sem alterar o contrato público do
core. Save, read, CAS e consumo foram linearizados por scripts Lua estáticos;
namespace e token permanecem opacos; tombstones preservam replay protection;
TTL físico não antecipa retenção; HITL funciona após restart do processo; e a
recuperação após restart Redis foi comprovada com AOF.

Sentinel e Cluster não foram testados nem declarados como suportados. A
capability lease/fencing Redis permanece bloqueada e será aprofundada somente
em tarefa formal posterior. Essas limitações não reduzem as garantias do
`CheckpointStore` implementado.

## Acceptance gates

| Gate | Estado | Evidência |
| --- | --- | --- |
| G01 | PASS | relatório DS-009: COMPLETE, 28/28 |
| G02–G05 | PASS | store, contrato, save/read e restart de processo |
| G06–G09 | PASS | JSON v1, schema, keyspace e tenant isolation |
| G10–G12 | PASS | CAS Lua, consumo único e tombstone |
| G13–G14 | PASS | relógio Redis, TTL físico e retenção separados |
| G15–G17 | PASS | restart de processo, restart AOF e HITL |
| G18–G20 | PASS | falhas tipadas, cancellation e ownership |
| G21–G22 | PASS | auditorias e dependência Redis fora do core |
| G23–G24 | PASS | baseline 1k/16k/256k e 17 testes Redis reais |
| G25–G28 | PASS | compatibilidade 1.x, gates, packaging e 13 artefatos |

## Decisão final

```text
ATLAS AGENT FRAMEWORK
ROADMAP 2 — M01 — DS-010

BASELINE                    1.0.1
TASK                        RedisCheckpointStore

DS009 CERTIFICATION         PASS
REDIS STORE                 PASS
CHECKPOINT CONTRACT         PASS
SAVE / READ                 PASS
SERIALIZATION               PASS
SCHEMA VERSION              PASS
KEYSPACE ISOLATION          PASS
TENANT ISOLATION            PASS
OPTIMISTIC CONCURRENCY      PASS
ATOMIC CONSUMPTION          PASS
REPLAY PROTECTION           PASS
TTL                         PASS
RETENTION / TOMBSTONES      PASS
PROCESS RESTART             PASS
REDIS RESTART               PASS
HITL                        PASS
CONNECTION FAILURES         PASS
CANCELLATION                PASS
RESOURCE OWNERSHIP          PASS
SECURITY                    PASS
CORE ISOLATION              PASS
PERFORMANCE BASELINE        PASS
REDIS INTEGRATION TESTS     PASS
BACKWARD COMPATIBILITY      PASS
QUALITY GATES               PASS
PACKAGING                   PASS
DOCUMENTATION               PASS

ACCEPTANCE GATES            28/28 PASS

TESTS PASSED                1380
TESTS FAILED                0
TESTS SKIPPED               0
COVERAGE                    92.89%

CRITICAL GAPS               0
HIGH BLOCKING GAPS          0

FINAL DECISION              COMPLETE
NEXT TASK                   DS-011 (NOT STARTED)
```

## Limitações preservadas

- não há exactly-once para efeitos externos;
- confirmação Redis depende de persistência, replicação e failover do deployment;
- resultado de consumo pode ser tipado como desconhecido após perda de resposta;
- RDB isolado, Sentinel e Cluster não foram certificados;
- lease/fencing Redis não está disponível e não é emulado com autoridade externa.
