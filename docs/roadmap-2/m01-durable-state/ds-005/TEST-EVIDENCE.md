# Evidências de testes DS-005

## Baseline

A branch foi criada diretamente do merge certificado da DS-004. Antes das
alterações, a entrega anterior registrava 1.204 testes aprovados, cobertura de
92,91% e 34 testes PostgreSQL reais.

## Evidência direcionada

- contrato/modelo core: 7 testes;
- suíte DS-005 PostgreSQL real: 12 testes;
- concorrência entre tasks e processos independentes: PASS;
- fencing em CAS e consumo autorizado: PASS;
- baseline de 30 amostras por operação: registrado em
  `PERFORMANCE-BASELINE.md`.

## Gates finais

- `uv sync --locked`: PASS;
- Ruff: PASS;
- formatação: 579 arquivos conformes;
- mypy: 349 arquivos fonte sem erros;
- PostgreSQL DS-002/003/004/005: 54 testes aprovados;
- suíte integral com PostgreSQL real: 1.223 testes aprovados, zero falhas;
- cobertura de linhas e branches: 92,92%;
- Bandit no core e adapters: zero ocorrências;
- build do `atlas-agent-core`: wheel e sdist aprovados;
- `uv build --all-packages`: sete wheels e sete sdists aprovados;
- Twine: 14/14 artefatos aprovados;
- instalação limpa Python 3.12 dos wheels core/adapters e imports públicos:
  PASS.

O aviso conhecido de `.pytest_cache` no Windows decorre de permissão do
diretório e não altera resultados. A suíte foi executada em Python 3.13.15; a
instalação limpa exigida foi também comprovada em Python 3.12.6.
