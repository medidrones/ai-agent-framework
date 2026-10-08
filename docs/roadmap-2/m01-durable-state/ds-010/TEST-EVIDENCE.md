# Evidências de teste da DS-010

## Escopo Redis

- 39 testes unitários sem servidor externo;
- 14 testes de integração com Redis real;
- 3 testes HITL com Redis real;
- concorrência: 20 consumidores e 12 writers;
- restart do processo e restart AOF do servidor;
- schema, corrupção, identidade, namespace, TTL, tombstone e ownership;
- cliente indisponível e preservação de cancelamento;
- benchmark com 3.000 ciclos e 100 workers.

## Ambiente Redis certificado

Redis 7.4.11 standalone, AOF ativo, `appendfsync always`, `noeviction` e
redis-py 6.4.0. Sentinel e Cluster: `NOT_APPLICABLE`, pois não foram declarados
como suportados nesta tarefa.

## Gates executados

| Verificação | Resultado |
| --- | --- |
| Suíte com PostgreSQL e Redis reais | 1.380 aprovados, 0 falhas, 0 skips |
| Cobertura com serviços reais | 92,89% |
| Suíte sem serviços externos | 1.267 aprovados, 113 skips explícitos |
| Cobertura sem serviços externos | 90,11% |
| Ruff | 676 arquivos, PASS |
| mypy | 373 arquivos, PASS |
| Build/Twine | 3 wheels + 3 sdists, PASS |
| Wheel clean-install Python 3.12 | save/read/consume, PASS |
| Bandit em código de produção | 0 findings, PASS |
| pip-audit produção + redis 6.4.0 | 0 vulnerabilidades, PASS |
| Artifact secret scan | 6 artefatos, 0 findings |
| Restart AOF | save/restart/read/consume, PASS |

O warning de cache do pytest no Windows não altera testes ou cobertura: o
diretório `.pytest_cache` estava sem permissão de escrita, e a suíte concluiu.
