# Evidências de teste da DS-009

Baseline do repositório: `fc33044dfd73fbc305604ece9e1dc4f71c455be8`,
Atlas 1.0.1. Ambiente PostgreSQL real: 16.14 Alpine em container isolado.

## Suíte específica

`test_postgresql_schema_migrations.py` cobre:

- checker sem mutação em banco não inicializado;
- fresh install e idempotência;
- upgrade 5→7 com dados e fencing preservados;
- rolling expansion 6→7;
- versão desconhecida, checksum adulterado, índice e coluna removidos;
- dois migration runners;
- rollback de DDL + histórico;
- cancelamento aguardando advisory lock;
- runtime com DML e sem DDL;
- indisponibilidade sem vazamento;
- alvo inválido antes de I/O.

Resultado específico: 13 PASS, 0 FAIL, 0 SKIP.

## Regressão PostgreSQL

As suítes DS-002–DS-009 e os contratos unitários executaram em PostgreSQL real:
124 PASS, 0 FAIL e 0 SKIP. A suíte integral executou 1.324 testes: 1.324 PASS,
0 FAIL, 0 SKIP, com 92,85% de branch coverage. Sem PostgreSQL, o gate de
compatibilidade executou 1.228 PASS e 96 skips esperados, com 90,04%.

## Benchmark

O script reproduzível executou nove access paths, 10.000 registros e 20
amostras. O resultado detalhado está em `PERFORMANCE-BASELINE.md` e
`INDEX-ANALYSIS.md`.

## Segurança e distribuição

Ruff validou 649 arquivos; mypy validou 363 arquivos. Core e adapters geraram
wheel e sdist, os quatro artefatos passaram no Twine e a migration 007 foi
confirmada no wheel e no sdist. O smoke isolado instalou os wheels, aplicou
001–007 em banco vazio e retornou `SCHEMA_COMPATIBLE`. Bandit não encontrou
findings médios/altos e pip-audit não encontrou vulnerabilidades conhecidas.
