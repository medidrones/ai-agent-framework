# M01 — Durable State

## Status formal

```text
M01 TASKS               DS-001–DS-016 COMPLETE
TECHNICAL CERTIFICATION PASS
OWNER SIGN-OFFS         5/5 PASS
M01 DECISION            CERTIFIED
STABLE VERSION          1.1.0
PUBLICATION              PUBLISHED
P0/P1 OPEN              0/0
NEXT MILESTONE          M02 — IN_PROGRESS
```

O M01 introduziu Durable State de forma aditiva, preservando o contrato público
`CheckpointStore` e isolando dependências de PostgreSQL e Redis na distribuição
`atlas-agent-adapters`.

## Entregas

| Tarefas | Escopo |
| --- | --- |
| DS-001 | certificação do contrato de persistência |
| DS-002–DS-004 | PostgreSQL, concorrência otimista e consumo atômico |
| DS-005–DS-009 | ownership, fencing, recovery, retenção, purge e schema |
| DS-010–DS-011 | Redis e consistência distribuída |
| DS-012 | recovery após falhas e crashes |
| DS-013 | restart e recuperação em Kubernetes |
| DS-014 | HITL durável |
| DS-015 | performance e carga |
| DS-016 | auditoria, sign-offs e certificação final |

## Garantias certificadas

- persistência PostgreSQL transacional e migrations versionadas;
- operações Redis atômicas, com limites de durabilidade declarados;
- compare-and-swap, leases e fencing contra workers obsoletos;
- consumo autorizado no máximo uma vez e proteção contra replay;
- recovery coordenado após restart, crash e substituição de pods;
- HITL durável com validação de identidade, decisão e ownership;
- retenção, tombstones e purge transacional;
- compatibilidade retroativa com os contratos Atlas 1.x;
- gates de segurança, qualidade, desempenho e distribuição aprovados.

A certificação não declara exactly-once para efeitos externos. Esses efeitos
devem usar idempotência e reconciliação na aplicação.

## Evidências

- [Certificação final do M01](ds-016/M01-FINAL-CERTIFICATION.md)
- [Relatório de certificação](ds-016/M01-CERTIFICATION-REPORT.md)
- [Decisão final da DS-016](ds-016/FINAL-DECISION.md)
- [Registro dos cinco sign-offs](ds-016/SIGN-OFF-RECORD.md)
- [Matriz de rastreabilidade](ds-016/TASK-TRACEABILITY-MATRIX.md)
- [Quality gates](ds-016/QUALITY-GATES.md)
- [Notas da versão 1.1.0](../../release/releases/1.1.0.md)

Os documentos da DS-016 são evidências congeladas do gate anterior à release.
Por isso, referências como `RELEASE ACTION NOT_EXECUTED` continuam corretas no
contexto histórico e são sucedidas pelos registros de promoção e publicação.

## Continuidade

O M01 está encerrado. O marco seguinte é o M02 — Distributed Agent
Orchestration & Execution,
que exige especificação e autorização independentes antes de qualquer mudança.
