# ADR-014 — Eventos funcionais versus observabilidade

- Status: aceita
- Data: 2026-10-19

## Decisão

`WorkflowEvent` registra fatos funcionais versionados e recuperáveis. Métricas,
spans e logs continuam pertencendo aos contratos best-effort de observabilidade.

## Consequências

O resultado funcional não incorpora telemetria. A OR-001 não implementa event
bus, broker ou exportador distribuído.
