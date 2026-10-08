# Arquitetura da DS-008

```text
Host autorizado
  -> CheckpointPurgeCoordinator (core)
    -> CheckpointPurgeRepository (contrato)
      -> PostgreSQLCheckpointPurgeRepository
        -> PostgreSQL: locks + revalidação + tombstone + DELETE + auditoria
```

O core permanece independente de PostgreSQL. O host agenda chamadas; import,
startup e configuração não iniciam purge. A política certificada na DS-007 é
injetada e reutilizada pelo mesmo `CheckpointRetentionClassifier`.

O coordinator cria um `purge_run_id`, limita lote e número de lotes e registra
observabilidade fail-open. O adapter é a autoridade sobre tempo e commit.
