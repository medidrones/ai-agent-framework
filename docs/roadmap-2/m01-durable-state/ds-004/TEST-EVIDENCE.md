# Evidências de testes DS-004

## Baseline anterior à alteração

- `uv sync --locked`: PASS;
- Ruff: PASS;
- formatação: 550 arquivos conformes;
- mypy: 344 arquivos fonte sem erros;
- build `atlas-agent-core`: PASS;
- pytest sem DSN: 1.168 aprovados e 22 ignorados;
- cobertura baseline: 92,14%.

## Evidências direcionadas

- testes HITL e unitários selecionados: 31 aprovados;
- testes DS-004 com PostgreSQL real: 12 aprovados;
- regressão PostgreSQL DS-002/003/004: 34 aprovados;
- multiprocessos Windows com `spawn`: PASS;
- baseline de 25 consumos concorrentes: 0,15 s no cenário de chamada;
- Ruff direcionado: PASS;
- mypy direcionado: PASS.

## Gates finais

- suíte integral com PostgreSQL real: 1.204 aprovados, zero falhas;
- cobertura de linhas e branches: 92,91%;
- Ruff: PASS;
- formatação: 563 arquivos conformes;
- mypy: 345 arquivos fonte sem erros;
- Bandit no core e adapters: zero ocorrências;
- `uv build --all-packages`: sete wheels e sete sdists aprovados;
- Twine sobre os quatorze artefatos: PASS;
- instalação limpa dos wheels e importação da capability: PASS.

O comando literal `uv build` foi executado e falhou porque a raiz declara
`tool.uv.package = false`; o setuptools tentou descoberta automática sobre o
workspace. A forma aplicável documentada pelo próprio `uv` para este monorepo é
`uv build --all-packages`, que passou para os sete projetos. Os builds
específicos exigidos pelo `AGENTS.md` também passaram.

O primeiro comando de instalação limpa instalou `psycopg` sem seu componente
binário e falhou por ausência de `libpq`. A repetição com `psycopg-binary`, que
faz parte do extra oficial `atlas-agent-adapters[postgresql]`, passou. Isso
confirma a importância de instalar o extra documentado e não representa falha
do artefato.

O aviso conhecido de `.pytest_cache` no Windows não altera resultados e decorre
de permissão do diretório de cache.
