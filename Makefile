.PHONY: install sync-version lint format format-check type-check test coverage quality build artifacts reproducible packaging-smoke packaging clean

install:
	uv sync

sync-version:
	uv run python scripts/sync_versions.py

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
	uv build --package atlas-agent
	uv build --package atlas-agent-adapters
	uv build --package atlas-agent-config
	uv build --package atlas-agent-core
	uv build --package atlas-agent-evaluation
	uv build --package atlas-agent-mcp
	uv build --package atlas-agent-providers

artifacts: build
	uv run python scripts/verify_artifacts.py

reproducible: artifacts
	uv run python scripts/check_reproducible_builds.py

packaging-smoke:
	uv run python scripts/smoke_wheels.py

packaging: quality reproducible packaging-smoke

clean:
	uv run python -c "from pathlib import Path; import shutil; root = Path.cwd().resolve(); targets = tuple(root / name for name in ('.coverage', 'coverage.xml', '.mypy_cache', '.pytest_cache', '.ruff_cache', 'build', 'dist')); assert all(path.parent == root for path in targets); [shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink(missing_ok=True) for path in targets]"
