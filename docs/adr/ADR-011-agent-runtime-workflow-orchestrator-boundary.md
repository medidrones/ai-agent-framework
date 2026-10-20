# ADR-011 — Fronteira entre AgentRuntime e WorkflowOrchestrator

- Status: aceita
- Data: 2026-10-19

## Decisão

`AgentRuntime` permanece responsável por uma execução individual de agente. O
`WorkflowOrchestrator` coordena uma definição de workflow e delegará execuções
individuais ao runtime em implementações futuras. O core expõe somente o
protocolo assíncrono nesta etapa.

## Consequências

O runtime publicado não depende do orquestrador. A OR-001 não contém engine,
scheduler, paralelismo, worker ou implementação concreta de orquestração.
