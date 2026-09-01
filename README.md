# Atlas Agent Framework

Atlas is a reusable, provider-agnostic Python framework for defining,
composing, executing, and evaluating AI agents.

This repository contains framework infrastructure rather than a business
application. The core package defines stable contracts while optional packages
will integrate model providers, storage systems, transports, and observability
backends.

## Status

The project is in its foundation phase. The current release establishes the
workspace, package, quality gates, and architectural dependency rules. Agent
runtime behavior is intentionally not implemented yet.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

## Development

Run all commands from the repository root:

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy packages
uv run pytest
uv build --package atlas-agent-core
```

The package uses a `src` layout and can be imported as follows:

```python
import atlas_agents

print(atlas_agents.__version__)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the high-level design and
[docs/architecture/dependency-rules.md](docs/architecture/dependency-rules.md)
for enforceable dependency constraints.

## Contributing and security

Development expectations are described in [CONTRIBUTING.md](CONTRIBUTING.md).
Report security issues using the private process in [SECURITY.md](SECURITY.md).

## License

Atlas Agent Framework is available under the [MIT License](LICENSE).
