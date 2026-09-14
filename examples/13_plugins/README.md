# Plugin

## Propósito

Descobrir, carregar, ativar e desativar um plugin instalado por entry point.

## Conceitos demonstrados

Plugin API, discovery e lifecycle.

## Arquitetura

Host do exemplo → API pública Atlas → contratos injetados → resultado observável.

## Pré-requisitos

Python 3.12+ e `uv`. O cenário padrão não exige rede.

## Instalação

`uv sync` na raiz do repositório.

## Como executar

`uv pip install --editable examples/13_plugins/example_plugin --no-deps` e,
depois, `uv run python examples/13_plugins/main.py`.

## Saída esperada

Plugin ativado, contribuição registrada e cleanup.

## Segurança

Fixtures e identidades locais existem apenas para demonstração. Não registre prompts, tokens, argumentos sensíveis ou credenciais.

## Considerações para produção

Substitua fixtures por adapters explícitos, defina limites, timeouts, autenticação, autorização, persistência e telemetria conforme o ambiente. Preserve a direção de dependências para os contratos públicos.

## Pacotes Atlas relacionados

atlas-agent-core. Consulte também a [visão arquitetural](../../docs/architecture/overview.md) e o [índice dos exemplos](../README.md).
