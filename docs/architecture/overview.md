# Architecture overview

Atlas Agent Framework is a modular Python SDK whose stable center is a small,
provider-neutral core. Consumers may use that core directly or add optional
plugins and transport adapters.

## Direction of dependency

```text
Consumers
    |
Adapters and plugins
    |
Core contracts
```

Source dependencies point toward the core. The core does not know which model
provider, database, broker, vector store, or transport will implement its
contracts.

## Repository organization

- `packages/atlas-agent-core` contains the importable `atlas_agents` package.
- Future packages will contain provider and infrastructure implementations.
- `docs` records architectural constraints and decisions.
- `examples` will demonstrate integration without introducing business logic
  into the framework.

The foundation intentionally contains no runtime logic. Contracts and behavior
will be added in small, independently reviewable phases.
