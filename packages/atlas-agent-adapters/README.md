# atlas-agent-adapters

Adapters externos opcionais para REST, gRPC, mensageria e persistência
PostgreSQL ou Redis de checkpoints.

Instale a integração PostgreSQL com:

```bash
pip install atlas-agent-adapters[postgresql]
```

Migrations são administrativas e nunca executadas no import. Depois de
provisionar o schema explicitamente, use o checker somente leitura no readiness:

```python
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLSchemaCompatibilityChecker,
)

await PostgreSQLCheckpointMigrator(pool).migrate()
schema = await PostgreSQLSchemaCompatibilityChecker(pool).check()
```

O resultado diferencia schema compatível, drift, versão não suportada e banco
não inicializado, sem carregar payloads nem realizar reparo automático.

Instale a integração Redis com:

```bash
pip install atlas-agent-adapters[redis]
```

O host deve injetar o cliente assíncrono e fornecer um namespace explícito:

```python
from redis.asyncio import Redis

from atlas_agents.adapters.checkpoints.redis import RedisCheckpointStore

client = Redis.from_url("rediss://redis.internal/0")
checkpoint_store = RedisCheckpointStore(client, namespace="produção:tenant-a")
```

O adapter não lê `REDIS_URL`, não fecha clientes injetados e usa scripts Lua
estáticos para save, atualização condicional e consumo único. A durabilidade
depende da configuração de AOF/RDB, replicação e eviction do serviço Redis.

Este pacote integra o ecossistema modular Atlas Agent Framework. Consulte a
[documentação oficial](https://github.com/Medicode/ai-agent-framework/tree/main/docs)
para instalação, compatibilidade e APIs públicas.
