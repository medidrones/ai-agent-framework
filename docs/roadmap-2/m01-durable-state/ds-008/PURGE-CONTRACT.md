# Contrato de purge

`PurgeAuthorization` exige principal explícito e a permissão
`checkpoint:purge`; `tenant_id` restringe o escopo. `CheckpointPurgeConfig`
limita `batch_size` a 1–1.000, `max_batches_per_run` a 1–100 e exige timeouts
positivos. `dry_run=True` é o padrão seguro.

Cada candidato gera exatamente um `PurgeItemResult`. Os totais de
`PurgeBatchResult` são validados contra os itens. Os outcomes são `PURGED`,
`SKIPPED`, `BLOCKED`, `FAILED` e `OUTCOME_UNKNOWN`.

`PURGED` significa commit confirmado ou resultado durável reconciliado. O
contrato não promete exactly-once para efeitos externos.
