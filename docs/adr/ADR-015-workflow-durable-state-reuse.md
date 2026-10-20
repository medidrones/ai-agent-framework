# ADR-015 — Reutilização do Durable State em workflows

- Status: aceita
- Data: 2026-10-19

## Decisão

Persistência futura de workflows deverá compor as capacidades certificadas do
M01, sem criar banco, lease, fencing ou `CheckpointStore` paralelo no core.
Um checkpoint de agente não será tratado como checkpoint completo de workflow.

## Consequências

A OR-001 define somente dados serializáveis. O mapeamento de estado, consumo
atômico e recovery de workflows exigirão contratos aditivos em tarefas futuras.
