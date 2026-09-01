# Atlas Agent Framework

Atlas é um framework Python reutilizável e independente de provedor para
definir, compor, executar e avaliar agentes de IA.

Este repositório contém a infraestrutura de um framework, não uma aplicação de
negócio. O pacote principal define contratos estáveis, enquanto pacotes
opcionais integrarão provedores de modelos, sistemas de armazenamento,
transportes e ferramentas de observabilidade.

## Situação atual

O projeto está na fase de fundação. A versão atual estabelece o workspace, o
pacote, os gates de qualidade e as regras arquiteturais de dependência. O
comportamento de execução dos agentes ainda não foi implementado
intencionalmente.

## Requisitos

- Python 3.12 ou superior
- [uv](https://docs.astral.sh/uv/)

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

O pacote utiliza o layout `src` e pode ser importado da seguinte forma:

```python
import atlas_agents

print(atlas_agents.__version__)
```

Consulte [ARCHITECTURE.md](ARCHITECTURE.md) para conhecer o desenho de alto
nível e
[docs/architecture/dependency-rules.md](docs/architecture/dependency-rules.md)
para conferir as restrições de dependência aplicáveis.

## Contribuição e segurança

As diretrizes de desenvolvimento estão descritas em
[CONTRIBUTING.md](CONTRIBUTING.md). Relate problemas de segurança pelo processo
privado definido em [SECURITY.md](SECURITY.md).

## Licença

O Atlas Agent Framework é disponibilizado sob a [Licença MIT](LICENSE).
