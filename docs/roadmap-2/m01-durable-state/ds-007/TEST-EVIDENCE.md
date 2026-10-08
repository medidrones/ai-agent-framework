# Evidências de teste da DS-007

## Escopo

Testes unitários cobrem validação, fronteiras, precedência dos bloqueios e
mudança de política. Testes PostgreSQL cobrem migration, relógio do banco,
tombstone transacional, replay, tenant, lease/recovery e ausência de remoção.

## Execução final

Ambiente: Windows, Python 3.13.15 e PostgreSQL 16 Alpine real em Docker.

| Verificação | Resultado |
| --- | --- |
| `uv sync` | PASS |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS — 613 arquivos |
| `uv run mypy packages` | PASS — 357 arquivos-fonte |
| suíte PostgreSQL | PASS — 69 testes |
| `uv run pytest` com PostgreSQL | PASS — 1.260 testes |
| Cobertura branch | PASS — 92,64% |
| build core | PASS — wheel e sdist 1.0.1 |
| build adapters | PASS — wheel e sdist 1.0.1 |
| Bandit sobre `packages/*/src` | PASS — zero finding |
| `pip-audit` | PASS — nenhuma vulnerabilidade conhecida |

O aviso de cache do pytest decorre de permissão local em `.pytest_cache` e não
afetou coleta, execução nem cobertura. Os testes PostgreSQL incluem igualdade
de expiração, rollback autorizado, tombstone sem payload, replay, isolamento,
lease, recovery, corrida após descoberta e baseline de 30 amostras.
