# Visão geral da arquitetura

O Atlas Agent Framework é um SDK Python modular cujo centro estável é um core
pequeno e neutro de provedor. Aplicações podem usar esse core diretamente ou
compor providers, plugins, adapters, MCP, configuração e avaliação por
distribuições opcionais.

## Propósito e escopo

O framework fornece contratos e componentes reutilizáveis para agentes de IA
sem incorporar uma aplicação ou domínio de negócio. O runtime coordena
lifecycle, chamadas completas e streaming, ciclos multi-turn, ferramentas,
aprovação humana, memória, Knowledge/RAG, guardrails e observabilidade.

A versão `1.1.0` adiciona o **Durable State** certificado pelo M01 do Roadmap 2:
checkpoints PostgreSQL e Redis, concorrência otimista, consumo autorizado
atômico, leases, fencing, retenção, purge, recovery distribuído e HITL durável.
Essas integrações permanecem fora do core e preservam os contratos públicos da
linha 1.x.

## Direção das dependências

```text
Aplicações e serviços
        ↓
Configuração · adapters · plugins · providers · MCP
        ↓
Contratos públicos do atlas-agent-core
```

As dependências de código apontam para os contratos do core. O core não depende
de SDKs de modelos, frameworks web, bancos de dados, brokers, bancos vetoriais
ou ferramentas concretas de telemetria.

## Distribuições

- `atlas-agent-core`: contratos, lifecycle, runtime e políticas
  provider-neutral;
- `atlas-agent-providers`: providers opcionais, incluindo OpenAI;
- `atlas-agent-adapters`: REST, gRPC, mensageria e stores PostgreSQL/Redis;
- `atlas-agent-mcp`: cliente e servidor Model Context Protocol;
- `atlas-agent-config`: configuração declarativa e composition root;
- `atlas-agent-evaluation`: datasets, evaluators, scoring e relatórios;
- `atlas-agent-framework`: meta-package para a experiência integrada.

As sete distribuições estão publicadas separadamente para manter dependências de
infraestrutura opcionais.

## Responsabilidades do core

- definir modelos imutáveis e tipados nas fronteiras públicas;
- validar lifecycle, estado, eventos e resultados;
- abstrair modelos e providers sem expor objetos específicos de SDKs;
- coordenar execução completa, streaming e ciclos multi-turn;
- aplicar limites, budget, timeout e cancellation;
- registrar, autorizar, validar e executar ferramentas conhecidas;
- suspender e retomar execuções HITL por contratos de checkpoint;
- integrar memória, Knowledge/RAG, guardrails e observabilidade por injeção;
- preservar compatibilidade retroativa e evitar infraestrutura obrigatória.

## Durable State

O `CheckpointStore` permanece como contrato público mínimo. Capabilities
opcionais adicionam garantias mais fortes sem ampliar a responsabilidade do
`AgentRuntime`. PostgreSQL fornece transações e autoridade temporal; Redis
fornece operações atômicas por Lua e garantias condicionadas à configuração de
persistência e topologia.

```text
AgentRuntime
    ↓ contratos/capabilities
CheckpointStore
    ├── PostgreSQL: transações · CAS · leases · fencing · migrations
    └── Redis: Lua · CAS · leases · fencing · TTL
            ↓
RecoveryCoordinator · Durable HITL · retenção/purge
```

O M01 certificou recovery após crash e restart, concorrência distribuída,
cenários Kubernetes, segurança e desempenho. A propriedade de autorização
preservada é `one approval → one resume → one side effect`; ela não representa
exactly-once para efeitos externos, que continuam exigindo idempotência e
reconciliação na aplicação.

## Estado do roadmap

- Roadmap 1 — Foundation: `COMPLETE`;
- Roadmap 2 / M01 — Durable State: `COMPLETE`, `CERTIFIED` e publicado na
  versão `1.1.0`;
- próximo marco planejado: M02 — Enterprise Memory, ainda não iniciado.

Consulte a [arquitetura implementada](implemented-architecture.md), o
[índice do Roadmap 2](../roadmap-2/README.md) e as
[regras de dependência](dependency-rules.md).
