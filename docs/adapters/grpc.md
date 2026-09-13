# Adapter gRPC

O contrato protobuf usa o package versionado `atlas.agent.v1`. O arquivo
canônico e o código Python gerado são versionados no repositório e distribuídos
com o pacote.

O serviço oferece `Execute`, `Stream`, `Resume` e `ResumeStream`. Operações
streaming usam server streaming e respeitam backpressure nativo. O deadline
restante do contexto gRPC restringe o timeout pedido para uma execução nova;
cancelamento encerra o iterador do runtime.

## Registro explícito

```python
import grpc

from atlas_agents.adapters.grpc import add_agent_execution_servicer

server = grpc.aio.server(interceptors=[authentication_interceptor])
add_agent_execution_servicer(
    server=server,
    service=service,
    principal_factory=principal_factory,
)

# O host escolhe credenciais, endereço, porta, start e shutdown.
```

`principal_factory` deve usar somente uma identidade autenticada pelo host ou
por interceptor. O adapter lê apenas a metadata configurada para idempotência;
o token de retomada permanece no campo protobuf do request.

## Evolução do protobuf

Campos existentes não devem mudar de número ou significado. Ao remover um
campo, reserve seu número e nome. Adições compatíveis usam novos números e
defaults seguros. Alterações incompatíveis exigem um novo package, como
`atlas.agent.v2`. Recompile e versione os módulos `_pb2.py`, `_pb2.pyi` e
`_pb2_grpc.py` junto com o `.proto`.

TLS/mTLS, reflection, interceptors, tamanho máximo de mensagem e limites de
concorrência são responsabilidades do servidor hospedeiro.
