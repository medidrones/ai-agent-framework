# ADR-003 — Capability de concorrência otimista PostgreSQL

## Contexto

O contrato público `CheckpointStore` do Atlas 1.x possui somente `save()` e
`consume()`. A DS-002 implementou esse contrato com consumo destrutivo atômico,
mas não criou leitura não destrutiva nem atualização condicional. Alterar as
assinaturas do core quebraria implementações existentes.

O campo `checkpoint_version` já persistido representa a versão do formato de
`ExecutionCheckpoint`. Ele não é uma revisão de armazenamento e não pode ser
incrementado a cada atualização.

## Decisão

O adapter PostgreSQL oferece uma capability aditiva e específica:

- `read(token)` devolve um `PostgreSQLCheckpointSnapshot` com payload e
  `revision`;
- `compare_and_swap(token, checkpoint, expected_revision)` atualiza somente a
  linha ativa cuja revisão corresponde ao valor esperado;
- a coluna `revision BIGINT` começa em 1 e é incrementada pelo próprio SQL;
- `CheckpointConcurrencyConflictError` diferencia revisão obsoleta de falha de
  infraestrutura e expõe apenas identificador e revisões seguras;
- `consume()` permanece inalterado e continua sendo a implementação do contrato
  mínimo do core.

A garantia é fornecida pelo PostgreSQL, sem `asyncio.Lock`, `threading.Lock` ou
estado global. Não existe retry automático para conflitos.

## Consequências

- contratos e implementações de `CheckpointStore` existentes permanecem
  compatíveis;
- consumidores que precisam de CAS dependem explicitamente do adapter
  PostgreSQL;
- `revision` e `checkpoint_version` têm ciclos de vida independentes;
- atualização e consumo serializam no lock da mesma linha e produzem somente
  os resultados documentados na DS-003;
- consumo continua sem parâmetro de revisão porque o contrato 1.x não o exige;
- a ADR não introduz exactly-once para efeitos externos nem antecipa a DS-004.
