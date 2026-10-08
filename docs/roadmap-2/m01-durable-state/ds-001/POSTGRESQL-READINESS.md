# Prontidão para adapter PostgreSQL

## Mapeamento recomendado

Uma tabela pode armazenar hash do token, payload JSON/JSONB, versão do
checkpoint, timestamps e estado físico. `save` deve ser create-only; `consume`
deve usar transação e alteração condicional com retorno do payload, garantindo
uma única vencedora entre instâncias.

| Capacidade | Classificação | Observação |
| --- | --- | --- |
| Save/Read | GAP | save está definido; read sem consumo é `MISSING` |
| Consumo atômico | READY | transação/`DELETE ... RETURNING` pode cumprir o contrato |
| Concorrência | GAP | consumo básico definido; sem revisão/lease |
| Controle de versão | GAP | schema versionado; revisão física e upcaster ausentes |
| Expiração | GAP | sem expiração normativa do checkpoint |
| Retenção | GAP | sem política de cleanup/purge |
| Recuperação após restart | GAP | payload persiste; claim/receipt e enumeração ausentes |
| Integridade de dados | READY | validação Pydantic e transação permitem implementação correta |
| Idempotência | GAP | consumo único não garante idempotência do efeito externo |

## Decisão

O contrato é suficiente para um adapter PostgreSQL mínimo de `save/consume`,
mas não para alegar recuperação durável completa nem exactly-once. Antes da
DS-002, `DS001-GAP-001` precisa de decisão arquitetural formal; as demais
lacunas devem ser resolvidas ou explicitamente atribuídas ao adapter.
