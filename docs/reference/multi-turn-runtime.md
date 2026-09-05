# Runtime multi-turn com ferramentas

O `AgentRuntime` executa ciclos completos e provider-agnostic entre modelo e
ferramentas. O loop pertence exclusivamente ao runtime; `ModelProvider` nunca
executa tools e `ToolExecutor` nunca chama o modelo.

```text
ModelProvider
      ↓
ModelResponse(TOOL_CALL)
      ↓
ToolExecutor
      ↓
ToolExecutionResult
      ↓
ModelMessage(TOOL)
      ↓
próximo model turn
```

## Disponibilidade por agente

Ferramentas registradas não ficam automaticamente disponíveis. Cada agente
possui uma allowlist explícita e ordenada:

```python
agent = AgentDefinition(
    agent_id="support",
    name="Suporte",
    instructions="Ajude o usuário.",
    tool_names=("get_customer", "create_ticket"),
)
```

O runtime resolve todos os nomes durante a preparação. Um nome configurado mas
não registrado falha com `agent_tool_not_registered`. A ordem declarada define
a ordem de `ModelRequest.tools`, e duplicidades são rejeitadas no próprio
`AgentDefinition`. Agentes sem nomes não recebem tools.

Quando a allowlist não está vazia, o runtime acrescenta `TOOL_CALLING` às
capabilities obrigatórias da seleção. `PARALLEL_TOOL_CALLING` não é exigida:
múltiplas chamadas são processadas sequencialmente na ordem do modelo.

Há duas camadas independentes de autorização:

```text
AgentDefinition.tool_names
          ↓
allowlist do agente
          ↓
ExecutionIdentity.permissions
          ↓
execução da implementação
```

Uma tool registrada fora da allowlist nunca é executada e encerra o agente com
`tool_not_available_for_agent`. Uma tool disponível, mas sem permissões para a
identidade atual, produz resultado `DENIED` e pode ser explicada pelo modelo no
turn seguinte.

## Histórico da conversa

`ModelMessage` aceita `tool_calls` somente no papel `ASSISTANT`. O campo possui
default vazio para preservar compatibilidade. A resposta intermediária e os
resultados ficam no único histórico mantido por `ExecutionState`:

```text
SYSTEM
USER
ASSISTANT(tool_calls=(call-1, ...))
TOOL(tool_call_id=call-1)
ASSISTANT(resposta final)
```

Conteúdo textual retornado junto com tool calls também é preservado. Cada nova
invocação reconstrói `ModelRequest` a partir de `state.messages`, usa o mesmo
provider/model selecionado e recebe um `request_id` novo.

`ToolResultMessageMapper` serializa JSON compacto e determinístico em
`TextContent`. O payload contém somente `status`, conteúdo funcional de
`output` e os campos seguros `code`, `message` e `retryable` do erro. Timestamps,
metadata, permissões e detalhes internos não são enviados ao modelo.

## Execução e contadores

O `ToolExecutor` separa preparação de execução:

```text
resolve
  ↓
permission
  ↓
argument validation
  ↓
resultado controlado ou execução preparada
  ↓
check max_tool_calls
  ↓
increment tool_call_count
  ↓
Tool.execute()
```

`turn_count` cresce imediatamente antes de cada `generate()` ou `stream()`.
`tool_call_count` cresce somente quando `Tool.execute()` vai começar. Portanto,
tools desconhecidas, negadas, inválidas, fora da allowlist ou bloqueadas pelo
limite não contam. Uma implementação que começou e falhou ou foi cancelada
conta.

Resultados controlados `SUCCEEDED`, `FAILED`, `DENIED` e `INVALID_ARGUMENTS`
viram mensagens `TOOL`; uma falha operacional não encerra automaticamente o
agente. O modelo pode responder, escolher alternativa ou emitir uma nova
chamada. Não existe retry ou fallback invisível.

## Lifecycle e eventos

Um batch utiliza uma única passagem pelo lifecycle:

```text
RUNNING
  ↓
WAITING_FOR_TOOL
  ↓
EXECUTING_TOOL
  ↓
RUNNING
```

`EXECUTING_TOOL` representa o processamento do batch, inclusive autorização e
validação. Para cada chamada, `TOOL_REQUESTED` é emitido sem argumentos
completos; o payload contém apenas ID, nome e nomes das chaves. Quando a
implementação será chamada, há `TOOL_EXECUTION_STARTED`. Todo resultado
controlado produz `TOOL_EXECUTION_COMPLETED` com status e código de erro
opcional. As sequências permanecem contínuas por execução.

## Limites, budget e timeout

Antes de cada model turn, o runtime verifica `max_turns`. Depois de cada
resposta, agrega usage e verifica limites de tokens e budget antes de processar
tools. Dentro do batch, verifica `max_tool_calls` antes de cada execução
preparada. Um limite do runtime encerra o agente e não é devolvido ao modelo
como erro funcional.

O mesmo `ExecutionDeadline` monotônico cobre preparação, todos os model turns,
validações e execuções de tools. O prazo nunca é renovado. Timeout termina em
`TIMED_OUT`; cancelamento externo tenta registrar `CANCELLED` e repropaga
`asyncio.CancelledError`.

Aplicações que habilitam tools devem configurar `max_turns` e
`max_tool_calls`. O core não introduz limites ocultos; valores ausentes
continuam formalmente ilimitados.

## Proteção contra chamadas duplicadas

`ExecutionState` mantém `ToolCallRecord` frozen e serializável por execução.

| Situação | Comportamento |
| --- | --- |
| ID novo | processar e registrar o resultado |
| Mesmo ID, nome e argumentos | reutilizar resultado sem contar ou executar |
| Mesmo ID com nome diferente | falhar com `tool_call_id_conflict` |
| Mesmo ID com argumentos diferentes | falhar com `tool_call_id_conflict` |

A reutilização emite `TOOL_EXECUTION_COMPLETED` com `deduplicated=true`. Essa
proteção é estritamente local à execução em memória. Não é idempotência
distribuída, não sobrevive a reinício e não substitui `idempotency_key`.

## Streaming

`stream()` repete exclusivamente `ModelProvider.stream()` em todos os turns.
Cada turn possui seu próprio `ModelStreamAccumulator`; tools são processadas
entre streams e seus eventos entram no mesmo journal. `generate()` nunca é
usado como fallback. O consumidor recebe deltas do turn final e um único
`RuntimeResultItem` terminal.

## Aprovação no loop

Depois da permissão e da validação dos argumentos, cada chamada pode produzir
uma suspensão. A chamada ainda não incrementa `tool_call_count`; após uma
aprovação válida, o runtime revalida a ferramenta e o limite, executa a chamada
original e continua o mesmo batch. Chamadas sensíveis subsequentes geram novas
suspensões. Consulte [aprovação humana](human-approval.md).

## Memória no loop

A recuperação acontece uma única vez durante `LOADING_CONTEXT`, antes da
primeira chamada ao modelo. A mensagem `DEVELOPER` resultante permanece no
histórico da execução e é reutilizada em todos os turns completos ou
incrementais. Uma retomada por aprovação restaura essa mensagem do checkpoint e
não consulta o store novamente.

Depois de uma resposta final válida, uma `MemoryWritePolicy` pode produzir
candidatas. O runtime restringe essas candidatas aos tipos declarados em
`AgentDefinition.memory.write_types` e realiza escritas sequenciais antes de
concluir. Consulte [memória](memory.md).

## Fora do escopo

Não existem execução paralela de tools, retry, fallback, timeout específico de
tool, idempotência distribuída, storage concreto de checkpoint ou memória,
Knowledge/RAG ou guardrails. Dependências concretas continuam sendo injetadas
nos construtores das implementações de `Tool`, `CheckpointStore` e
`MemoryStore`.
