# Transações PostgreSQL

A migration 003 cria `atlas_agent.checkpoint_leases`, constraints de estado e
índice parcial por expiração. `INSERT ... ON CONFLICT DO UPDATE` lineariza a
aquisição. Updates condicionais linearizam renew e release.

Todas as queries são parametrizadas. O pool pertence ao caller. Os contextos de
conexão confirmam operações bem-sucedidas e executam rollback em exceções ou
cancelamento. `CURRENT_TIMESTAMP` é a autoridade temporal; o relógio do worker
não participa da decisão de validade.

As migrations continuam imutáveis, serializadas por advisory lock e verificadas
por SHA-256 no registro `schema_migrations`.
