# Contratos, registro e execução segura de ferramentas

A camada de ferramentas define uma fronteira provider-agnostic para registrar
implementações conhecidas, autorizar uma chamada, validar argumentos e produzir
um resultado operacional seguro. O `AgentRuntime` usa essa fronteira no ciclo
`modelo → ferramenta → modelo`, sem transferir responsabilidades do executor.

## Fronteiras dos contratos

Os tipos possuem responsabilidades diferentes e não são intercambiáveis:

```text
ToolDefinition ≠ ModelToolDefinition
ToolCall       ≠ ToolExecutionRequest
ToolOutput     ≠ ToolExecutionResult
ToolRegistry   ≠ ServiceContainer
```

`ToolDefinition` contém schema, permissões, semântica de idempotência e metadata
interna. `to_model_definition()` cria uma nova `ModelToolDefinition` contendo
somente `name`, `description` e `parameters`; permissões, idempotência e metadata
de runtime nunca atravessam a fronteira do modelo.

```python
definition = ToolDefinition(
    name="get_customer",
    description="Consulta um cliente pelo identificador.",
    parameters={
        "type": "object",
        "properties": {"customer_id": {"type": "string"}},
        "required": ["customer_id"],
        "additionalProperties": False,
    },
    required_permissions=frozenset({"customer.read"}),
    idempotency=ToolIdempotency.IDEMPOTENT,
    metadata={"owner": "customer-platform"},
)

model_definition = definition.to_model_definition()
```

## Implementação e injeção de dependências

`Tool` é um contrato async-first. Uma implementação retorna `ToolOutput`, cujo
conteúdo e metadata precisam ser serializáveis em JSON. Objetos de domínio,
responses de SDKs e outras instâncias arbitrárias são rejeitados nessa fronteira.

Dependências pertencem à própria ferramenta e são injetadas no construtor:

```python
class CustomerLookupTool(Tool):
    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository
        self._definition = definition

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        customer = await self._repository.get(str(arguments["customer_id"]))
        return ToolOutput(content={"customer": customer.to_dict()})
```

`ToolExecutionContext` contém somente `execution_id`, `agent_id`,
`tool_call_id`, `ExecutionIdentity` opcional e metadata de correlação. Ele não
contém `AgentContext`, serviços, callbacks genéricos ou métodos de lookup.

## Registry

`ToolRegistry` mantém estado somente em sua instância e aceita apenas `Tool`.
Ele preserva a ordem de registro e resolve nomes por igualdade exata:

```python
registry = ToolRegistry()
registry.register(customer_tool)

tool = registry.get("get_customer")
optional_tool = registry.try_get("get_customer")
all_tools = registry.tools()
model_tools = registry.model_definitions()
removed = registry.unregister("get_customer")
```

Um nome duplicado produz `DuplicateToolError`; `get()` e `unregister()` produzem
`ToolNotRegisteredError` para nomes desconhecidos, enquanto `try_get()` retorna
`None`. Não há sobrescrita, normalização de caixa, correção aproximada, registry
global nem descoberta dinâmica. O registry deve ser montado no bootstrap e não
é thread-safe para mutações concorrentes.

## Solicitação, contexto e resultado

`ToolExecutionRequest` preserva `tool_call_id`, nome exato, argumentos já
estruturados, `idempotency_key` opcional e metadata. Argumentos em JSON textual
são rejeitados. O `tool_call_id` deve coincidir com o contexto; divergência é um
bug de orquestração e produz `ToolExecutionInvariantError`.

```python
result = await executor.execute(
    ToolExecutionRequest(
        tool_call_id="call-001",
        tool_name="get_customer",
        arguments={"customer_id": "123"},
        idempotency_key="customer-lookup-123",
    ),
    context=ToolExecutionContext(
        execution_id="execution-001",
        agent_id="assistant",
        tool_call_id="call-001",
        identity=identity,
    ),
)
```

`ToolExecutionResult` mantém a identidade original, status, output ou erro,
timestamps UTC com fuso e metadata. Os status são `SUCCEEDED`, `FAILED`,
`DENIED`, `INVALID_ARGUMENTS` e `CANCELLED`. Falhas transportam somente
`ToolExecutionError`, sem exception, stack trace ou output parcial.

## Autorização

`ToolPermissionEvaluator` é puro e aplica a política all-of sobre strings
opacas. A verificação ocorre antes da validação dos argumentos para não revelar
detalhes do schema a uma identidade não autorizada.

| Permissões exigidas | Identidade | Decisão |
| --- | --- | --- |
| nenhuma | ausente | permitir |
| nenhuma | presente | permitir |
| `a` | `a` | permitir |
| `a` | `a,b` | permitir |
| `a,b` | `a` | negar, falta `b` |
| `a` | ausente | negar, falta `a` |

Uma negativa produz `DENIED/tool_permission_denied` e a implementação não é
executada.

## Validação de argumentos

`ToolArgumentValidator` é o contrato substituível. A implementação padrão,
`JsonSchemaToolArgumentValidator`, usa `jsonschema` e valida o Draft 2020-12
completo. Ela verifica também a validade do próprio schema, coleta todas as
ocorrências em ordem determinística e as normaliza em
`ToolArgumentValidationIssue` com caminho JSON Pointer, código e mensagem em
português.

Argumentos inválidos produzem `INVALID_ARGUMENTS/tool_invalid_arguments`; a
ferramenta não é chamada. A biblioteca consolidada evita um parser manual que
alegaria suporte incompleto ao padrão.

## Pipeline do executor

```text
ToolExecutionRequest
        ↓
resolver nome exato no registry
        ↓
validar identidade request/context
        ↓
avaliar todas as permissões
        ↓
validar argumentos pelo JSON Schema
        ↓
executar a implementação async conhecida
        ↓
normalizar ToolOutput ou erro
        ↓
ToolExecutionResult
```

`prepare()` executa resolução, identidade, autorização e validação. Quando a
chamada pode alcançar a implementação, ele devolve uma preparação opaca;
`execute_prepared()` efetiva essa chamada. Essa separação permite ao runtime
verificar `max_tool_calls` depois dos controles e antes de executar. O método
`execute()` permanece como a API conveniente que encadeia as duas etapas.

Uma ferramenta desconhecida vira `FAILED/tool_not_found`. `ToolError` preserva
seu código seguro, detalhes e retryability, sem disparar retry. Exceções
inesperadas viram `FAILED/tool_execution_error` com mensagem genérica;
`asyncio.CancelledError` não é capturado e continua sendo propagado.

O executor não guarda estado por chamada e pode atender execuções concorrentes.
A segurança da implementação concreta é responsabilidade dessa implementação;
o executor não cria lock, semaphore, thread pool ou serialização global.

## Idempotência e limites atuais

`ToolIdempotency` declara `UNSPECIFIED`, `IDEMPOTENT` ou `NON_IDEMPOTENT`, e a
solicitação pode transportar uma `idempotency_key`. Isso estabelece identidade
para uma camada futura, mas declaração não é enforcement no executor: duas
chamadas diretas de `execute()` com o mesmo ID ou chave executam duas vezes. O
runtime mantém deduplicação local por `tool_call_id` durante cada execução.

Não existem cache local, store distribuído, auto retry, fallback, timeout
específico, approval, import dinâmico, shell, `eval`, `exec`, ferramenta genérica
de filesystem ou acesso à rede no core. Não existe store distribuído que estenda
a deduplicação entre processos ou execuções. Consulte
[multi-turn-runtime.md](multi-turn-runtime.md).
