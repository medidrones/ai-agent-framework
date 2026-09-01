.PHONY: install lint format format-check type-check test coverage quality build clean

install:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

type-check:
	uv run mypy packages

test:
	uv run pytest

coverage:
	uv run pytest --cov --cov-report=term-missing --cov-report=xml

quality: lint format-check type-check test

build:
	uv build --package atlas-agent-core

clean:
	uv run python -c "from pathlib import Path; import shutil; root = Path.cwd().resolve(); targets = tuple(root / name for name in ('.coverage', 'coverage.xml', '.mypy_cache', '.pytest_cache', '.ruff_cache', 'build', 'dist')); assert all(path.parent == root for path in targets); [shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink(missing_ok=True) for path in targets]"
