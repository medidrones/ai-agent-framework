# Evidências de teste da DS-003

## Ambiente

- Data: 2026-10-08
- Branch: `medicode/ds-003-checkpoint-optimistic-concurrency`
- Commit-base: `31e63364a580d13687e76df18071c1bce7846013`
- Python principal: 3.12.6
- PostgreSQL: 16 Alpine em container local isolado
- Baseline Atlas: 1.0.1

## Baseline antes das alterações

| Gate | Resultado |
| --- | --- |
| `uv sync --locked` | PASS |
| Ruff | PASS |
| formatação | PASS |
| mypy | PASS — 342 arquivos |
| pytest sem DSN | PASS — 1.165 aprovados e 10 ignorados |

## Resultado final

| Gate | Resultado | Evidência |
| --- | --- | --- |
| suíte PostgreSQL dedicada | PASS | 30 testes, zero falhas |
| regressão integral com PostgreSQL | PASS | 1.190 testes, zero falhas |
| compatibilidade Python 3.13 sem DSN | PASS | 1.168 aprovados e 22 integrações ignoradas |
| cobertura | PASS | 92,87%; mínimo 90% |
| Ruff | PASS | nenhuma violação |
| formatação | PASS | 550 arquivos |
| mypy | PASS | 344 arquivos sem erros |
| Bandit | PASS | 2.796 linhas, zero findings |
| builds | PASS | core, adapters e meta-package; wheels e sdists |
| Twine | PASS | seis artefatos válidos |
| instalação limpa | PASS | API pública e migration 002 importadas do wheel |
| migration empacotada | PASS | `002_add_checkpoint_revision.sql` presente no wheel |

O único aviso local foi a impossibilidade preexistente de o pytest gravar
`.pytest_cache` no workspace. O aviso não altera execução, cobertura ou
resultados.

## Cenários certificados

| Cenário | Evidência observada |
| --- | --- |
| atualização sem conflito | revisão 1 → 2 e atualização posterior 2 → 3 |
| writers concorrentes | exatamente um snapshot e um conflito tipado |
| versão obsoleta | payload vencedor e revisão 2 preservados |
| consumido/desconhecido | not found; nenhuma linha recriada |
| expirado | atualização rejeitada; payload e revisão 1 preservados |
| identidade | mudança de execution/agent/tenant rejeitada |
| falha antes do commit | trigger controlado provoca rollback integral |
| update versus consume | somente os dois resultados documentados ocorreram |
| processos independentes | um processo venceu e outro recebeu conflito |
| cancelamento | `CancelledError`, cleanup e revisão 1 preservada |
| restart | novo pool leu payload atualizado na revisão 2 |
| isolamento | dois tokens distintos avançaram independentemente |
| HITL e replay | regressão DS-002 e runtime integral aprovados |

Os testes de lock consultam `pg_stat_activity` para confirmar espera real no
PostgreSQL antes de liberar a barreira. O teste multiprocess utiliza contexto
`spawn`, pools independentes e conexões distintas; a garantia não depende de
locks Python compartilhados.
