# Como contribuir

Obrigado por contribuir com o Atlas Agent Framework.

## Pré-requisitos

- Python 3.12 ou superior
- uv
- GNU Make 4 ou superior
- Git

## Preparação do ambiente

A partir da raiz do repositório, instale o workspace e as dependências de
desenvolvimento:

```bash
uv sync
```

## Criação de branch

Crie uma branch curta a partir da revisão atual da branch principal. Use um
nome que descreva o objetivo da alteração e evite misturar refatorações não
relacionadas.

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

## Testes e documentação

Toda mudança de comportamento deve incluir testes do fluxo esperado e dos
principais fluxos negativos. APIs públicas exigem docstrings em inglês e
documentação técnica em português do Brasil. Não documente APIs que ainda não
existem.

## APIs públicas e dependências

Alterações incompatíveis em APIs públicas precisam de justificativa,
estratégia de migração e registro no changelog. Antes de incluir uma dependência,
confirme que a biblioteca é necessária, mantida e compatível com a camada. SDKs
de infraestrutura devem permanecer fora do core.

## Pull requests

Um pull request deve ter escopo claro, explicar a decisão adotada, relacionar
testes e comandos executados e registrar riscos restantes. Todos os gates de
qualidade e o build devem passar antes da revisão final.

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
