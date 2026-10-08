# Arquitetura da DS-010

`RedisCheckpointStore` reside em `atlas-agent-adapters`; o core mantém apenas
`CheckpointStore`. A composição é explícita no host e não consulta ambiente.

```text
AgentRuntime -> CheckpointStore (core)
                         ^
                         |
              RedisCheckpointStore
                         |
                cliente redis.asyncio
```

Cada token gera uma chave opaca e cada mutação executa um script Lua estático
de chave única. O adapter reutiliza `ExecutionCheckpoint.model_dump(mode="json")`
e valida novamente o modelo na recuperação. Não há estado global, lock local,
conexão no import ou dependência Redis no core.

O adapter oferece capabilities aditivas `read`, `compare_and_swap` e
`consume_authorized`. Lease/fencing Redis não é declarado: a capability leased
permanece ausente e o runtime bloqueia essa composição em vez de fingir
proteção cruzada com PostgreSQL.
