# Abstração de modelos

A Model Abstraction Layer define a fronteira estável entre o core do Atlas e
qualquer provedor de modelos. O core conhece apenas contratos próprios;
adapters futuros traduzirão requisições, respostas e erros dos SDKs concretos.

```text
Agent Runtime (futuro)
        │
        ▼
   ModelProvider
        │
        ├──────── Adapter OpenAI
        ├──────── Adapter Anthropic
        ├──────── Adapter Gemini
        └──────── Adapter local

atlas-agent-core
        ▲
        │ depende dos contratos
pacote do provider ───── SDK externo
```

O sentido inverso é proibido: `atlas-agent-core` nunca importa um SDK externo.
`ModelProvider` representa um provedor que pode oferecer vários modelos;
`ModelDescriptor` representa um desses modelos.

## Contrato do provider

```python
class ModelProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    async def list_models(self) -> tuple[ModelDescriptor, ...]: ...

    @abstractmethod
    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse: ...

    @abstractmethod
    def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]: ...
```

Não existe `supports()` nesta fase. `list_models()` fornece os descriptors
necessários, e resolução de capabilities pertence ao registry futuro.

O registry e o algoritmo determinístico de resolução agora estão documentados
em [model-selection.md](model-selection.md).

## Capabilities e modelos

`ModelCapability` possui valores públicos estáveis:

```text
TEXT_GENERATION
STREAMING
STRUCTURED_OUTPUT
TOOL_CALLING
PARALLEL_TOOL_CALLING
VISION
AUDIO_INPUT
AUDIO_OUTPUT
JSON_MODE
```

`ModelDescriptor` contém `provider`, `model`, capabilities imutáveis, janela de
contexto, limite de saída e metadata opaca. Os limites opcionais devem ser
positivos. O identificador do provider remove somente whitespace externo; o
model ID continua opaco. Preços não fazem parte do descriptor.

## Mensagens e multimodalidade

`ModelMessage` aceita os papéis `SYSTEM`, `DEVELOPER`, `USER`, `ASSISTANT` e
`TOOL`. Seu conteúdo é uma tupla da união discriminada `MessageContent`:

- `TextContent` contém texto não vazio;
- `ImageContent` contém URI opaca, media type, detail e metadata;
- `AudioContent` contém URI opaca, media type e metadata.

O core não baixa URIs, não lê arquivos nem interpreta Base64. Mensagens de
papel `TOOL` devem informar `tool_call_id`; outras políticas de mensagens ficam
reservadas ao futuro Tool Runtime.

## Tools e structured output

`ModelToolDefinition` é somente a visão de uma ferramenta apresentada ao
modelo: nome, descrição e JSON Schema de parâmetros. Não é uma ferramenta
executável. `ToolCall` registra ID, nome e argumentos já convertidos para
`dict[str, object]`; JSON textual específico de provider deve ser convertido
pelo adapter.

`StructuredOutputDefinition` contém nome, descrição opcional, JSON Schema e a
flag `strict`. Tipos Pydantic não atravessam diretamente essa fronteira.

Schemas, argumentos e metadata usam `dict[str, object]` com validação de
compatibilidade JSON e cópia defensiva. Um alias JSON recursivo não foi criado
nesta fase para preservar simplicidade e compatibilidade com Pydantic e Mypy.

## Request

`ModelRequest` contém:

```text
model
messages
tools
structured_output
temperature
max_output_tokens
stop_sequences
metadata
```

Uma requisição exige ao menos uma mensagem. `max_output_tokens`, quando
informado, deve ser positivo. `temperature` deve ser finita e não negativa, sem
impor um máximo universal. Validações adicionais pertencem ao provider. Não há
opções específicas de vendor.

## Response

`ModelResponse` contém:

```text
response_id
model
content
tool_calls
finish_reason
usage
metadata
```

`FinishReason` normaliza `STOP`, `TOOL_CALL`, `LENGTH`, `CONTENT_FILTER`,
`CANCELLED`, `ERROR` e `UNKNOWN`. Uma resposta finalizada com `TOOL_CALL` exige
ao menos uma chamada. Conteúdo e tool calls podem coexistir para evitar perda
de informação produzida pelo provider.

## Uso

`ModelUsage` representa uma única chamada de modelo e é separado de `Usage`,
que agrega a execução do agente. Ele registra tokens de entrada, saída, total,
cache e raciocínio, além de custo estimado opcional e metadata. O total deve ser
igual à soma de entrada e saída; tokens de cache e raciocínio são detalhamentos
reportados pelo provider. O core não calcula preços nem agrega chamadas.

## Streaming

O streaming utiliza eventos estruturados, não `AsyncIterator[str]`:

```text
RESPONSE_STARTED
TEXT_DELTA
TOOL_CALL_STARTED
TOOL_CALL_ARGUMENT_DELTA
TOOL_CALL_COMPLETED
USAGE_UPDATED
RESPONSE_COMPLETED
ERROR
```

Cada `ModelStreamEvent` possui sequência maior ou igual a `1`, response ID
opcional, dados JSON, timestamp com fuso horário e imutabilidade de modelo. Se o
timestamp não for informado, o contrato utiliza o instante atual em UTC. Um
stream bem-sucedido começa com `RESPONSE_STARTED` e termina com
`RESPONSE_COMPLETED`; o provider deve preservar a ordem lógica e emitir
informação suficiente para formar uma resposta final. `ModelStreamAccumulator`
valida esse protocolo e reconstrói a resposta usada por `AgentRuntime.stream()`;
consulte [runtime-streaming.md](runtime-streaming.md).

## Contexto e erros

`ModelExecutionContext` transporta somente `execution_id`, `agent_id`,
`request_id` e metadata de correlação. Ele não expõe todo o `AgentContext` ao
provider.

`ModelProviderError` herda de `AtlasAgentError` e expõe somente mensagem,
provider, model opcional e `retryable`. A hierarquia pública contém:

- `ModelAuthenticationError`;
- `ModelPermissionError`;
- `ModelNotFoundError`;
- `ModelRateLimitError`;
- `ModelTimeoutError`;
- `ModelUnavailableError`;
- `ModelInvalidRequestError`;
- `ModelResponseError`.

Rate limit, timeout e indisponibilidade são retryable por padrão. Autenticação,
permissão, modelo inexistente e request inválido não são. O contrato não guarda
chaves, headers, requests completos ou respostas raw e não implementa retry.

Metadata é deliberadamente opaca e validada como JSON. O core não inspeciona
chaves mágicas para tentar reconhecer credenciais; adapters e consumidores são
responsáveis por nunca inserir segredos nesses mapas.

## Fora do escopo

Esta camada não implementa SDK de provider, rede, router, fallback, retry,
execução de ferramentas nem cálculo de custos. Registry, seleção e runtime
provider-neutral são implementados no core sobre os contratos aqui definidos.
