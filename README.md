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

Ainda não existe runtime nem integração concreta com modelos, ferramentas,
memória ou bases de conhecimento. Um agente concreto pode implementar o
contrato, mas sua execução e suas dependências continuam sob responsabilidade
do consumidor.

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
from atlas_agents import AgentDefinition, AgentInput

definition = AgentDefinition(
    agent_id="assistant",
    name="Assistente",
    instructions="Responda de forma objetiva.",
)
input_data = AgentInput(message="Explique o contrato do agente.")
```

A referência completa está em
[docs/reference/core-primitives.md](docs/reference/core-primitives.md). Consulte
também [docs/reference/execution-lifecycle.md](docs/reference/execution-lifecycle.md)
para o mapa de estados e eventos e
[docs/reference/model-abstraction.md](docs/reference/model-abstraction.md) para
a fronteira provider-agnostic de modelos e
[docs/reference/model-selection.md](docs/reference/model-selection.md) para
registro, catálogo e seleção determinística.

Consulte [ARCHITECTURE.md](ARCHITECTURE.md) para conhecer o desenho de alto
nível e
[docs/architecture/dependency-rules.md](docs/architecture/dependency-rules.md)
para conferir as restrições de dependência aplicáveis.

## Estrutura do repositório

```text
.
├── docs/architecture/          # Documentação arquitetural
├── packages/
│   └── atlas-agent-core/      # Distribuição Python principal
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
