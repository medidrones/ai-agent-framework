# Adapter orientado a eventos

O adapter de eventos é independente de broker. `ExecutionCommandConsumer`
recebe um `MessageEnvelope`, contexto confiável da entrega, publisher e serviço
de execução; ele não conecta, consome, confirma ou encerra clientes de Kafka,
RabbitMQ, SQS ou outro produto.

## Envelope e comandos

O envelope contém `message_id`, tipo, versão de schema, correlação, causação,
timestamp com fuso e payload JSON. Os comandos aceitos são:

- `execution.execute` com `ExecuteAgentCommand`;
- `execution.resume` com `ResumeExecutionCommand`.

Identidade não pertence ao payload. Um adapter específico de broker autentica a
origem e entrega `TrustedMessageContext`; `MessagePrincipalResolver` transforma
somente esse contexto em principal.

Para fixtures e brokers que já fornecem um `TransportPrincipal` autenticado,
`TrustedContextPrincipalResolver` é a implementação pública mínima. Ela nunca
consulta claims presentes no payload do comando.

Schemas de referência estão versionados para o
[envelope](schemas/message-envelope-v1.schema.json), o
[comando de execução](schemas/execute-agent-command-v1.schema.json) e o
[comando de retomada](schemas/resume-execution-command-v1.schema.json). O
`message_type` determina qual schema deve validar o payload.

## Publicação e confirmação

O modo padrão `terminal_only` publica um evento `execution.<status>` após o
resultado e usa `message_id` como chave de idempotência. O modo opt-in
`stream_events` publica cada item como `execution.stream`, aumentando volume e
exigindo que consumidores tolerem duplicatas.

`MessageProcessingResult` separa acknowledge de retry. Payload, tipo ou versão
inválidos não são retryable. Indisponibilidade transitória do publisher solicita
redelivery. A aplicação específica do broker decide ack/nack, DLQ, retry,
backoff, particionamento e ordenação.

Mensageria normalmente oferece at-least-once. O store em memória não é durável,
e nem execução nem publicação formam uma transação única. Para produção, use
idempotência persistente e, quando necessário, inbox/outbox transacional. O
Atlas não declara exactly-once.
