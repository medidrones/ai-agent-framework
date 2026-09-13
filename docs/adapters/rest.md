# Adapter REST/FastAPI

`create_app()` cria uma aplicação FastAPI pertencente ao chamador. A factory
não inicia ASGI server e não define singleton global.

## Rotas v1

| Método | Rota | Semântica |
|---|---|---|
| `POST` | `/v1/executions` | execução completa |
| `POST` | `/v1/executions/stream` | execução por SSE |
| `POST` | `/v1/executions/resume` | retomada completa |
| `POST` | `/v1/executions/resume/stream` | retomada por SSE |
| `GET` | `/v1/health` | liveness local |
| `GET` | `/v1/readiness` | composição local |

Falhas funcionais do runtime, como `failed`, `rejected`, `timed_out`,
`limit_exceeded` e `budget_exceeded`, são respostas HTTP 200 com status no
payload. Erros de autenticação, autorização, validação e indisponibilidade são
erros do transporte.

## Autenticação e montagem

```python
from fastapi import Request

from atlas_agents.adapters import TransportPrincipal
from atlas_agents.adapters.rest import RESTAdapterConfig, create_app


class PrincipalFactory:
    async def create(self, request: Request) -> TransportPrincipal:
        # O middleware do host já validou a credencial.
        subject = request.state.authenticated_subject
        return TransportPrincipal(subject=subject, authentication_method="host")


app = create_app(
    service=service,
    principal_factory=PrincipalFactory(),
    config=RESTAdapterConfig(max_request_bytes=1_048_576),
)
```

Use TLS, autenticação e rate limiting no host ou gateway. O limite interno usa
`Content-Length`; o servidor ASGI ou proxy também deve limitar corpos chunked e
descompactados. Nunca copie campos de identidade do JSON para o principal.

## Streaming SSE

Cada item é emitido como `data: <json>` e preserva a sequência do runtime. O
último item representa resultado ou suspensão. O adapter fecha o gerador
upstream quando o cliente desconecta. Reconexão por `Last-Event-ID`, replay e
persistência de eventos não fazem parte deste contrato.

A chave de idempotência não streaming é enviada no header `Idempotency-Key`. O
token de retomada fica exclusivamente no body, nunca na rota ou query string.
