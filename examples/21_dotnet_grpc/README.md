# Consumidor .NET gRPC

## Propósito

Gerar o cliente a partir do proto oficial e usar cancellation/deadline.

## Conceitos demonstrados

ExecuteAsync, streaming, ResumeAsync e protobuf.

## Arquitetura

Cliente .NET → transporte versionado → AgentExecutionService → AgentRuntime.

## Pré-requisitos

.NET SDK 8 ou superior e um adapter Atlas compatível em execução.

## Instalação

`dotnet restore` no diretório do projeto. Em outro terminal, inicie o servidor
com `uv run python examples/17_grpc/main.py --serve`.

## Como executar

`dotnet run --project examples/21_dotnet_grpc/dotnet/Atlas.Grpc.Client.Example -- http://127.0.0.1:50051`

## Saída esperada

Status unary, eventos gRPC e retomada quando houver suspensão.

## Segurança

Autenticação anônima, HTTP sem TLS e endpoints locais são somente para desenvolvimento. Em produção, use identidade verificada, TLS e autorização.

## Considerações para produção

Substitua fixtures por adapters explícitos, defina limites, timeouts, autenticação, autorização, persistência e telemetria conforme o ambiente. Preserve a direção de dependências para os contratos públicos.

## Pacotes Atlas relacionados

atlas-agent-adapters[grpc], Grpc.Net.Client e .NET 8 LTS. Consulte também a [visão arquitetural](../../docs/architecture/overview.md) e o [índice dos exemplos](../README.md).
