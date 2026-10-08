# ADR-009 — Retomada atômica e fencing no Redis

## Status

Aceita em 2026-10-08.

## Contexto

A DS-010 certificou o consumo atômico de um checkpoint em uma única chave, mas
não expôs ownership Redis nem uma tentativa estável para reconciliar respostas
perdidas. Validar um lease em PostgreSQL e depois consumir no Redis criaria uma
janela sem transação entre as duas autoridades.

## Decisão

O adapter mantém o lease, sua geração de fencing e o checkpoint no mesmo hash
Redis. Scripts Lua estáticos validam estado, tempo do servidor, revisão,
identidade, owner e geração antes da mutação. O hash tag é específico por
checkpoint, preservando um slot único sem concentrar todo o namespace.

A API pública 1.x permanece inalterada. As operações de lease, CAS protegido,
consumo protegido e reconciliação identificada são capabilities aditivas do
adapter. Uma tentativa identificada persiste seu `operation_id` no mesmo ponto
de linearização do consumo.

## Consequências

- workers obsoletos são rejeitados pelo Redis antes da mutação;
- o fencing é válido somente quando lease e checkpoint usam a mesma autoridade;
- Cluster e Sentinel não são anunciados sem certificação real;
- a confirmação depende da durabilidade configurada no Redis;
- efeitos externos continuam exigindo idempotência ou fencing próprios.
