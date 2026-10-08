# Evidências de testes

Baseline certificado: commit `2187bcd999f470a3553048ad6fb5b3c4497c68b1`,
branch de trabalho `medicode/ds-012-failure-crash-recovery`, Atlas 1.0.1.

| Verificação | Resultado |
| --- | --- |
| `uv sync` | PASS |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS, 697 arquivos |
| `mypy packages` | PASS, 375 arquivos |
| `pytest` com PostgreSQL/Redis reais | 1.408 passed, 0 failed, 0 skipped |
| cobertura branch | 92,68% (mínimo 90%) |
| processo abrupto PostgreSQL/Redis | PASS |
| restart de servidor PostgreSQL/Redis | PASS/PASS |
| wheels e sdists core/adapters | PASS |
| instalação limpa Python 3.12 | PASS |
| smoke de imports instalado | PASS |

O aviso `PytestCacheWarning` decorre de permissão local da `.pytest_cache` e não
afetou coleta, execução ou cobertura. Artefatos locais preexistentes em
`reports/release` não fazem parte da DS-012.
