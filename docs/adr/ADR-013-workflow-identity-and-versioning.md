# ADR-013 — Identidade e versionamento de workflows

- Status: aceita
- Data: 2026-10-19

## Decisão

Definição, execução de workflow, nó, tentativa de nó, execução de agente e
correlação possuem identificadores distintos. Versões de definição seguem PEP
440. Eventos possuem `schema_version` independente da versão da definição.

## Consequências

`tenant_id` é somente um fato de contexto e nunca prova autorização. Políticas
de autorização futuras recebem contexto confiável e devem falhar de forma
fechada em suas implementações.
