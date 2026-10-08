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
    PostgreSQLCheckpointLeaseManager,
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
    lease_manager = PostgreSQLCheckpointLeaseManager(pool)
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

Quando utilizado pelo `AgentRuntime`, o adapter expõe adicionalmente
`consume_authorized()`. A operação executa a validação síncrona da decisão e da
modalidade depois do `DELETE ... RETURNING`, mas antes do commit. Uma validação
inválida ou cancelada provoca rollback e mantém o checkpoint disponível para
uma decisão legítima. Essa capability é detectada estruturalmente; o contrato
público `CheckpointStore` continua contendo somente `save()` e `consume()`.

O callback de autorização não deve realizar I/O nem efeitos externos. Ele é
executado dentro da transação e deve apenas validar fatos do checkpoint e da
decisão. Validators customizados podem aplicar identidade, tenant, papéis e
políticas organizacionais sem transferir essas regras ao adapter PostgreSQL.

## Concorrência otimista

O adapter oferece uma capability aditiva para coordenadores que precisam
atualizar um checkpoint antes do consumo:

```python
snapshot = await checkpoint_store.read(resume_token)
updated = await checkpoint_store.compare_and_swap(
    resume_token=resume_token,
    checkpoint=new_checkpoint,
    expected_revision=snapshot.revision,
)
```

`revision` é uma revisão de armazenamento iniciada em 1 e independente de
`checkpoint_version`, que continua representando o formato do payload. Somente
um writer com a revisão esperada confirma a atualização; os demais recebem
`CheckpointConcurrencyConflictError`. O adapter não aplica retry automático.

## Lease, ownership e fencing

`PostgreSQLCheckpointLeaseManager` coordena ownership temporário usando o
relógio do PostgreSQL. O checkpoint deve existir e estar ativo. Uma aquisição
concorrente tem exatamente um vencedor; release e expiração permitem nova
aquisição com fencing token estritamente maior.

```python
from datetime import timedelta

lease = await lease_manager.acquire(
    checkpoint_id=checkpoint.execution_id,
    owner_id=worker_id,
    duration=timedelta(seconds=30),
)
try:
    snapshot = await checkpoint_store.compare_and_swap_leased(
        resume_token=resume_token,
        checkpoint=updated_checkpoint,
        expected_revision=current_revision,
        lease=lease,
    )
finally:
    await lease_manager.release(lease=lease)
```

Para o caminho HITL, `consume_authorized_leased()` combina autorização,
consumo atômico e validação do fencing token. As variantes com lease são
capabilities aditivas; métodos existentes permanecem compatíveis com Atlas
1.x. Um lease não protege efeitos em serviços externos que não implementem
fencing ou idempotência.

## Recovery de execuções

`PostgreSQLRecoveryCandidateRepository` descobre checkpoints não terminais em
lotes estáveis sem carregar payloads. `PostgreSQLRecoveryAttemptRecorder`
admite e conclui tentativas sob o fencing token corrente. A migration 004 cria
o histórico auditável correspondente.

O host compõe esses adapters com `ExecutionRecoveryCoordinator`, uma policy de
elegibilidade e um invoker. O Atlas fornece
`AuthorizedHITLRecoveryPolicy` e `AgentRuntimeRecoveryInvoker`; ambos exigem um
`RecoveryResumeRequestResolver` que entregue token e aprovação reais. O host
continua responsável pela frequência das chamadas, shutdown e obtenção segura
das decisões.

Consulte a [arquitetura da DS-006](../roadmap-2/m01-durable-state/ds-006/ARCHITECTURE.md)
e a [integração HITL](../roadmap-2/m01-durable-state/ds-006/HITL-RECOVERY.md).

## Retenção e operação

O parâmetro legado `retention` continua compatível. Para políticas explícitas,
use `CheckpointRetentionPolicy` em `retention_policy`: ela separa TTL HITL e
janelas de retenção de consumidos, expirados, terminais e recovery. O relógio
do PostgreSQL decide a fronteira (`agora >= expires_at`).

Cada consumo grava um tombstone sem payload na mesma transação. Para avaliar
limpeza, `PostgreSQLCheckpointRetentionRepository.classify()` retorna uma lista
limitada e isolada por tenant; não remove dados. Lease, recovery, legal hold,
incompatibilidade e retenção ativa bloqueiam a elegibilidade. O purge físico
com política DS-007 permanece reservado à DS-008. `ping()` verifica
disponibilidade sem expor configuração.

Consulte o [contrato da DS-007](../roadmap-2/m01-durable-state/ds-007/EXPIRATION-CONTRACT.md)
e as [regras de elegibilidade](../roadmap-2/m01-durable-state/ds-007/PURGE-ELIGIBILITY.md).

O payload do checkpoint pode conter mensagens, argumentos e metadata sensíveis.
Proteja backups, conexões, permissões e armazenamento com os controles da
plataforma. O adapter evita persistir o bearer token, mas não faz redaction nem
criptografia do payload da aplicação.
