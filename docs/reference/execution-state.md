# Estado de execução

`ExecutionState` é a fonte de verdade mutável e controlada de uma única
execução. Ele reúne definição, entrada, contexto, lifecycle, mensagens,
seleção de modelo, uso, contadores, eventos e resultado sem realizar I/O.

```text
AgentDefinition
      │
AgentInput
      │
AgentContext
      │
      ▼
ExecutionState
      │
      ├── ExecutionLifecycle
      ├── ModelSelectionResult
      ├── ModelMessage[]
      ├── Usage
      ├── AgentEvent[]
      ├── turn_count / tool_call_count
      ├── output
      └── error
      │
      ├── snapshot() ──▶ ExecutionSnapshot
      └── to_result() ─▶ AgentResult
```

## API pública

```python
state = ExecutionState(
    execution_id=context.execution_id,
    agent=definition,
    input_data=input_data,
    context=context,
)

state.transition_to(ExecutionStatus.VALIDATING_INPUT)
state.add_message(message)
state.set_model_selection(selection)
state.increment_turn()
state.increment_tool_calls(2)
state.add_model_usage(model_usage)
state.record_event(event)

snapshot = state.snapshot()
```

O status não possui setter. `transition_to()` delega integralmente a validação
para `ExecutionLifecycle` e expõe seu histórico por `transitions`, sem manter
uma segunda lista. `complete()`, `fail()`, `cancel()` e `timeout()` são atalhos
controlados para encerramentos que precisam armazenar dados adicionais.

`ExecutionState` pertence a uma única execução e não é thread-safe.
`AgentRuntime` coordena suas mutações e é o único responsável pelo execution
loop. Os métodos abstratos `Agent.run()` e `Agent.stream()` permanecem como
fachadas públicas compatíveis e devem delegar ao runtime, sem duplicar o loop.

## Invariantes

- `execution_id` é opaco, obrigatório e deve coincidir com
  `AgentContext.execution_id`;
- toda instância inicia em `CREATED`;
- mensagens mantêm ordem e são expostas como tupla;
- uma seleção de modelo pode ser registrada exatamente uma vez;
- turnos crescem de um em um e chamadas de ferramentas somente por valor
  inteiro positivo;
- eventos pertencem à mesma execução e seguem a sequência contínua `1, 2, 3`;
- mutações operacionais são rejeitadas após um estado terminal;
- eventos continuam registráveis após o término, pois formam o journal de
  observabilidade coordenado separadamente pelo runtime;
- `FAILED` exige `AgentErrorInfo`, enquanto `COMPLETED` não admite erro;
- timestamps têm fuso horário e nunca retrocedem.

`record_event()` apenas valida e registra. Ele não cria eventos nem é chamado
implicitamente por uma transição. O runtime coordena
`AgentEventFactory.from_transition()` e `record_event()` de forma explícita.

## Agregação de uso

`add_model_usage()` agrega `input_tokens`, `output_tokens`,
`cached_input_tokens` e `reasoning_tokens`. O total segue o contrato atual de
`ModelUsage`, que valida `total_tokens == input_tokens + output_tokens`; o
estado não altera os valores reportados.

A política de custo é conservadora: custo desconhecido se propaga. A primeira
chamada com custo conhecido inicia o agregado, mas, se qualquer chamada tiver
`estimated_cost=None`, o agregado passa a `None` e permanece desconhecido.
Portanto, o valor nunca sugere um custo total que não possa ser comprovado.

## Estado, snapshot e resultado

| Tipo | Mutabilidade | Uso |
| --- | --- | --- |
| `ExecutionState` | controlada por métodos | estado interno do runtime |
| `ExecutionSnapshot` | frozen | observação serializável |
| `AgentResult` | frozen | resultado público terminal |

`snapshot()` produz cópias lógicas das coleções, metadados e output. Alterações
posteriores no estado não modificam snapshots anteriores. O snapshot contém
somente dados e não inclui lifecycle, provider, registry, clock, locks ou
callbacks. Restauração ainda não é suportada.

`to_result()` só funciona em estados terminais e mapeia `execution_id`, status,
output, uso, eventos e erro. Mensagens e seleção permanecem no estado e no
snapshot porque não pertencem ao contrato público atual de `AgentResult`.

## Fora do escopo

Esta classe não executa providers ou ferramentas, não acessa rede e não contém
registry, service locator, retry, fallback, RAG, memória persistente, event bus,
checkpoint/restore nem mecanismo de concorrência. A orquestração externa está
documentada em [`agent-runtime.md`](agent-runtime.md).
