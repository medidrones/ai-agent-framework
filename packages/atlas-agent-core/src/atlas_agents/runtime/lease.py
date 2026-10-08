"""Provider-neutral contracts for durable checkpoint ownership."""

from datetime import datetime, timedelta
from typing import Protocol

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _non_empty, _timezone_aware
from atlas_agents.exceptions import AtlasAgentError


class CheckpointLease(_FrozenModel):
    """Represent one time-bounded generation of checkpoint ownership."""

    checkpoint_id: str
    owner_id: str
    fencing_token: int = Field(gt=0)
    acquired_at: datetime
    expires_at: datetime

    @field_validator("checkpoint_id", "owner_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        """Reject empty lease identifiers."""
        return _non_empty(value)

    @field_validator("acquired_at", "expires_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        """Require timezone-aware lease timestamps."""
        return _timezone_aware(value, label="do lease")

    @model_validator(mode="after")
    def validate_expiration(self) -> "CheckpointLease":
        """Require expiration after acquisition."""
        if self.expires_at <= self.acquired_at:
            raise ValueError("A expiração do lease deve suceder sua aquisição")
        return self


class CheckpointLeaseError(AtlasAgentError):
    """Base class for controlled checkpoint lease errors."""


class CheckpointLeaseConflictError(CheckpointLeaseError):
    """Report ownership held by another active worker."""


class CheckpointLeaseLostError(CheckpointLeaseError):
    """Report an expired, released, or superseded lease generation."""


class CheckpointLeaseNotFoundError(CheckpointLeaseError):
    """Report a checkpoint that is not eligible for leasing."""


class CheckpointLeaseManager(Protocol):
    """Coordinate temporary ownership without prescribing infrastructure."""

    async def acquire(
        self,
        *,
        checkpoint_id: str,
        owner_id: str,
        duration: timedelta,
    ) -> CheckpointLease:
        """Acquire one eligible checkpoint or raise a controlled conflict."""
        ...

    async def renew(
        self,
        *,
        lease: CheckpointLease,
        duration: timedelta,
    ) -> CheckpointLease:
        """Extend one active lease generation."""
        ...

    async def release(self, *, lease: CheckpointLease) -> None:
        """Release one active lease without resetting its fencing generation."""
        ...
