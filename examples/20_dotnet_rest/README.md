# Consumidor .NET REST

## Propósito

Comprovar interoperabilidade via HttpClient, SSE e resume no corpo.

## Conceitos demonstrados

DTOs externos, execute, stream e HITL resume.

## Arquitetura

Cliente .NET → transporte versionado → AgentExecutionService → AgentRuntime.

## Pré-requisitos

.NET SDK 8 ou superior e um adapter Atlas compatível em execução.

## Instalação

`dotnet restore` no diretório do projeto. Em outro terminal, inicie o servidor
com `uv run python examples/16_rest/main.py --serve`.

## Como executar

`dotnet run --project examples/20_dotnet_rest/dotnet/Atlas.Rest.Client.Example -- http://127.0.0.1:8000`

## Saída esperada

Status HTTP, eventos SSE e retomada quando houver suspensão.

## Segurança

Autenticação anônima, HTTP sem TLS e endpoints locais são somente para desenvolvimento. Em produção, use identidade verificada, TLS e autorização.

## Considerações para produção

Substitua fixtures por adapters explícitos, defina limites, timeouts, autenticação, autorização, persistência e telemetria conforme o ambiente. Preserve a direção de dependências para os contratos públicos.

## Pacotes Atlas relacionados

atlas-agent-adapters[rest] e .NET 8 LTS. Consulte também a [visão arquitetural](../../docs/architecture/overview.md) e o [índice dos exemplos](../README.md).
