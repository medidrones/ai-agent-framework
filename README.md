# Atlas Agent Framework

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
opaco de uso único, inclusive no modo streaming. Ainda não existem retries
automáticos, fallback, memória, RAG ou integração concreta com modelos.

## Requisitos

- Python 3.12 ou superior
- [uv](https://docs.astral.sh/uv/)
- GNU Make 4 ou superior para utilizar os alvos opcionais do `Makefile`

## Desenvolvimento

Execute todos os comandos a partir da raiz do repositório:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy packages
uv run pytest
uv build --package atlas-agent-core
```

Os mesmos comandos podem ser executados pelos alvos do `Makefile`. Por exemplo,
`make quality` executa lint, validação de formato, verificação de tipos e
testes.

O workspace raiz é um agregador não distribuível. Por isso, o build seleciona
explicitamente `atlas-agent-core`, evitando a geração acidental de um wheel
vazio para o projeto agregador.

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

Consulte [ARCHITECTURE.md](ARCHITECTURE.md) para conhecer o desenho de alto
nível e
[docs/architecture/dependency-rules.md](docs/architecture/dependency-rules.md)
para conferir as restrições de dependência aplicáveis.

## Estrutura do repositório

```text
.
├── docs/architecture/          # Documentação arquitetural
├── packages/
│   └── atlas-agent-core/      # Distribuição e testes organizados por contexto
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
