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

O projeto está na fase de fundação. A versão atual estabelece o workspace, o
pacote, os gates de qualidade e as regras arquiteturais de dependência. O
comportamento de execução dos agentes ainda não foi implementado
intencionalmente.

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
import atlas_agents

print(atlas_agents.__version__)
```

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
