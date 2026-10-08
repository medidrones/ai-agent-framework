from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from atlas_agents import (
    CheckpointLease,
    CheckpointLeaseConflictError,
    CheckpointLeaseError,
    CheckpointLeaseLostError,
    CheckpointLeaseManager,
    CheckpointLeaseNotFoundError,
)


def lease() -> CheckpointLease:
    acquired_at = datetime(2026, 1, 1, tzinfo=UTC)
    return CheckpointLease(
        checkpoint_id="execution-1",
        owner_id="worker-1",
        fencing_token=1,
        acquired_at=acquired_at,
        expires_at=acquired_at + timedelta(seconds=30),
    )


def test_lease_is_immutable_and_public() -> None:
    value = lease()

    assert value.checkpoint_id == "execution-1"
    assert value.fencing_token == 1
    assert isinstance(CheckpointLeaseManager, type)
    with pytest.raises(ValidationError):
        value.owner_id = "worker-2"


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"checkpoint_id": " "}, "vazio"),
        ({"owner_id": ""}, "vazio"),
        ({"fencing_token": 0}, "greater than 0"),
        ({"acquired_at": datetime(2026, 1, 1)}, "fuso"),
        (
            {"expires_at": datetime(2025, 12, 31, tzinfo=UTC)},
            "expiração",
        ),
    ],
)
def test_lease_rejects_invalid_boundaries(
    update: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        CheckpointLease(**{**lease().model_dump(), **update})


def test_lease_errors_share_controlled_base() -> None:
    assert issubclass(CheckpointLeaseConflictError, CheckpointLeaseError)
    assert issubclass(CheckpointLeaseLostError, CheckpointLeaseError)
    assert issubclass(CheckpointLeaseNotFoundError, CheckpointLeaseError)
