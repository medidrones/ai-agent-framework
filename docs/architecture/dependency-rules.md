# Dependency rules

These rules preserve Atlas as an embeddable framework instead of coupling it to
a specific application or infrastructure stack.

## Core package

The core package may depend only on general-purpose libraries needed for
validation, serialization, typing, and provider-neutral behavior.

It must not import or require:

- model provider SDKs;
- web frameworks;
- database drivers or object-relational mappers;
- message broker clients;
- vector database clients;
- infrastructure-specific telemetry clients;
- business-domain packages.

The core must not read secrets from environment variables, use global mutable
registries, execute arbitrary code, or expose provider-specific values through
public interfaces.

## Plugins

Plugins implement contracts declared by the core. A plugin may depend on its
target SDK, but that dependency stays in the plugin's own distribution. Plugins
must not depend on transport adapters.

## Adapters

Adapters translate between external transports and the public core API. They
may depend on the core and on transport libraries. The core must never import
an adapter.

## Enforcement

Each package declares its dependencies independently. CI runs linting, strict
type checking, tests, and package builds. Architecture tests will be added when
cross-package imports exist and can be meaningfully validated.
