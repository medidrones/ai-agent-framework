# Certificação consolidada PostgreSQL

PostgreSQL foi revalidado em container real `postgres:16-alpine`, com banco
`atlas_test`, pela suíte completa de 15/10/2026.

| Área | Evidência | Resultado |
| --- | --- | --- |
| save/consume | integração real | PASS |
| concorrência e CAS | corridas multiprocessadas/assíncronas | PASS |
| autorização atômica | validação antes do commit | PASS |
| leases e fencing | stale owner rejeitado | PASS |
| recovery | tentativas duráveis e reconciliação | PASS |
| retenção/purge | revalidação transacional e auditoria | PASS |
| schema/migrations | contrato, drift, upgrade e rollback | PASS |
| durable HITL | decisão, auditoria e resume | PASS |
| performance | p95 máximo 909,109 ms a 500 workers | PASS |
| soak | 3.600,073 s; 1.096.355 ciclos | PASS |

O driver permanece opcional em `atlas-agent-adapters[postgresql]`; nenhuma
dependência PostgreSQL entrou no core. Não se declara exactly-once para efeitos
fora da transação do banco.

**Decisão:** `POSTGRESQL = VERIFIED`.
