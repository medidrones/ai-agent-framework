"""Explicit secret references, protected values, and resolvers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from atlas_agents.config.errors import SecretResolutionError


def _required(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("A referência de segredo não pode ser vazia")
    return normalized


class SecretReference(BaseModel):
    """Keep only a logical secret name in serializable configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    secret_ref: str

    _validate_reference = field_validator("secret_ref")(_required)


class SecretValue:
    """Wrap a resolved secret and disclose it only through an explicit call."""

    __slots__ = ("__value",)

    def __init__(self, value: str) -> None:
        """Store one non-empty resolved secret outside config models."""
        if not value:
            raise ValueError("O valor resolvido do segredo não pode ser vazio")
        self.__value = value

    def get_secret_value(self) -> str:
        """Return the secret only after an explicit caller action."""
        return self.__value

    def __repr__(self) -> str:
        """Return a permanently redacted representation."""
        return "SecretValue(********)"

    def __str__(self) -> str:
        """Return a permanently redacted string representation."""
        return "********"


class SecretResolver(Protocol):
    """Resolve a logical secret reference without implicit caching."""

    async def resolve(self, reference: SecretReference) -> SecretValue:
        """Return one protected secret value."""
        ...


class MappingSecretResolver:
    """Resolve secrets from an explicitly supplied local mapping."""

    def __init__(self, values: Mapping[str, str | SecretValue]) -> None:
        """Copy caller values into one instance-local resolver."""
        self.__values = dict(values)

    async def resolve(self, reference: SecretReference) -> SecretValue:
        """Resolve exactly one mapped logical reference."""
        try:
            value = self.__values[reference.secret_ref]
        except KeyError as error:
            raise SecretResolutionError(
                f"Não foi possível resolver a referência '{reference.secret_ref}'.",
                path=reference.secret_ref,
            ) from error
        if isinstance(value, SecretValue):
            return value
        try:
            return SecretValue(value)
        except ValueError as error:
            raise SecretResolutionError(
                f"A referência '{reference.secret_ref}' não possui valor utilizável.",
                path=reference.secret_ref,
            ) from error


class RejectingSecretResolver:
    """Fail closed when a host did not configure secret resolution."""

    async def resolve(self, reference: SecretReference) -> SecretValue:
        """Reject every reference without environment fallback."""
        raise SecretResolutionError(
            f"Não há resolver para a referência '{reference.secret_ref}'.",
            path=reference.secret_ref,
        )
