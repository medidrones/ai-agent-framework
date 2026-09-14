# Agente mínimo

## Propósito

Executar o menor agente Atlas funcional, totalmente offline e determinístico.

## Conceitos demonstrados

AgentDefinition, AgentRuntime e provider injetado.

## Arquitetura

Host do exemplo → API pública Atlas → contratos injetados → resultado observável.

## Pré-requisitos

Python 3.12+ e `uv`. O cenário padrão não exige rede.

## Instalação

`uv sync` na raiz do repositório.

## Como executar

`uv run python examples/01_minimal_agent/main.py`

## Saída esperada

`Atlas agent is running.`

## Segurança

Fixtures e identidades locais existem apenas para demonstração. Não registre prompts, tokens, argumentos sensíveis ou credenciais.

## Considerações para produção

Substitua fixtures por adapters explícitos, defina limites, timeouts, autenticação, autorização, persistência e telemetria conforme o ambiente. Preserve a direção de dependências para os contratos públicos.

## Pacotes Atlas relacionados

atlas-agent-core. Consulte também a [visão arquitetural](../../docs/architecture/overview.md) e o [índice dos exemplos](../README.md).
