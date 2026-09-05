# Checkpoint e retomada

`ExecutionCheckpoint` é o contrato versionado e serializável usado para
retomar uma execução. Ele é diferente de `ExecutionSnapshot`: snapshot serve à
observabilidade; checkpoint contém fatos normativos para reconstrução.

## Conteúdo preservado

O checkpoint mantém:

- versão, modalidade `run` ou `stream` e identidade da execução;
- definição declarativa do agente, entrada e contexto;
- status `WAITING_FOR_APPROVAL`, mensagens e seleção do modelo;
- uso acumulado, contadores de turnos e ferramentas;
- eventos, transições e registros de chamadas já processadas;
- solicitação de aprovação e chamadas ainda pendentes;
- histórico de decisões, limites, budget e timeout restante;
- timestamps e metadados serializáveis.

Ele não contém instâncias de provider, ferramenta, executor, registry, clock,
lock ou callback. Também não serializa deadline monotônico absoluto,
credenciais ou o próprio token de retomada.

## Storage abstrato e token de uso único

O core define somente `CheckpointStore`:

```python
class CheckpointStore(Protocol):
    async def save(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
    ) -> None: ...

    async def consume(
        self,
        resume_token: ResumeToken,
    ) -> ExecutionCheckpoint: ...
```

`consume()` deve recuperar e invalidar o token atomicamente. Assim, duas
retomadas concorrentes não podem executar a mesma ação. Adapters concretos
devem implementar durabilidade, controle de acesso e atomicidade conforme sua
infraestrutura; o pacote core não fornece store em memória, filesystem, Redis
ou banco de dados.

Se uma ferramenta exigir aprovação sem um store injetado, a execução falha com
`approval_checkpoint_store_required`. Falha ao salvar produz
`checkpoint_save_failed`; não é retornada uma suspensão sem persistência.

## Restauração

```text
ResumeToken
  → CheckpointStore.consume()
  → validação da versão e das invariantes
  → ExecutionStateRestorer
  → ExecutionState
  → validação da decisão
  → revalidação de provider, ferramenta, permissões e limites
```

`ExecutionStateRestorer` reconstrói o lifecycle pelo histórico de transições e
restaura journal, mensagens, uso, contadores, seleção e aprovação pendente. A
factory de eventos começa na sequência seguinte. Versões desconhecidas e
checkpoints inconsistentes geram erros explícitos.

Não há nova seleção de modelo. Se o provider ou uma ferramenta declarada pelo
agente não estiver mais registrada, a retomada falha sem fallback.

## Semântica do timeout

Antes da suspensão, o checkpoint grava apenas
`remaining_timeout_seconds`. Na retomada, um novo deadline monotônico é criado
com essa duração. O tempo em que a decisão humana permanece pendente não
consome o timeout, mas o trabalho anterior já consumido não é recuperado.

Limites, budget e contadores também são reconstruídos sem reset. A aprovação em
si não incrementa turnos nem ferramentas; a ferramenta conta somente quando
sua execução realmente começa.

Consulte [aprovação humana](human-approval.md) para a policy, as decisões e o
pipeline de ferramentas.
