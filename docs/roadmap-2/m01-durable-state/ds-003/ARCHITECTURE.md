# Arquitetura da DS-003

## Escopo

A DS-003 adiciona concorrência otimista ao `PostgreSQLCheckpointStore` sem
alterar `CheckpointStore`, `ExecutionCheckpoint` ou `AgentRuntime`.

```text
Aplicação / coordenador autorizado
        │
        ├── read(token)
        │       └── PostgreSQLCheckpointSnapshot(checkpoint, revision)
        │
        └── compare_and_swap(token, checkpoint, expected_revision)
                │
                ▼
        UPDATE ... WHERE revision = expected
                │
          ┌─────┴─────┐
          │           │
       sucesso     zero linhas
          │           ├── ausente/expirado/consumido → not found
          │           ├── identidade divergente → invalid checkpoint
          │           └── revisão divergente → conflict
          ▼
      revision + 1
```

## Fronteiras

- A capability pertence a `atlas-agent-adapters[postgresql]`.
- Psycopg e SQL permanecem fora do core.
- O pool continua sendo criado, aberto e fechado pela aplicação.
- A garantia distribuída depende da transação e do lock de linha PostgreSQL.
- Não há estado de concorrência no processo Python.

## Compatibilidade

Os métodos `save()` e `consume()` não mudam. Aplicações 1.x que não utilizam a
capability nova observam o mesmo comportamento da DS-002. A migration 002
preenche registros existentes com revisão inicial 1.
