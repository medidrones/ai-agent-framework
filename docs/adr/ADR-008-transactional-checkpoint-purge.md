# ADR-008 — Purge transacional de checkpoints

## Status

Aceita na DS-008.

## Contexto

A DS-007 classifica retenção, mas não autoriza exclusão física. Uma consulta
prévia também não protege contra aquisição concorrente de lease, recovery ou
mudança de retenção.

## Decisão

O core expõe contrato provider-neutral, autorização explícita, limites e
resultados. O adapter PostgreSQL descobre lotes com `FOR UPDATE SKIP LOCKED`,
obtém advisory lock transacional por execução, revalida política, lease,
recovery, schema e legal hold, preserva tombstone, exclui e audita na mesma
transação. Lease e purge compartilham a disciplina de advisory lock.

`PURGED` só é retornado depois da confirmação do commit. Se essa confirmação
falhar, a auditoria é reconciliada; operações sem evidência durável retornam
`OUTCOME_UNKNOWN`.

## Consequências

- vários workers podem cooperar sem dupla exclusão;
- payloads não entram em descoberta, auditoria, métricas ou traces;
- tombstones são eliminados somente após sua janela explícita;
- não há scheduler, migration implícita ou garantia indefinida de replay;
- o host continua responsável por autenticar e autorizar o principal.
