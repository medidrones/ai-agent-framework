# ADR-005 — Lease e fencing de checkpoints no PostgreSQL

## Status

Aceita em 2026-10-08.

## Decisão

O core expõe os contratos provider-neutral `CheckpointLease` e
`CheckpointLeaseManager`. O adapter PostgreSQL mantém ownership em uma tabela
dedicada e preserva a geração de fencing após release e expiração.

O relógio e a atomicidade do PostgreSQL determinam validade, aquisição,
renovação e liberação. Escritas CAS e consumo autorizado que exigem ownership
usam operações aditivas que validam owner e fencing token na mesma instrução
SQL da alteração protegida.

## Consequências

- o core não depende de driver ou banco de dados;
- APIs 1.x existentes permanecem disponíveis;
- stale workers são rejeitados nas operações protegidas pelo adapter;
- efeitos externos continuam dependendo de idempotência ou fencing próprio;
- coordenação automática de recovery permanece para a DS-006.
