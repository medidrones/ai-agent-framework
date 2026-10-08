# Checkpoints duráveis no Redis

O `RedisCheckpointStore` é uma implementação opcional do contrato
`CheckpointStore`. Instale o extra e injete explicitamente o cliente:

```bash
pip install atlas-agent-adapters[redis]
```

```python
from redis.asyncio import Redis

from atlas_agents.adapters.checkpoints.redis import RedisCheckpointStore

client = Redis.from_url("rediss://redis.internal/0")
store = RedisCheckpointStore(client, namespace="produção:tenant-a")
```

O host continua responsável pelo cliente injetado. Para ownership pelo adapter,
use `RedisCheckpointStore.from_url(...)` e `async with` ou `aclose()`.

Save, leitura, compare-and-swap, lease/fencing e consumo são linearizados por
scripts Lua estáticos sobre uma única chave. Tokens e namespaces não aparecem
em texto claro no keyspace. Tombstones preservam proteção contra replay sem
reter o payload consumido.

Para ownership distribuído, adquira o lease pelo próprio store e passe-o para a
operação protegida:

```python
from datetime import timedelta

lease = await store.acquire_lease(
    resume_token=token,
    owner_id="worker-01",
    duration=timedelta(seconds=30),
)
checkpoint = await store.consume_authorized_leased(
    resume_token=token,
    lease=lease,
    authorize=validate_decision,
)
```

O lease Redis e o checkpoint usam a mesma autoridade e o mesmo hash slot. Não
combine lease PostgreSQL com checkpoint Redis esperando atomicidade. Em fluxos
que precisam reconciliar uma resposta perdida, use um `operation_id` estável em
`consume_authorized_identified` e consulte `reconcile_consumption` antes de
tentar novamente.

Redis standalone 7.4 com AOF foi certificado. Sentinel e Cluster não foram
testados e não fazem parte da matriz oficial da DS-011. A confirmação do Redis
não equivale, isoladamente, à durabilidade transacional do PostgreSQL.
