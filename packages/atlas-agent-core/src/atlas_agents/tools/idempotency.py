"""Declarative idempotency semantics for tools."""

from enum import StrEnum


class ToolIdempotency(StrEnum):
    """Describe whether repeated logical operations are semantically safe."""

    UNSPECIFIED = "unspecified"
    IDEMPOTENT = "idempotent"
    NON_IDEMPOTENT = "non_idempotent"
