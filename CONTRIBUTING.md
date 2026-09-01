# Como contribuir

Obrigado por contribuir com o Atlas Agent Framework.

## Pré-requisitos

- Python 3.12 ou superior
- uv
- Git

## Preparação do ambiente

A partir da raiz do repositório, instale o workspace e as dependências de
desenvolvimento:

```bash
uv sync
```

## Gates de qualidade

Execute as mesmas verificações usadas pela integração contínua:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages
uv run pytest
uv build --package atlas-agent-core
```

Opcionalmente, instale os hooks locais de pre-commit:

```bash
uv run pre-commit install
```

## Diretrizes para alterações

- Mantenha cada alteração concentrada em um objetivo coerente.
- Preserve a inversão de dependência e os contratos do core neutros de
  provedor.
- Adicione tipagem completa e documentação para APIs públicas.
- Adicione testes unitários e de fluxos negativos para mudanças de
  comportamento.
- Não adicione SDKs de provedores ou dependências de infraestrutura ao core.
- Registre decisões arquiteturais relevantes antes da implementação.

O código, os identificadores e as docstrings devem ser escritos em inglês. O
README e a documentação técnica devem ser escritos em português do Brasil.
