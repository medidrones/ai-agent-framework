# Evidências de testes DS-006

## Baseline

Antes das alterações: `uv sync --locked` aprovado e 1.177 testes aprovados com
46 skips sem DSN PostgreSQL.

## Evidência direcionada

- core recovery: vazio, pre/post-check, HITL conservador, conflito, limite,
  isolamento de falhas, cancelamento, timeout, checkpoint incompatível e falha
  ao persistir resultado;
- runtime HITL: consumo autorizado fenced pelo parâmetro aditivo `lease`;
- PostgreSQL real: descoberta/tenant, corrida async, multiprocesso, restart,
  limite durável, fencing obsoleto, lease expirado e performance;
- migration 004 verificada por checksum pelo migrator existente.

## Gates finais

- `uv sync --locked`: PASS;
- Ruff: PASS em 596 arquivos;
- mypy: 353 arquivos fonte sem erros;
- suíte integral com PostgreSQL real: 1.245 testes aprovados, zero falhas;
- conjunto PostgreSQL DS-002 a DS-006: 62 testes;
- cobertura de linhas e branches: 92,57%;
- Bandit: zero ocorrências em 22.858 linhas;
- `pip-audit`: nenhuma vulnerabilidade conhecida;
- build: sete wheels e sete sdists;
- Twine: 14/14 artefatos aprovados;
- instalação limpa Python 3.12.6 dos wheels core/adapters, imports públicos e
  presença da migration 004: PASS.

O único aviso da suíte é a impossibilidade de gravar `.pytest_cache` por
permissão do diretório no Windows; resultados e cobertura foram produzidos
normalmente.
