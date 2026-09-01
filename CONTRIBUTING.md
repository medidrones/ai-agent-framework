# Contributing

Thank you for contributing to Atlas Agent Framework.

## Prerequisites

- Python 3.12 or newer
- uv
- Git

## Setup

From the repository root, install the workspace and development dependencies:

```bash
uv sync
```

## Quality gates

Run the same checks used by continuous integration:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages
uv run pytest
uv build --package atlas-agent-core
```

Optionally install the local pre-commit hooks:

```bash
uv run pre-commit install
```

## Change guidelines

- Keep changes focused on one coherent objective.
- Maintain dependency inversion and provider-neutral core contracts.
- Add complete type hints and public API documentation.
- Add unit and negative-path tests for behavior changes.
- Do not add provider SDKs or infrastructure dependencies to the core.
- Record significant architectural decisions before implementation.

All code and technical documentation must be written in English.
