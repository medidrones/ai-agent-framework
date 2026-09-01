# Security Policy

## Supported versions

Atlas Agent Framework is pre-release software. Security fixes are applied to
the latest revision of the default branch.

## Reporting a vulnerability

Do not disclose vulnerabilities in a public issue. Report them privately to
the repository maintainers using the security reporting feature provided by
the repository host. Include reproduction steps, affected versions, impact,
and any suggested mitigation.

Maintainers should acknowledge a report within five business days and provide
status updates while it is investigated.

## Security principles

- Secrets are injected explicitly and are never logged or serialized.
- Core code does not read credentials directly from environment variables.
- Tool inputs are validated before execution.
- Retrieved and model-generated content is treated as untrusted.
- Arbitrary code execution is not part of the core runtime.
- Network access is introduced only through explicit adapters.
