# Evidências de teste

Baseline/working tree: `c93a761a033f3239af0f4a68a93f6e0b9334a792`, Python
3.13.15, Redis 7.4.11, PostgreSQL 16, execução em 2026-10-08.

| Gate | Comando | Resultado |
| --- | --- | --- |
| sync | `uv sync --locked` | PASS, exit 0 |
| lint | `uv run ruff check .` | PASS, exit 0 |
| formato | `uv run ruff format --check .` | PASS, 677 arquivos |
| tipos | `uv run mypy packages` | PASS, 373 arquivos |
| regressão real | `uv run pytest --cov --cov-branch` | 1.389 PASS, 92,63% |
| Redis focado | três módulos Redis | 65 PASS |
| core build | `uv build --package atlas-agent-core` | PASS |
| adapter build | `uv build --package atlas-agent-adapters` | PASS |
| metadata | `uvx twine check ...` | 4 artefatos PASS |
| clean install | wheels locais, Python 3.12.6 | PASS |
| segurança | Bandit + pip-audit | PASS |

O único aviso foi a impossibilidade de gravar `.pytest_cache` por permissão no
Windows; não alterou coleta, execução nem resultado.
