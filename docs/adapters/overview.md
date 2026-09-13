# Adapters externos

A distribuição opcional `atlas-agent-adapters` expõe o runtime Atlas por REST,
gRPC e mensageria sem transferir para os transportes a propriedade do loop de
execução. Todos os adapters convergem para `AgentExecutionService`, uma fachada
provider-neutral com quatro operações: `execute`, `stream`, `resume` e
`resume_stream`.

```text
HTTP / gRPC / broker
        ↓
DTO e autenticação do transporte
        ↓
AgentExecutionService
        ↓
AgentRegistry + policies explícitas
        ↓
AgentRuntime (core)
```

O pacote depende do core; o core não conhece FastAPI, gRPC, protobuf nem
brokers. A aplicação hospedeira cria e injeta runtime, agentes, autenticação,
autorização, limites, budget e idempotência. Nenhum adapter abre portas, inicia
servidores, conecta em brokers, lê variáveis de ambiente ou cria estado global.

## Instalação

```bash
uv add atlas-agent-adapters
```

Os contratos públicos ficam em `atlas_agents.adapters`. Os módulos
`atlas_agents.adapters.rest`, `atlas_agents.adapters.grpc` e
`atlas_agents.adapters.events` contêm as integrações de transporte.

## Composição mínima

`AgentExecutionService` exige políticas explícitas. `AllowAllAgentAccessPolicy`
existe para ambientes internos confiáveis, mas seu uso precisa ser uma decisão
visível do host.

```python
from atlas_agents.adapters import (
    AgentExecutionService,
    AgentRegistry,
    AllowAllAgentAccessPolicy,
    BoundedExecutionPolicyResolver,
    SubjectExecutionIdentityMapper,
)
from atlas_agents.runtime import ExecutionLimits

agents = AgentRegistry()
agents.register(agent_definition)

service = AgentExecutionService(
    runtime=runtime,
    agent_registry=agents,
    identity_mapper=SubjectExecutionIdentityMapper(),
    access_policy=AllowAllAgentAccessPolicy(),
    policy_resolver=BoundedExecutionPolicyResolver(
        maximum_limits=ExecutionLimits(max_turns=10, timeout_seconds=60),
    ),
)
```

O exemplo deliberadamente não cria runtime nem agente concretos: essas
dependências pertencem ao bootstrap da aplicação.

## Garantias comuns

- identidade é derivada de um principal autenticado pelo host, nunca do body;
- autorização ocorre antes de qualquer chamada ao runtime;
- limites pedidos pelo cliente são reduzidos aos tetos do servidor;
- erros externos usam códigos estáveis e mensagens seguras;
- resultados funcionais do runtime, inclusive falha e timeout, continuam sendo
  respostas de aplicação;
- tokens de retomada não entram em URL, representação de objetos ou eventos;
- streams preservam ordem, backpressure e fechamento cooperativo.

Consulte os guias de [serviço de execução](execution-service.md),
[REST](rest.md), [gRPC](grpc.md), [mensageria](event-driven.md),
[segurança](security.md) e [versionamento](versioning.md).
