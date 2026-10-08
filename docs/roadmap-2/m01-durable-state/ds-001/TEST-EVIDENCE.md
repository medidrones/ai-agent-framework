# Evidências de teste

## Baseline antes das alterações

| Gate | Resultado |
| --- | --- |
| `uv sync` | PASS |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS — 516 arquivos |
| `uv run mypy packages` | PASS — 333 arquivos fonte |
| `uv run pytest --cov --cov-branch --cov-report=term-missing` | PASS — 1.151 testes, 93,00% |
| `uv build` na raiz agregadora | NOT_VERIFIED — não aplicável; raiz não é pacote distribuível |

O erro do build na raiz foi a descoberta de múltiplos pacotes top-level. O gate
oficial do repositório é `uv build --package atlas-agent-core` e será registrado
no fechamento final.

## Evidência adicionada pela DS-001

Arquivo: `tests/runtime/test_checkpoint_contract_certification.py`.

- assinatura assíncrona exata de `CheckpointStore`;
- inventário estável dos campos v1;
- round-trip JSON determinístico e ausência do token;
- rejeição de dados extras/inválidos;
- leitura de fixture v1 versionada;
- propagação de falha do storage sem executar ferramenta;
- propagação de `CancelledError` sem executar ferramenta.

Execução direcionada com `--no-cov`: **7 passed**. O aviso único foi a falta de
permissão para gravar `.pytest_cache`, sem impacto nos testes.

## Cobertura existente reutilizada

`test_human_approval.py`, `test_human_approval_streaming.py`,
`test_memory_runtime.py`, `test_knowledge_runtime.py`,
`test_guardrail_runtime.py` e `test_observability_runtime.py` cobrem concorrência,
replay, expiração, corrupção, limites, timeout, budget, streaming, memória,
knowledge, guardrails e continuidade de trace.

## Gates finais

| Gate | Resultado final |
| --- | --- |
| `uv sync` | PASS — 79 pacotes resolvidos, 77 verificados |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS — 527 arquivos |
| `uv run mypy packages` | PASS — 334 arquivos fonte |
| `uv run pytest` | PASS — 1.158 testes, cobertura 93,01% |
| `uv build --package atlas-agent-core` | PASS — sdist e wheel `1.0.1` |
| `pip-audit` sobre o export de produção | PASS — nenhuma vulnerabilidade conhecida após atualizar PyJWT para 2.15.1 |

O pytest manteve um aviso não bloqueante: o Windows negou a criação do cache
local `.pytest_cache`. A coleta, execução, cobertura e saída do processo foram
concluídas com sucesso.
