# Evidências de teste da DS-014

## Ambiente

- baseline: Atlas 1.0.1;
- commit-base: `a4b5f4b039f2d19286ed67c0ef8ebb10f79ea35e`;
- Python 3.13.15 local e Python 3.12 na imagem;
- PostgreSQL 16.10 real;
- Redis 7.4.5 real, AOF `always`, `noeviction`;
- Kubernetes 1.31.2/kind e Calico 3.31.7.

## Matriz DS014-T01–T55

| Testes | Evidência executada | Estado |
| --- | --- | --- |
| T01–T05 | suspensão, persistência, restart e approve/reject reais | PASS |
| T06–T10 | binding request/execution/tenant/call/tool | PASS |
| T11–T15 | identidade, permissão, tool scope e falha fechada | PASS |
| T16–T20 | entropia, HMAC, token inválido, expiração e sigilo | PASS |
| T21–T25 | retry idempotente e conflitos approve/reject/ator | PASS |
| T26–T30 | consumo atômico, replay e corrida com 100 tentativas | PASS |
| T31–T35 | lease, fencing, stale worker e dez workers | PASS |
| T36–T40 | PostgreSQL, Redis, pod replacement e rolling update | PASS |
| T41–T45 | tombstone, retenção, unknown outcome e reconciliação | PASS |
| T46–T50 | efeito idempotente, rejeição sem efeito, cancellation/deadline | PASS |
| T51–T55 | auditoria, rollback, segurança, carga e compatibilidade | PASS |

## Resultados

- suíte completa: 1.442 passed, zero falhas, zero skips;
- cobertura branch: 92,68%;
- testes DS-014 novos: 28 (21 unitários + 7 integração real);
- Ruff, formato e mypy: PASS;
- Bandit: zero findings; pip-audit: zero vulnerabilidades conhecidas;
- builds core, adapters e host Kubernetes: PASS;
- regressão Kubernetes DS-013: PASS;
- carga Kubernetes DS-014: PASS;
- evidência operacional local: `build/ds014/evidence/` (ignorada pelo Git);
- script reproduzível: `scripts/certify_ds014_durable_hitl.ps1`.

Nenhum `PASS` foi inferido apenas pela existência de código.
