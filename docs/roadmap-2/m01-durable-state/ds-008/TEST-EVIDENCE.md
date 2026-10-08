# Evidências de teste da DS-008

## PostgreSQL real

A suíte `test_postgresql_checkpoint_purge.py` cobre banco vazio, limite,
ordenação, dry-run, purge, retenção, lease, recovery, legal hold, schema e
política incompatíveis, tenants, dois workers, dois processos, fencing,
idempotência, tombstone vencido, rollback de auditoria, cancellation,
reconciliação, corrida com lease, row lock, corrida com resume, cenário E2E de
100 registros e performance. Resultado focado: `22 passed`.

No E2E: 100 iniciais, 40 elegíveis, 40 removidos, 60 preservados, 40
tombstones, zero exclusões não autorizadas e zero duplicações.

## Rastreabilidade T01–T40

- T01–T04: vazio, limites, ordem e elegível;
- T05–T11: ativo/retenção/lease/recovery/legal hold/schema/revalidação;
- T12–T18: workers, resume/recovery, tombstone, replay, fencing, idempotência;
- T19–T24: rollback, reconciliação, tombstone/auditoria e locks;
- T25–T30: cancellation, falha controlada, tenant, benchmark, regressão e API;
- T31–T34: advisory lock compartilhado, renovação/retention/legal hold sob row lock;
- T35: reconciliação por IDs após mutação;
- T36–T38: processos, reinício idempotente e tombstone vencido;
- T39–T40: auditoria transacional e observabilidade fail-open.

Os quality gates globais e números finais ficam no relatório de certificação.
