# Arquitetura da OR-001

```text
Aplicação host
    ↓
WorkflowDefinition + WorkflowInput + WorkflowContext
    ↓
WorkflowOrchestrator (protocolo, sem implementação na OR-001)
    ├── políticas explícitas
    ├── eventos e resultados funcionais
    ├── futuro uso do Durable State M01
    └── futura delegação → AgentRuntime → agente individual
```

As dependências apontam para os contratos do core. O namespace
`atlas_agents.orchestration` não importa adapters, providers, bancos, brokers ou
Kubernetes. `AgentRuntime` não conhece `WorkflowOrchestrator`.

## Escopo preservado

Esta entrega não contém scheduler, engine de DAG, workers, paralelismo, retry,
compensação ou persistência. A validação completa do grafo pertence à OR-002.
