# Adapter gRPC

## Propósito

Executar chamadas unary e streaming em servidor gRPC efêmero.

## Conceitos demonstrados

proto v1, servicer oficial e deadline do transporte.

## Arquitetura

Host do exemplo → API pública Atlas → contratos injetados → resultado observável.

## Pré-requisitos

Python 3.12+ e `uv`. O cenário padrão não exige rede.

## Instalação

`uv sync` na raiz do repositório.

## Como executar

`uv run python examples/17_grpc/main.py`

## Saída esperada

Status completed e quantidade de itens do stream.

## Segurança

Fixtures e identidades locais existem apenas para demonstração. Não registre prompts, tokens, argumentos sensíveis ou credenciais.

## Considerações para produção

Substitua fixtures por adapters explícitos, defina limites, timeouts, autenticação, autorização, persistência e telemetria conforme o ambiente. Preserve a direção de dependências para os contratos públicos.

## Pacotes Atlas relacionados

atlas-agent-adapters[grpc]. Consulte também a [visão arquitetural](../../docs/architecture/overview.md) e o [índice dos exemplos](../README.md).
