# Evidências de teste da DS-002

## Ambiente

- Data: 2026-10-08
- Branch: `medicode/ds-002-postgresql-checkpoint-store`
- Commit-base: `88e62e2bdce7c6be0c5102a561d0de81b6ded341`
- Python: 3.12.6
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
| regressão completa | PASS | 1.173 testes; zero falhas |
| cobertura | PASS | 92,87%; mínimo exigido de 90% |
| `uv build --package atlas-agent-core` | PASS | wheel e sdist 1.0.1 |
| `uv build --package atlas-agent-adapters` | PASS | wheel e sdist 1.0.1 |
| `uv build --package atlas-agent-framework` | PASS | wheel e sdist 1.0.1 |
| `twine check` | PASS | seis artefatos válidos |
| instalação limpa | PASS | core e adapter instalados de wheels |
| migration no wheel | PASS | recurso SQL presente; seis arquivos do adapter PostgreSQL |
| Bandit | PASS | 2.627 linhas; zero findings |
| `git diff --check` | PASS | nenhuma inconsistência textual |

A regressão foi executada com `ATLAS_TEST_POSTGRES_DSN` apontando para a
instância PostgreSQL real. O único aviso foi a impossibilidade preexistente de o
pytest gravar `.pytest_cache` no workspace; ele não afeta execução, resultado ou
cobertura.

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
3.12. A execução remota desse job permanece `NOT_EXECUTED` até a branch ser
publicada; ela não é registrada aqui como `PASS`.
