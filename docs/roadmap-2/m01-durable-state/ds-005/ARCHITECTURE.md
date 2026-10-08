# Arquitetura DS-005

A DS-005 adiciona ownership temporário sem alterar `CheckpointStore` ou
`AgentRuntime`. O core define modelos e protocolo; o pacote de adapters contém
SQL, migration e implementação PostgreSQL.

```text
Recovery consumer (DS-006 futura)
        │
        ├── CheckpointLeaseManager (core)
        │       └── PostgreSQLCheckpointLeaseManager
        │
        └── PostgreSQLCheckpointStore
                ├── compare_and_swap_leased()
                └── consume_authorized_leased()
                         │
                         ▼
                 PostgreSQL: revision + lease + fencing
```

`checkpoint_id` corresponde a `ExecutionCheckpoint.execution_id`. A tabela de
leases não possui cascade de exclusão: a linha liberada preserva a geração
monotônica. A elegibilidade é sempre confirmada contra um checkpoint ativo.
