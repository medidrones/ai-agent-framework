# Atomicidade SQL

## Migration real

```sql
ALTER TABLE atlas_agent.checkpoints
    ADD COLUMN revision BIGINT NOT NULL DEFAULT 1,
    ADD COLUMN modified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT atlas_checkpoint_revision_positive CHECK (revision > 0);
```

## Compare-and-swap real

```sql
UPDATE atlas_agent.checkpoints
SET checkpoint_version = $1,
    payload = $2,
    expires_at = $3,
    modified_at = CURRENT_TIMESTAMP,
    revision = revision + 1
WHERE token_digest = $4
  AND revision = $5
  AND execution_id = $6
  AND agent_id = $7
  AND tenant_id IS NOT DISTINCT FROM $8
  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
RETURNING payload, revision;
```

Na execução Psycopg, os placeholders são `%s`; todos os valores permanecem
parametrizados. O predicado e o incremento pertencem à mesma instrução. O lock
de linha adquirido pelo PostgreSQL impede que dois writers confirmem a mesma
revisão esperada.

## Transação

O context manager de conexão confirma somente quando toda a operação termina
sem erro. Exceção do banco ou cancelamento causa rollback. Um trigger de teste
que falha antes do commit comprova que payload e revisão anteriores permanecem
intactos.

Não há retry automático quando o resultado do commit é ambíguo por falha de
conexão.
