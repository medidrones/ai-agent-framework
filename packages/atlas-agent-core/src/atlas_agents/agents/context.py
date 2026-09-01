"""External execution context supplied by framework consumers."""

from pydantic import Field, field_validator

from atlas_agents._models import _FrozenModel, _json_mapping, _non_empty


class ExecutionIdentity(_FrozenModel):
    """Represent a resolved identity without depending on an auth mechanism."""

    subject: str
    roles: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    attributes: dict[str, object] = Field(default_factory=dict)

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        """Reject an empty identity subject."""
        return _non_empty(value)

    @field_validator("attributes")
    @classmethod
    def validate_attributes(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep attributes serializable and isolated from caller mutation."""
        return _json_mapping(value)


class AgentContext(_FrozenModel):
    """Provide explicit execution-scoped data from a consuming application."""

    execution_id: str
    session_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    identity: ExecutionIdentity | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("execution_id")
    @classmethod
    def validate_execution_id(cls, value: str) -> str:
        """Reject an empty execution identifier."""
        return _non_empty(value)

    @field_validator("session_id", "user_id", "tenant_id")
    @classmethod
    def validate_optional_ids(cls, value: str | None) -> str | None:
        """Reject optional identifiers when explicitly provided as empty."""
        return None if value is None else _non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata serializable and isolated from caller mutation."""
        return _json_mapping(value)
