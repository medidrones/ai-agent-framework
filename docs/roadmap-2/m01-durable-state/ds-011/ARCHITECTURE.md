# Arquitetura da DS-011

O `AgentRuntime` continua responsável pela orquestração e o componente HITL
continua responsável pela autorização. O `RedisCheckpointStore` implementa a
persistência, a exclusão distribuída e a proteção contra replay sem introduzir
Redis no core.

```text
Runtime/HITL -> capability aditiva -> RedisCheckpointStore -> script Lua -> Redis
                                       | checkpoint + lease + receipt |
                                       +-------- mesma chave ---------+
```

Cada checkpoint ocupa uma chave opaca com hash tag própria. Save, read, CAS,
lease, fencing, consumo e reconciliação não usam locks Python nem estado global.
O deployment fornece cliente, namespace, credenciais e política de retenção.

Não existe transação entre PostgreSQL e Redis. Composição protegida usa lease
Redis com checkpoint Redis ou permanece bloqueada.
