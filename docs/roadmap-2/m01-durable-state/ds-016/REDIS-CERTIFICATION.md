# Certificação consolidada Redis

Redis foi revalidado em container real `redis:7.4-alpine`, com AOF habilitado e
`appendfsync=always`, pela suíte completa de 15/10/2026.

| Área | Evidência | Resultado |
| --- | --- | --- |
| save/consume | scripts Lua e integração real | PASS |
| consumo autorizado | validação e mutação no mesmo hash | PASS |
| concorrência/CAS | único vencedor e revisão | PASS |
| leases/fencing | mesma autoridade e mesmo hash slot | PASS |
| tentativa identificada | `operation_id` reconciliável | PASS |
| durable HITL | fluxo PostgreSQL-boundary/Redis-store | PASS |
| performance | p95 máximo 533,686 ms a 500 workers | PASS |
| soak | 3.600,056 s; 1.358.054 ciclos | PASS |

## Limitações declaradas

A garantia depende da configuração de persistência do Redis. Cluster e Sentinel
não foram certificados e não são anunciados. Fencing somente é válido quando
lease e checkpoint compartilham a mesma autoridade Redis. Efeitos externos
continuam exigindo idempotência ou fencing próprio.

**Decisão:** `REDIS = VERIFIED_WITH_DECLARED_LIMITS`.
