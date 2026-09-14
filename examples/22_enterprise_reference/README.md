# Referência corporativa

## Propósito

Consolidar a arquitetura Atlas em um cenário de suporte sem serviços reais.

## Conceitos demonstrados

config, memória, RAG, citação, MCP, HITL, guardrails, telemetria e avaliação.

## Arquitetura

Host do exemplo → API pública Atlas → contratos injetados → resultado observável.

## Pré-requisitos

Python 3.12+ e `uv`. O cenário padrão não exige rede.

## Instalação

`uv sync` na raiz do repositório.

## Como executar

`uv run python examples/22_enterprise_reference/main.py`

## Saída esperada

Execução concluída, uma citação, HITL verdadeiro e avaliação aprovada.

## Segurança

Fixtures e identidades locais existem apenas para demonstração. Não registre prompts, tokens, argumentos sensíveis ou credenciais.

## Considerações para produção

Substitua fixtures por adapters explícitos, defina limites, timeouts, autenticação, autorização, persistência e telemetria conforme o ambiente. Preserve a direção de dependências para os contratos públicos.

## Pacotes Atlas relacionados

atlas-agent-framework, atlas-agent-config, atlas-agent-evaluation e atlas-agent-mcp. Consulte também a [visão arquitetural](../../docs/architecture/overview.md) e o [índice dos exemplos](../README.md).
