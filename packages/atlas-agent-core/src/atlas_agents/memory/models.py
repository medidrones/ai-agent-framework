"""Immutable serializable memory records, queries, and write values."""

import math
from datetime import UTC, datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import (
    _FrozenModel,
    _json_mapping,
    _non_empty,
    _timezone_aware,
)
from atlas_agents.memory.scope import MemoryScope
from atlas_agents.memory.types import MemoryType


class MemoryRecord(_FrozenModel):
    """Represent one definitive record returned by a memory store."""

    memory_id: str
    memory_type: MemoryType
    scope: MemoryScope
    content: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("memory_id", "content")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject empty record identifiers and content."""
        return _non_empty(value)

    @field_validator("created_at", "updated_at", "expires_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        """Require timezone-aware timestamps when present."""
        return None if value is None else _timezone_aware(value, label="da memória")

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)

    @model_validator(mode="after")
    def validate_temporal_order(self) -> Self:
        """Keep record update and expiry timestamps chronologically valid."""
        if self.updated_at < self.created_at:
            raise ValueError("A atualização da memória não pode anteceder a criação")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("A expiração da memória deve ser posterior à criação")
        return self


class MemoryWriteRequest(_FrozenModel):
    """Request one append-oriented memory write without choosing its ID."""

    memory_type: MemoryType
    scope: MemoryScope
    content: str
    expires_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        """Reject an empty memory payload."""
        return _non_empty(value)

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value: datetime | None) -> datetime | None:
        """Reject naive or already expired write requests."""
        if value is None:
            return None
        validated = _timezone_aware(value, label="da memória")
        if validated <= datetime.now(UTC):
            raise ValueError("A nova memória deve expirar no futuro")
        return validated

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class MemoryQuery(_FrozenModel):
    """Describe one exact-scope, single-type provider-neutral search."""

    scope: MemoryScope
    memory_type: MemoryType
    text: str | None = None
    limit: int = Field(default=20, gt=0)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        """Reject explicitly empty query text."""
        return None if value is None else _non_empty(value)

    @field_validator("limit", mode="before")
    @classmethod
    def reject_boolean_limit(cls, value: object) -> object:
        """Reject booleans even though Python models them as integers."""
        if isinstance(value, bool):
            raise ValueError("O limite de memória não pode ser booleano")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)


class MemorySearchResult(_FrozenModel):
    """Pair a record with an optional store-specific search score."""

    record: MemoryRecord
    score: float | None = None

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: float | None) -> float | None:
        """Reject non-finite store scores."""
        if value is not None and not math.isfinite(value):
            raise ValueError("O score de memória deve ser finito")
        return value


class MemoryCandidate(_FrozenModel):
    """Describe policy-selected memory content before scope resolution."""

    memory_type: MemoryType
    content: str
    expires_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        """Reject empty candidate content."""
        return _non_empty(value)

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value: datetime | None) -> datetime | None:
        """Require an optional future timezone-aware expiry."""
        if value is None:
            return None
        validated = _timezone_aware(value, label="da memória")
        if validated <= datetime.now(UTC):
            raise ValueError("A candidata de memória deve expirar no futuro")
        return validated

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        """Keep metadata JSON-compatible and isolated."""
        return _json_mapping(value)
