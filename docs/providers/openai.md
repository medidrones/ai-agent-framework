# Provider oficial OpenAI

`atlas-agent-providers` implementa `OpenAIModelProvider` sobre a API Responses
assíncrona. A integração é opcional: o SDK `openai` existe somente nesta
distribuição e nunca entra no `atlas-agent-core`.

## Instalação e composição manual

```bash
uv add atlas-agent-providers
```

```python
from openai import AsyncOpenAI

from atlas_agents import ModelProviderRegistry
from atlas_agents.providers.openai import OpenAIModelProvider

client = AsyncOpenAI(api_key="chave-fornecida-explicitamente")
provider = OpenAIModelProvider(client)

registry = ModelProviderRegistry()
registry.register(provider)

# O chamador continua responsável por fechar o cliente.
await client.close()
```

O provider não cria o cliente, não lê variáveis de ambiente e não carrega
`.env`. `list_models()` consulta apenas o catálogo local, sem chamar
`client.models.list()`.

## Plugin

O entry point `openai` pode ser descoberto pelo sistema de plugins. A ativação
recebe configuração explícita no `PluginContext`:

```python
context = PluginContext.create(
    atlas_version="1.0.0",
    configuration={
        "api_key": "chave-fornecida-pelo-host",
        "store_responses": False,
        "max_retries": 2,
    },
)
```

Nesse modo, o plugin cria o cliente durante `activate()` e o fecha em
`deactivate()`. Manifesto, descritores, resultados e `repr` da configuração não
expõem a chave.

## Recursos suportados

| Recurso | Status |
| --- | --- |
| Texto | Suportado |
| Streaming | Suportado |
| Function calling | Suportado |
| Múltiplas chamadas de ferramenta | Suportado |
| Structured Outputs com JSON Schema | Suportado |
| Entrada de imagem por HTTPS ou data URL | Suportado |
| Entrada de áudio | Não suportado |
| Web search e file search nativos | Não suportado |
| Realtime, background e conversas hospedadas | Não suportado |

O catálogo padrão, validado na documentação oficial OpenAI em setembro de
2026, contém `gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-terra` e `gpt-5.6-luna`.
Todos anunciam texto, streaming, saída estruturada, function calling paralelo e
visão, com janela de contexto de 1.050.000 tokens e saída máxima de 128.000.
Não há preços nem estimativas de custo hardcoded.

As referências normativas são o
[catálogo oficial de modelos](https://developers.openai.com/api/docs/models), a
[API Responses](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
e as páginas de
[`gpt-6-astra`](https://developers.openai.com/api/docs/models/gpt-6-astra),
[`gpt-5.6-sol`](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[`gpt-5.6-terra`](https://developers.openai.com/api/docs/models/gpt-5.6-terra) e
[`gpt-5.6-luna`](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

## Fronteira do adapter

```text
Atlas ModelRequest
        │
        ▼
OpenAIRequestMapper
        │
        ▼
OpenAI Responses API
        │
        ▼
OpenAIResponseMapper / OpenAIStreamMapper
        │
        ▼
ModelResponse / ModelStreamEvent
```

Papéis `SYSTEM`, `DEVELOPER`, `USER` e `ASSISTANT` permanecem mensagens. O
histórico de chamadas do assistant vira itens `function_call`; mensagens
`TOOL` viram `function_call_output` ligadas pelo `tool_call_id`. Cada request é
autossuficiente: o adapter não usa `previous_response_id`, `conversation`,
hosted prompts ou execução em background.

O provider apenas traduz chamadas de ferramenta. A execução, autorização,
aprovação humana, checkpoint, memória, Knowledge/RAG e guardrails continuam sob
responsabilidade do runtime do Atlas.

## Privacidade e armazenamento

Chamadas reais enviam ao serviço OpenAI as mensagens e, quando presentes,
schemas de ferramentas, schemas de saída e referências de imagens. Por padrão,
o payload inclui `store=False`. A persistência remota só é habilitada por
`OpenAIProviderConfig(store_responses=True)` ou pela configuração explícita do
plugin.

O adapter não encaminha automaticamente `ModelRequest.metadata`, metadata do
contexto, identidade, IDs de execução/request ou tokens de retomada. Respostas
não incluem objetos crus do SDK. Erros são normalizados e não copiam headers,
corpos HTTP ou mensagens potencialmente sensíveis.
