# Registro e seleção de modelos

`ModelProviderRegistry` registra explicitamente providers, descobre seus
descriptors e seleciona um par provider/modelo de forma determinística. Ele não
é global, não funciona como service locator e aceita somente `ModelProvider`.

O registry seleciona contratos; nunca chama `generate()` ou `stream()`.

```text
providers registrados
        │
        ▼
list_models() sequencial
        │
        ▼
catálogo imutável
        │
        ▼
filtros obrigatórios
        │
        ▼
strategy determinística
        │
        ▼
ModelSelectionResult
```

## API do registry

```python
registry = ModelProviderRegistry()

registry.register(provider)
provider = registry.get("provider")
optional = registry.try_get("provider")
snapshot = registry.providers()
removed = registry.unregister("provider")

catalog = await registry.build_catalog()
candidates = await registry.find_candidates(request)
selection = await registry.select(request)
```

`provider_name` é único por instância. Somente whitespace externo é removido;
maiúsculas e minúsculas permanecem distintas. Registro duplicado gera
`DuplicateModelProviderError`. `get()` e `unregister()` geram
`ModelProviderNotRegisteredError` quando o identificador não existe;
`try_get()` retorna `None`.

`providers()` retorna uma tupla independente na ordem de registro. Não existe
singleton, decorator de registro ou estado de módulo.

## Catálogo

Cada descoberta consulta `list_models()` sequencialmente na ordem de registro.
Não há cache, concorrência, persistência ou refresh em background. Falhas de
provider são propagadas imediatamente, sem selecionar silenciosamente entre os
demais; `asyncio.CancelledError` também é preservado.

O catálogo é uma tupla de `ModelCatalogEntry`:

```text
provider_name
descriptor
registration_order
model_order
```

`registration_order` registra a posição do provider, e `model_order`, a posição
retornada por `list_models()`. O descriptor deve declarar o mesmo provider e um
provider não pode repetir o mesmo model ID. Violações geram
`InvalidModelDescriptorError`. O mesmo model ID pode existir em providers
diferentes porque sua identidade é o par `(provider, model)`.

## Requisição de seleção

`ModelSelectionRequest` é imutável e contém:

```text
provider
model
required_capabilities
preferred_capabilities
minimum_context_window
minimum_max_output_tokens
metadata
```

Todos os campos são opcionais; uma requisição vazia seleciona entre todo o
catálogo. Limites mínimos devem ser positivos. Um limite desconhecido no
descriptor (`None`) não atende a um requisito explícito.

Quando provider e model são informados juntos, o par é explícito. Modelo
inexistente gera `ModelNotAvailableError`; capability obrigatória ausente gera
`ModelCapabilityMismatchError`. Outro modelo nunca é usado como fallback.

## Candidatos e algoritmo oficial

`find_candidates()` mantém a ordem natural do catálogo e aplica, exatamente
nesta ordem:

1. provider solicitado;
2. model solicitado;
3. todas as capabilities obrigatórias;
4. janela mínima de contexto;
5. limite mínimo de tokens de saída.

Capabilities preferidas não eliminam candidatos. Para evitar contagem dupla:

```text
effective_preferred = preferred_capabilities - required_capabilities
```

`ModelCandidate` registra descriptor, ordens e quantidade de preferências
atendidas. A strategy default classifica por:

1. maior quantidade de capabilities preferidas, ordem decrescente;
2. ordem de registro do provider, crescente;
3. ordem do modelo retornada pelo provider, crescente;
4. model ID estável como último desempate.

Não há randomização, round-robin, custo, latência, health, região ou metadata
mágica no ranking.

## Strategy e resultado

`ModelSelectionStrategy` recebe somente candidatos já válidos. A implementação
default, `DeterministicModelSelectionStrategy`, é stateless. Uma strategy
alternativa pode ser injetada no construtor do registry.

`ModelSelectionResult` permanece serializável e não contém a instância runtime
do provider:

```text
provider_name
model
descriptor
matched_required_capabilities
matched_preferred_capabilities
preferred_capability_matches
candidate_count
```

O runtime obtém a instância selecionada com
`registry.get(selection.provider_name)`.

Na execução single-turn, o runtime une requisitos do caller às capabilities
derivadas do input: `TEXT_GENERATION` sempre, `VISION` para imagens e
`AUDIO_INPUT` para áudio. Restrições explícitas de provider/modelo continuam sem
fallback. O provider resolvido é usado somente durante a chamada e nunca é
armazenado em `ExecutionState`.

## Erros

Erros de registry são locais e separados de `ModelProviderError`:

```text
AtlasAgentError
├── ModelProviderRegistryError
│   ├── DuplicateModelProviderError
│   ├── ModelProviderNotRegisteredError
│   └── InvalidModelDescriptorError
└── ModelSelectionError
    ├── NoMatchingModelError
    ├── ModelCapabilityMismatchError
    └── ModelNotAvailableError
```

`NoMatchingModelError` preserva somente requisitos seguros e nunca copia a
metadata do request.

## Fora do escopo

Não há provider concreto, fallback, retry, cache, plugin discovery, config
loader, roteamento por custo/latência ou health check. `AgentRuntime` utiliza
esta camada para uma única seleção e uma chamada de modelo, sem alterar as
responsabilidades do registry.
