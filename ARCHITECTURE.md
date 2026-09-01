# Architecture

Atlas Agent Framework is organized as a Python monorepo. Its architecture is
based on dependency inversion: stable core contracts are implemented by
optional infrastructure packages.

## Layers

1. **Core** defines provider-neutral agent, model, tool, memory, knowledge,
   orchestration, governance, and observability contracts.
2. **Plugins** implement core contracts for concrete providers and
   infrastructure.
3. **Adapters** expose the framework through transports such as CLI, MCP,
   REST, gRPC, or events.
4. **Consumers** integrate Atlas through its Python API or an adapter.

Dependencies point inward. The core must remain usable without any plugin or
adapter and must never import from those packages.

## Current scope

The repository currently includes only the workspace and the
`atlas-agent-core` package shell. Runtime, provider, tool, and storage behavior
will be introduced incrementally after their contracts are designed.

Detailed package boundaries are documented in
[`docs/architecture/dependency-rules.md`](docs/architecture/dependency-rules.md).
