# Atlas Agent Framework

> Versão estável em preparação: `1.0.1`, derivada da candidata certificada
> `1.0.1rc1`. O nome público é `atlas-agent-framework`; o namespace Python
> `atlas_agent` permanece inalterado.
> Consulte as [notas de release](docs/release/releases/1.0.1.md).

A distribuição opcional `atlas-agent-config` oferece schema versionado,
carregamento seguro de YAML/JSON, referências de segredos, factories tipadas e
uma composition root com rollback. Consulte a
[`configuração declarativa`](docs/config/overview.md).

O core também oferece guardrails provider-neutral com opt-in explícito por
agente para entrada, saída e ferramentas. Consulte
[`guardrails.md`](docs/reference/guardrails.md).

O runtime possui observabilidade provider-neutral e fail-open por injeção
explícita, com tracing, métricas, continuidade em checkpoints e defaults no-op.
Consulte [`observability.md`](docs/reference/observability.md).

A distribuição opcional `atlas-agent-evaluation` mede resultados com datasets
versionados, evaluators determinísticos, scoring e relatórios, sem alterar o
runtime produtivo. Consulte [`evaluation.md`](docs/reference/evaluation.md).

O core agora oferece uma API explícita de plugins com discovery por entry
points, compatibilidade de versão, preflight de conflitos, ativação segura e
rollback por plugin. Consulte [`plugins.md`](docs/reference/plugins.md).

A distribuição opcional `atlas-agent-providers` oferece o provider oficial
OpenAI sobre a API Responses, com streaming, function calling, saída estruturada
e entrada de imagem. Consulte [`openai.md`](docs/providers/openai.md).

A distribuição opcional `atlas-agent-mcp` integra o runtime ao Model Context
Protocol como cliente e servidor, com transportes stdio e Streamable HTTP,
importação explícita de ferramentas e exposição por allowlist. Consulte a
[`visão geral MCP`](docs/mcp/overview.md).

A distribuição opcional `atlas-agent-adapters` expõe uma fachada única de
execução por REST/FastAPI, gRPC/protobuf e mensageria broker-neutral, com
identidade confiável, autorização e limites explícitos. Consulte a
[`visão geral dos adapters`](docs/adapters/overview.md).

Atlas é um framework Python reutilizável e independente de provedor para
definir, compor, executar e avaliar agentes de IA.

Este repositório contém a infraestrutura de um framework, não uma aplicação de
negócio. O pacote principal define contratos estáveis, enquanto pacotes
opcionais integrarão provedores de modelos, sistemas de armazenamento,
transportes e ferramentas de observabilidade.

## Objetivo

O objetivo do Atlas é oferecer um núcleo tecnológico incorporável para definir
e executar agentes sem impor uma stack de aplicação. Providers, persistência,
transportes e integrações serão adicionados por pacotes opcionais que
implementam contratos do core.

O Atlas é um framework e não uma aplicação final. Ele não contém interface,
autenticação, infraestrutura obrigatória nem regras de um domínio de negócio.

## Princípios

- inversão de dependência entre core e integrações;
- APIs async-first para operações de I/O;
- tipagem completa e contratos públicos explícitos;
- dependências mínimas no core;
- extensibilidade por plugins e adapters opcionais;
- segurança e observabilidade consideradas desde o núcleo.

## Situação atual

O projeto possui a fundação do workspace e os primeiros contratos públicos do
core. Já é possível descrever agentes, entradas, contexto, identidade, resultados,
uso e eventos, além de implementar o contrato abstrato `Agent`. O lifecycle
formal valida mudanças de estado, registra um histórico imutável e permite gerar
eventos monotônicos por execução. A abstração de modelos já representa
capabilities, mensagens multimodais, requests, responses, streaming e providers
sem depender de SDKs concretos. Providers podem ser registrados e seus modelos
selecionados por capabilities e limites com desempate determinístico.
O estado de execução em memória já pode integrar esses contratos, acumular
mensagens e uso, validar eventos e produzir snapshots e resultados terminais.
`AgentRuntime` coordena execuções completas por meio de
`ModelProvider.generate()` ou entrega incremental por `ModelProvider.stream()`,
sem depender de provider concreto. O streaming valida sequência, protocolo,
tool calls e snapshots cumulativos de uso antes de reconstruir a resposta.
Limites opcionais de turnos, tools e tokens, budget estimado e timeout total
governam ambos os modos sem adicionar dependências de provider.
Uma camada independente de ferramentas já oferece contratos imutáveis, registry
determinístico, autorização, validação JSON Schema e execução assíncrona segura.

Agentes declaram uma allowlist ordenada de ferramentas. O runtime executa o loop
`modelo → ferramenta → modelo`, preserva o histórico provider-neutral, protege
chamadas duplicadas dentro da execução e suporta múltiplos model turns nos modos
completo e streaming. Ferramentas sensíveis podem suspender a execução para
aprovação humana, salvar um checkpoint por contrato injetado e retomar com token
opaco de uso único, inclusive no modo streaming. Agentes também podem habilitar
memória de trabalho, conversa e longo prazo por escopos seguros, store abstrato
e policies explícitas de leitura e escrita. Também podem consultar uma
allowlist de fontes externas por contratos Knowledge/RAG, com contexto não
autoritativo e citações `K1`, `K2`… Ainda não existem retries automáticos,
fallback ou backends concretos de retrieval. O provider OpenAI é a primeira
integração concreta com modelos.

## Distribuições

| Pacote | Finalidade | Instalação |
| --- | --- | --- |
| `atlas-agent-core` | contratos e runtime mínimo | `pip install atlas-agent-core` |
| `atlas-agent-providers` | providers oficiais | `pip install atlas-agent-providers[openai]` |
| `atlas-agent-mcp` | integração MCP | `pip install atlas-agent-mcp` |
| `atlas-agent-adapters` | transportes externos | `pip install atlas-agent-adapters[rest]` |
| `atlas-agent-config` | configuração declarativa | `pip install atlas-agent-config` |
| `atlas-agent-evaluation` | avaliação | `pip install atlas-agent-evaluation` |
| `atlas-agent-framework` | meta-package opcional | `pip install atlas-agent-framework[full]` |

O core não instala OpenAI, MCP, FastAPI, gRPC ou PyYAML. Consulte a
[estratégia de pacotes](docs/distribution/packages.md), os
[extras disponíveis](docs/distribution/optional-dependencies.md) e a
[matriz de compatibilidade](docs/distribution/compatibility.md).

## Requisitos do ambiente

- Python 3.12 ou superior
- [uv](https://docs.astral.sh/uv/)
- GNU Make 4 ou superior para utilizar os alvos opcionais do `Makefile`

## Exemplos oficiais

A suíte em [`examples/`](examples/README.md) demonstra progressivamente a API
pública, desde o agente mínimo até adapters REST/gRPC, consumidores .NET e uma
arquitetura corporativa determinística. Salvo o cenário OpenAI explicitamente
opt-in, os exemplos Python funcionam offline.

## Desenvolvimento

Execute todos os comandos a partir da raiz do repositório:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy packages
uv run pytest
make build
```

Os mesmos comandos podem ser executados pelos alvos do `Makefile`. Por exemplo,
`make quality` executa lint, validação de formato, verificação de tipos e
testes.

`make artifacts` constrói e inspeciona os wheels e sdists. O alvo
`make packaging-smoke` instala os wheels em ambientes temporários e valida
core mínimo, imports opcionais, namespace compartilhado e entry points.

O workspace raiz é um agregador. Use `make build` para selecionar explicitamente
as distribuições `atlas-agent-adapters`, `atlas-agent-config`, `atlas-agent-core`,
`atlas-agent-evaluation`, `atlas-agent-providers`, `atlas-agent-mcp` e o
meta-package opcional `atlas-agent-framework`, evitando
publicar o agregador por engano.

O pacote utiliza o layout `src` e pode ser importado da seguinte forma:

```python
from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentRuntime,
    ModelProviderRegistry,
)

definition = AgentDefinition(
    agent_id="assistant",
    name="Assistente",
    instructions="Responda de forma objetiva.",
)
input_data = AgentInput(message="Explique o contrato do agente.")

registry = ModelProviderRegistry()
# Um ModelProvider implementado em pacote opcional deve ser registrado aqui.
runtime = AgentRuntime(model_registry=registry)

# result = await runtime.run(
#     agent=definition,
#     input_data=input_data,
#     context=AgentContext(execution_id="execution-1"),
# )
```

A referência completa está em
[docs/reference/core-primitives.md](docs/reference/core-primitives.md). Consulte
também [docs/reference/execution-lifecycle.md](docs/reference/execution-lifecycle.md)
para o mapa de estados e eventos e
[docs/reference/model-abstraction.md](docs/reference/model-abstraction.md) para
a fronteira provider-agnostic de modelos e
[docs/reference/model-selection.md](docs/reference/model-selection.md) para
registro, catálogo e seleção determinística e
[docs/reference/execution-state.md](docs/reference/execution-state.md) para o
estado controlado do runtime. O primeiro pipeline executável está em
[docs/reference/agent-runtime.md](docs/reference/agent-runtime.md), e sua API
incremental está em
[docs/reference/runtime-streaming.md](docs/reference/runtime-streaming.md).
As políticas operacionais estão descritas em
[docs/reference/execution-limits.md](docs/reference/execution-limits.md), e a
infraestrutura segura de ferramentas em
[docs/reference/tools.md](docs/reference/tools.md). O loop agentic completo está
em [docs/reference/multi-turn-runtime.md](docs/reference/multi-turn-runtime.md).
A suspensão para decisão humana está em
[docs/reference/human-approval.md](docs/reference/human-approval.md), e a
persistência abstrata para retomada em
[docs/reference/checkpoint-resume.md](docs/reference/checkpoint-resume.md).
A camada de memória está descrita em
[docs/reference/memory.md](docs/reference/memory.md), e sua separação de
Knowledge/RAG em
[docs/architecture/memory-vs-knowledge.md](docs/architecture/memory-vs-knowledge.md).
A referência de conhecimento está em
[docs/reference/knowledge.md](docs/reference/knowledge.md), e sua integração no
runtime em [docs/reference/rag-runtime.md](docs/reference/rag-runtime.md).
A referência de observabilidade está em
[docs/reference/observability.md](docs/reference/observability.md), com a decisão
arquitetural em
[docs/architecture/observability.md](docs/architecture/observability.md).
A avaliação de qualidade está em
[docs/reference/evaluation.md](docs/reference/evaluation.md), com contratos de
[datasets](docs/reference/evaluation-datasets.md), catálogo de
[evaluators](docs/reference/evaluators.md) e sua
[arquitetura independente](docs/architecture/evaluation.md). A extensão por
pacotes está documentada na [referência de plugins](docs/reference/plugins.md),
no [guia de autoria](docs/plugins/authoring.md), nas
[orientações de segurança](docs/plugins/security.md) e na
[arquitetura de plugins](docs/architecture/plugins.md). Os contratos externos,
formas de composição e garantias por transporte estão na
[documentação de adapters](docs/adapters/overview.md) e em sua
[decisão arquitetural](docs/architecture/external-adapters.md).

Consulte [ARCHITECTURE.md](ARCHITECTURE.md) para conhecer o desenho de alto
nível e
[docs/architecture/dependency-rules.md](docs/architecture/dependency-rules.md)
para conferir as restrições de dependência aplicáveis.

## Estrutura do repositório

```text
.
├── docs/architecture/          # Documentação arquitetural
├── packages/
│   ├── atlas-agent-core/       # Distribuição e testes do núcleo
│   ├── atlas-agent-evaluation/ # Avaliação opcional e independente do runtime
│   ├── atlas-agent-providers/  # Providers concretos e SDKs opcionais
│   ├── atlas-agent-mcp/        # Integração cliente e servidor com MCP
│   ├── atlas-agent-adapters/   # REST, gRPC e mensageria externa
│   └── atlas-agent-config/     # Configuração declarativa e composition root
├── .github/workflows/         # Integração contínua
├── AGENTS.md                 # Regras para agentes de engenharia
├── Makefile                  # Comandos locais de conveniência
└── pyproject.toml            # Workspace e ferramentas de qualidade
```

## Contribuição e segurança

As diretrizes de desenvolvimento estão descritas em
[CONTRIBUTING.md](CONTRIBUTING.md). Relate problemas de segurança pelo processo
privado definido em [SECURITY.md](SECURITY.md).

## Licença

O Atlas Agent Framework é disponibilizado sob a [Licença MIT](LICENSE).
