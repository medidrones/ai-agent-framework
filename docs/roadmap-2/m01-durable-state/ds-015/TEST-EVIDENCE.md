# Evidências de teste

## Baseline e ambiente

- pré-requisito: DS-014 `COMPLETE`, 33/33 gates;
- commit de entrada: `92ffe70948e1755ce4a4f9ab95157dd731d824ee`;
- Atlas: `1.0.1`;
- Python: `3.13.15`;
- PostgreSQL real: `16.14`;
- Redis real: `7.4.11`, AOF e `appendfsync=always`;
- thresholds definidos em `PERFORMANCE-THRESHOLDS.md` antes dos ensaios finais.

## Resultados reproduzíveis

| Evidência | Resultado |
| --- | --- |
| matriz de payload | 1 KiB, 16 KiB, 256 KiB e 1 MiB executados |
| concorrência | 1, 10, 50, 100, 250 e 500 workers executados |
| contenção | um vencedor em consume, CAS e lease; 0 violações |
| soak PostgreSQL | 3.600,073 s; 1.096.355 ciclos; `PASS` |
| soak Redis | 3.600,056 s; 1.358.054 ciclos; `PASS` |
| fault PostgreSQL | falha observada, recuperação confirmada, 0 falso sucesso |
| fault Redis | falha observada, recuperação confirmada, 0 falso sucesso |
| segurança sob carga | todos os contadores de violação iguais a zero |

Os JSONs em `results/` são a evidência primária. O comando
`uv run python scripts/summarize_ds015_results.py <arquivos>` valida e resume
esses dados sem reescrevê-los.

## Quality gates

Executados em 13/10/2026 com PostgreSQL e Redis reais habilitados:

| Gate | Resultado |
| --- | --- |
| `uv sync --locked` | PASS |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS |
| `uv run mypy packages` | PASS — 375 arquivos |
| `uv run pytest` | PASS — 1.455 passed, 0 failed, 0 skipped, cobertura 92,68% |
| `uv build --package atlas-agent-core` | PASS |
| `uv build --package atlas-agent-adapters` | PASS |
| `uv build examples/kubernetes-recovery` | PASS |

O pytest emitiu apenas um `PytestCacheWarning` não bloqueante por falta de
permissão para atualizar `.pytest_cache`; testes e cobertura não foram afetados.

## Instalação limpa

Os wheels de core, adapters e do host de certificação foram instalados em uma
venv nova, sem editable install. O primeiro smoke detectou que a fixture do
runner não estava empacotada. O runner foi corrigido para carregar o recurso do
próprio pacote e seu pool Redis passou a comportar os 500 competidores fixos da
matriz. Após rebuild e reinstalação limpa, o entry point
`atlas-durable-state-performance-certify` concluiu baseline, escalabilidade,
contenção e soak curto com `PASS` usando o banco lógico Redis 15 isolado.

O smoke curto valida empacotamento; não substitui os dois soaks certificados de
60 minutos.

## Evidência Kubernetes reutilizada

DS-013 e DS-014 já certificaram, sobre a mesma baseline funcional, restart de
pods, rolling deployment, leases, fencing e HITL distribuído. A DS-015 não
alterou runtime nem adapters: adicionou apenas instrumentação e artefatos de
certificação. As evidências anteriores são, portanto, referenciadas e não
apresentadas como uma nova execução Kubernetes.
