# Checkpoints PostgreSQL

O `PostgreSQLCheckpointStore` é a implementação opcional do contrato
`CheckpointStore` para execuções HITL duráveis. Ele pertence à distribuição
`atlas-agent-adapters`; o core continua sem dependências de banco de dados.

## Instalação

```bash
pip install atlas-agent-adapters[postgresql]
```

## Composição e ciclo de vida

A aplicação é proprietária do pool e deve abri-lo e fechá-lo explicitamente.
O adapter não lê variáveis de ambiente, não cria conexões globais e não encerra
o pool recebido.

```python
from psycopg_pool import AsyncConnectionPool

from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointStore,
)

pool = AsyncConnectionPool(
    "postgresql://atlas:senha@localhost/atlas",
    min_size=1,
    max_size=10,
    open=False,
)

await pool.open(wait=True)
try:
    await PostgreSQLCheckpointMigrator(pool).migrate()
    checkpoint_store = PostgreSQLCheckpointStore(
        pool,
        token_hmac_key=segredo_hmac_de_32_bytes,
    )
    runtime = AgentRuntime(
        # demais dependências explícitas
        checkpoint_store=checkpoint_store,
    )
finally:
    await pool.close()
```

`token_hmac_key` deve ser obtido pelo composition root da aplicação e possuir ao
menos 32 bytes. Quando configurada, a chave produz um digest HMAC-SHA-256 do
token. Sem ela, o store utiliza SHA-256. O valor original do token nunca é
persistido.

## Migrations

Execute `PostgreSQLCheckpointMigrator.migrate()` antes de servir tráfego. As
migrations são versionadas, imutáveis, verificadas por checksum e serializadas
por advisory lock transacional. A versão inicial cria o schema `atlas_agent`,
a tabela de controle `schema_migrations` e a tabela `checkpoints`.

Não edite uma migration já aplicada. Uma divergência de checksum interrompe o
startup com `PostgreSQLMigrationError`.

## Semântica de consumo

`save()` é create-only: uma colisão de token falha sem sobrescrever o registro.
`consume()` executa `DELETE ... RETURNING` em uma transação, de modo que apenas
um consumidor concorrente recebe o checkpoint. Tokens desconhecidos, expirados
ou já consumidos produzem a mesma resposta segura.

Essa garantia é **at-most-once para a autorização de retomada**. Ela não oferece
exactly-once para efeitos externos executados depois do consumo. Uma falha entre
o consumo e o efeito da ferramenta permanece uma fronteira arquitetural
documentada na ADR-002.

O cancelamento de uma operação pendente causa rollback da transação. Um payload
corrompido é consumido e rejeitado de forma fail-closed, preservando o contrato
1.x, que valida o checkpoint após o consumo.

## Retenção e operação

O parâmetro opcional `retention` limita a vida do registro a partir de
`checkpoint.updated_at`. Se a aprovação também possuir expiração, prevalece a
data mais próxima. `purge_expired(batch_size=1000)` remove lotes concorrentes
com `SKIP LOCKED`; `ping()` verifica disponibilidade sem expor a configuração.

O payload do checkpoint pode conter mensagens, argumentos e metadata sensíveis.
Proteja backups, conexões, permissões e armazenamento com os controles da
plataforma. O adapter evita persistir o bearer token, mas não faz redaction nem
criptografia do payload da aplicação.
