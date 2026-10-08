# Evidências de teste da DS-002

## Ambiente

- Data: 2026-10-08
- Branch: `medicode/ds-002-postgresql-checkpoint-store`
- Commit-base: `88e62e2bdce7c6be0c5102a561d0de81b6ded341`
- Python: 3.12.6 e 3.13.15
- PostgreSQL: 16 Alpine, instância real isolada em container local
- Baseline Atlas: 1.0.1

O commit-base identifica o ponto integrado de partida. A implementação da
DS-002 ainda estava no working tree durante esta certificação e deve receber um
commit próprio antes da publicação da branch.

## Quality gates

| Verificação | Resultado | Evidência resumida |
| --- | --- | --- |
| `uv sync --locked` | PASS | 83 pacotes resolvidos; lock consistente |
| `uv run ruff check .` | PASS | nenhuma violação |
| `uv run ruff format --check .` | PASS | 537 arquivos formatados |
| `uv run mypy packages` | PASS | 342 arquivos sem erros |
| regressão completa Python 3.12 + PostgreSQL | PASS | 1.175 testes; zero falhas |
| regressão completa Python 3.13 | PASS | 1.165 aprovados e 10 integrações PostgreSQL ignoradas |
| cobertura | PASS | 92,91% no gate integral; mínimo exigido de 90% |
| `uv build --package atlas-agent-core` | PASS | wheel e sdist 1.0.1 |
| `uv build --package atlas-agent-adapters` | PASS | wheel e sdist 1.0.1 |
| `uv build --package atlas-agent-framework` | PASS | wheel e sdist 1.0.1 |
| `twine check` | PASS | seis artefatos válidos |
| instalação limpa | PASS | core e adapter instalados de wheels |
| migration no wheel | PASS | recurso SQL presente; seis arquivos do adapter PostgreSQL |
| Bandit | PASS | 2.627 linhas; zero findings |
| `git diff --check` | PASS | nenhuma inconsistência textual |

A regressão Python 3.12 foi executada com `ATLAS_TEST_POSTGRES_DSN` apontando
para a instância PostgreSQL real. A regressão Python 3.13 reproduziu o gate de
compatibilidade sem DSN e confirmou a serialização canônica de capabilities. O
único aviso foi a impossibilidade preexistente de o pytest gravar
`.pytest_cache` no workspace; ele não afeta execução, resultado ou cobertura.

## Cenários PostgreSQL

A suíte dedicada terminou com **15 testes aprovados** e cobre:

- migration inicial, idempotência e registro de checksum;
- persistência e consumo transacionais;
- token armazenado apenas como digest e opção HMAC-SHA-256;
- `save` create-only e rejeição de colisão;
- doze consumidores concorrentes com exatamente um vencedor;
- replay, token desconhecido e expiração com resposta indistinguível;
- limpeza concorrente e limitada de registros expirados;
- payload corrompido consumido e rejeitado em modo fail-closed;
- sobrevivência do checkpoint ao fechamento e recriação do pool da aplicação;
- cancelamento de consumo bloqueado, rollback e preservação do checkpoint;
- erro de banco encapsulado sem exposição do token ou da credencial de teste;
- suspensão e retomada HITL reais pelo `AgentRuntime`, com uma única execução da
  ferramenta sob corrida entre duas retomadas.

## CI

O workflow `Qualidade` recebeu um job dedicado com serviço
`postgres:16-alpine`, health check e execução da suíte PostgreSQL em Python
3.12. A evidência remota é mantida pelo pull request e seus checks, sem ser
substituída por uma declaração estática neste documento.
