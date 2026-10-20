# ADR-012 — Modelo declarativo de workflows

- Status: aceita
- Data: 2026-10-19

## Decisão

Workflows são descritos por modelos Pydantic congelados: definição, nós e
conexões. `condition_ref` aceita apenas um nome simbólico; expressões e código
executável são proibidos. A OR-001 valida unicidade e referências, mas reserva
ciclos, ordenação topológica, gateways e joins para a OR-002.

## Consequências

Definições são provider-neutral, serializáveis em JSON e independentes de
infraestrutura. A presença de um `WorkflowNodeKind` não implica suporte de
execução nesta etapa.
