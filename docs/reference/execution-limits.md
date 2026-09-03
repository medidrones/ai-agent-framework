# Limites, timeout e budget de execução

O runtime oferece políticas opcionais, imutáveis e provider-agnostic para
governar cada execução. Sem configuração, `run()` e `stream()` preservam o
comportamento anterior.

```python
runtime = AgentRuntime(
    model_registry=registry,
    limits=ExecutionLimits(
        max_turns=1,
        max_tool_calls=5,
        max_input_tokens=10_000,
        max_output_tokens=2_000,
        max_total_tokens=12_000,
        timeout_seconds=30,
    ),
    budget=ExecutionBudget(
        max_estimated_cost=Decimal("1.00"),
        currency="USD",
    ),
)
```

Todos os limites numéricos informados em `ExecutionLimits` devem ser positivos.
O timeout também deve ser finito. `ExecutionLimits()` significa ausência de
restrições explícitas. Um budget aceita custo máximo zero, rejeita valores
negativos ou não finitos e não realiza conversão cambial.

## Escopo e substituição

Defaults podem ser definidos no construtor do runtime. `run()` e `stream()`
também aceitam `limits` e `budget`; quando informados, eles substituem
integralmente o respectivo default. Não existe merge campo a campo. As políticas
e o consumo são isolados por execução, mesmo quando o runtime e o provider são
compartilhados.

```python
result = await runtime.run(
    agent=definition,
    input_data=input_data,
    context=context,
    limits=ExecutionLimits(max_total_tokens=5_000),
    budget=ExecutionBudget(max_estimated_cost=Decimal("0.50")),
)
```

## Checker puro

`ExecutionLimitChecker` não realiza I/O, não muta `ExecutionState` e não altera
o lifecycle. Seus métodos retornam `None` ou um value object de violação:

```text
check_turn_allowed()       → ExecutionLimitViolation | None
check_tool_call_allowed()  → ExecutionLimitViolation | None
check_usage()              → ExecutionLimitViolation | None
check_budget()             → ExecutionBudgetViolation | None
```

`ExecutionLimitViolation` contém `reason`, `limit` e `observed`. Os motivos
públicos são `max_turns`, `max_tool_calls`, `max_input_tokens`,
`max_output_tokens` e `max_total_tokens`.

`max_turns` representa o número máximo de invocações do modelo. O runtime
verifica o contador antes, incrementa o turno e somente então chama o provider.
`max_tool_calls` representa ferramentas efetivamente executadas, não solicitações
do modelo. O runtime prepara autorização e argumentos primeiro, verifica o
limite imediatamente antes da invocação e incrementa o contador apenas quando
a implementação será chamada.

## Enforcement pós-resposta

Tokens e custo são verificados depois que o provider informa usage:

```text
ModelResponse
    ↓
adicionar usage ao estado
    ↓
input tokens → output tokens → total tokens
    ↓
budget
    ↓
adicionar mensagem assistant e validar output
```

Igualdade com o limite é permitida; apenas `observed > limit` encerra a
execução. Se múltiplos limites forem excedidos, a precedência é:

1. `max_input_tokens`;
2. `max_output_tokens`;
3. `max_total_tokens`;
4. budget.

Uma violação de tokens termina em `LIMIT_EXCEEDED`; custo termina em
`BUDGET_EXCEEDED`. Usage reportada permanece no resultado, enquanto `output`
fica `None` e nenhuma mensagem assistant é adicionada.

O enforcement é necessariamente posterior nesta versão: não existe tokenizer,
estimador de custo, tabela de preços ou reserva preflight. Portanto, uma chamada
pode consumir além do limite antes que o Atlas consiga detectá-lo.

## Custo desconhecido e moeda

`Usage.estimated_cost is None` significa custo desconhecido, não zero. Nesse
caso o budget é indeterminado e a execução continua. Uma política futura poderá
exigir visibilidade de custo.

O campo `currency` é apenas um identificador de auditoria. O runtime presume que
o custo reportado usa a moeda configurada e não consulta cotação nem converte
valores.

## Deadline absoluto

O timeout utiliza um único `ExecutionDeadline` baseado em `time.monotonic()`.
O prazo começa com a execução e cobre validação, seleção, todos os turnos do
modelo, execução de ferramentas e processamento. No streaming, cada espera usa
o tempo restante do mesmo deadline;
um chunk não renova o prazo e o tempo do consumidor entre chamadas ao iterador
não é envolvido por um contexto de cancelamento do runtime.

```text
Runtime deadline expirou        → TIMED_OUT + AgentResult
Provider lançou ModelTimeoutError → FAILED
Caller cancelou a coroutine     → CANCELLED + CancelledError repropagado
Consumer fechou o stream cedo   → CANCELLED + cleanup
```

O primeiro sinal efetivamente observado vence uma corrida entre deadline e
cancelamento externo. Testes não devem depender de empate exato.

## Eventos e erros

Os terminais usam os eventos já existentes:

```text
EXECUTION_LIMIT_EXCEEDED
  {reason, limit, observed}

EXECUTION_BUDGET_EXCEEDED
  {limit, observed}

EXECUTION_TIMED_OUT
  {timeout_seconds, elapsed_seconds}
```

Os códigos públicos são `execution_timed_out`,
`execution_max_turns_exceeded`, `execution_max_tool_calls_exceeded`,
`execution_max_input_tokens_exceeded`,
`execution_max_output_tokens_exceeded`,
`execution_max_total_tokens_exceeded` e `execution_budget_exceeded`. Todos são
não retryable nesta versão.

## Limites preservados

Não há pricing database, tokenizer, previsão ou reserva de custo, conversão de
moeda, quotas globais ou por tenant, rate limiting, limite de concorrência,
retry, fallback, roteamento adaptativo, aprovação ou execução paralela de tools.
