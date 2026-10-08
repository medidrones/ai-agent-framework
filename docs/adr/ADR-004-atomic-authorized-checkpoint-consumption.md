# ADR-004 — Consumo atômico autorizado de checkpoints

## Contexto

O contrato 1.x define `CheckpointStore.consume()` como consumo destrutivo e
atômico. A DS-002 comprovou um único vencedor no PostgreSQL, mas o runtime
validava a decisão de aprovação somente após o retorno de `consume()`. Assim,
uma decisão incompatível consumia o token antes de ser rejeitada.

Alterar `CheckpointStore` quebraria implementações existentes. Realizar uma
leitura seguida de consumo criaria uma janela TOCTOU entre validação e remoção.

## Decisão

O runtime detecta estruturalmente a capability opcional
`consume_authorized(resume_token, authorize)`. No adapter PostgreSQL:

1. `DELETE ... RETURNING` bloqueia e remove logicamente a linha na transação;
2. o payload é validado;
3. o callback síncrono valida modalidade, decisão e políticas de identidade;
4. somente então a saída do contexto confirma o commit.

Qualquer exceção ou cancelamento anterior ao commit provoca rollback. O callback
não pode realizar I/O ou efeitos externos. O ponto de linearização observável é
o commit da transação que confirma o `DELETE`.

## Compatibilidade

`CheckpointStore`, `ExecutionCheckpoint`, `ApprovalDecision` e as assinaturas
públicas de `AgentRuntime.resume()` e `resume_stream()` permanecem inalterados.
Stores sem a capability continuam no caminho 1.x: consumo seguido de validação.

## Consequências

- uma decisão inválida não destrói o checkpoint no PostgreSQL;
- consumidores concorrentes continuam tendo no máximo um vencedor;
- decisão rejeitada válida encerra a retomada e consome o token uma única vez;
- perda de conexão após o commit pode produzir resultado ambíguo;
- a garantia não equivale a exactly-once para ferramentas ou efeitos externos;
- claim/ack, leases e recuperação após crash continuam fora da DS-004.
