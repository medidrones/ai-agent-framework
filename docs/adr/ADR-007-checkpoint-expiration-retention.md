# ADR-007 — Expiração e retenção de checkpoints

## Status

Aceita em 2026-10-08.

## Decisão

O core define política, fatos temporais e classificação provider-neutral. O
PostgreSQL é a autoridade de tempo e persiste prazos absolutos. Um checkpoint
expira quando `clock_timestamp() >= expires_at`. Consumo grava, na mesma
transação, um tombstone sem payload. A DS-007 apenas classifica elegibilidade;
remoção física pertence à DS-008.

Mudanças futuras de política usam o maior prazo entre o persistido e o
recalculado. Assim, expansão estende a proteção e redução não antecipa purge.
Lease, recovery ativo, incompatibilidade e legal hold bloqueiam elegibilidade.

## Consequências

- o core continua sem dependência de banco;
- replay permanece detectável após consumo;
- expiração não equivale a exclusão;
- não há alegação de exactly-once para efeitos externos.
