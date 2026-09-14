# Provider OpenAI

## Propósito

Mostrar a injeção explícita do cliente e do provider OpenAI pelo host.

## Conceitos demonstrados

OpenAIModelProvider, AsyncOpenAI e seleção de modelo.

## Arquitetura

Host do exemplo → API pública Atlas → contratos injetados → resultado observável.

## Pré-requisitos

Python 3.12+, `uv` e uma chave OpenAI válida.

## Instalação

`uv sync` e defina `OPENAI_API_KEY` apenas no ambiente do processo; use `.env.example` como referência.

## Como executar

`uv run python examples/02_openai_agent/main.py`

## Saída esperada

Uma resposta do modelo configurado.

## Segurança

A chave é lida pelo host e injetada no cliente; nunca é armazenada, serializada ou registrada.

## Considerações para produção

Substitua fixtures por adapters explícitos, defina limites, timeouts, autenticação, autorização, persistência e telemetria conforme o ambiente. Preserve a direção de dependências para os contratos públicos.

## Pacotes Atlas relacionados

atlas-agent-core e atlas-agent-providers[openai]. Consulte também a [visão arquitetural](../../docs/architecture/overview.md) e o [índice dos exemplos](../README.md).
