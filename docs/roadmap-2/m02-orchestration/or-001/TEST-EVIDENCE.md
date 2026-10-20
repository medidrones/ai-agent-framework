# Evidências de teste da OR-001

## Baseline pré-alteração

- commit: `fb060b436d68f70248a240bbec4dfbe33b8715f1`;
- tag `v1.1.0`: `116e886e95c8785920ca1f18e6d88b01a3c1e3ed`;
- ambiente: Windows, CPython 3.13.15, uv;
- lint, formatação e mypy: aprovados;
- pytest: 1.328 aprovados, 128 ignorados, 0 falhas;
- cobertura reportada: 89,61%, aviso pré-existente a revalidar no gate final;
- build de `atlas-agent-core`: wheel e sdist gerados.

## Resultado final

- `uv sync`: `PASS`;
- `uv run ruff check .`: `PASS`;
- `uv run ruff format --check .`: `PASS`, 843 arquivos formatados;
- `uv run mypy packages`: `PASS`, 388 arquivos-fonte;
- `uv run pytest`: `PASS`, 1.398 aprovados, 128 ignorados, 0 falhas;
- cobertura global com branches: `90,00%`;
- `uv build --package atlas-agent-core`: `PASS`, wheel e sdist;
- instalação sem editable do wheel em ambiente limpo: `PASS`;
- import de `WorkflowDefinition` e `WorkflowOrchestrator`: `PASS`;
- presença de `py.typed` no wheel instalado: `PASS`.

Os 128 testes ignorados exigem serviços externos e já faziam parte da baseline;
nenhum teste foi desabilitado pela OR-001.

## Matriz

Os testes `test_or001_contracts.py` cobrem OR001-T01–T25 e os casos negativos
de segurança. `test_or001_architecture.py` cobre OR001-T26–T29. OR001-T30 é comprovado
no gate final instalando o wheel em ambiente limpo e importando a API pública.

O teste do wheel foi executado com dependências declaradas instaladas em um
venv temporário e o artefato local instalado com `--no-deps --no-index`.
