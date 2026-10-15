# Quality gates da DS-016

Execução em 15/10/2026, Python 3.12.6, candidato `89f00df`.

| Comando/gate | Resultado |
| --- | --- |
| `uv sync` | PASS |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS — 783 arquivos |
| `uv run mypy packages` | PASS — 375 arquivos |
| `uv run pytest` com PostgreSQL/Redis reais | PASS — 1.455 passed, 0 failed, 0 skipped |
| branch coverage | PASS — 92,68% (mínimo 90%) |
| build `atlas-agent-core` | PASS — wheel e sdist |
| build `atlas-agent-adapters` | PASS — wheel e sdist |
| validação dos artefatos 1.0.1 | PASS — 14 artefatos |
| instalação limpa | PASS — três ambientes isolados |
| Bandit | PASS — zero findings |
| pip-audit | PASS — zero vulnerabilidades conhecidas |

O primeiro pytest dentro do sandbox revelou bloqueio do `socketpair` interno do
asyncio no Windows. A pilha apontou `socket._fallback_socketpair`, não código do
Atlas. A execução autorizada fora do sandbox e contra serviços reais passou.
O único aviso final foi a impossibilidade de atualizar `.pytest_cache`, sem
efeito em testes ou cobertura.

**Decisão:** `QUALITY_GATES = PASS`.
