# Human-in-the-loop

## Propósito

Suspender antes do efeito, aprovar ou rejeitar e retomar por token opaco.

## Conceitos demonstrados

HITL, checkpoint, approval e resume.

## Arquitetura

Host do exemplo → API pública Atlas → contratos injetados → resultado observável.

## Pré-requisitos

Python 3.12+ e `uv`. O cenário padrão não exige rede.

## Instalação

`uv sync` na raiz do repositório.

## Como executar

`uv run python examples/07_human_in_the_loop/main.py`

## Saída esperada

Caminhos APROVAR e REJEITAR com contagem de chamadas.

## Segurança

Fixtures e identidades locais existem apenas para demonstração. Não registre prompts, tokens, argumentos sensíveis ou credenciais.

## Considerações para produção

Substitua fixtures por adapters explícitos, defina limites, timeouts, autenticação, autorização, persistência e telemetria conforme o ambiente. Preserve a direção de dependências para os contratos públicos.

## Pacotes Atlas relacionados

atlas-agent-core. Consulte também a [visão arquitetural](../../docs/architecture/overview.md) e o [índice dos exemplos](../README.md).
