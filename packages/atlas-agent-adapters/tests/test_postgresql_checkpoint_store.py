from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from atlas_agents import ExecutionCheckpoint, ResumeToken
from atlas_agents.adapters.checkpoints.postgresql import (
    CheckpointConcurrencyConflictError,
    PostgreSQLCheckpointSnapshot,
    PostgreSQLCheckpointStore,
)

ROOT = Path(__file__).parents[2]
FIXTURE = (
    ROOT
    / "atlas-agent-core"
    / "tests"
    / "fixtures"
    / "checkpoints"
    / "execution-checkpoint-v1.json"
)


def checkpoint(*, expires_at: datetime | None = None) -> ExecutionCheckpoint:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["pending_approval"]["expires_at"] = (
        None if expires_at is None else expires_at.isoformat()
    )
    return ExecutionCheckpoint.model_validate(payload)


def store(
    *, retention: timedelta | None = None, key: bytes | None = None
) -> PostgreSQLCheckpointStore:
    pool = cast(Any, object())
    return PostgreSQLCheckpointStore(
        pool,
        retention=retention,
        token_hmac_key=key,
    )


def test_token_digest_never_preserves_plaintext() -> None:
    token = ResumeToken(value="DS002-SECRET-TOKEN")
    plain = store()._token_digest(token)
    protected = store(key=b"k" * 32)._token_digest(token)

    assert plain == hashlib.sha256(token.value.encode()).digest()
    assert token.value.encode() not in plain
    assert protected != plain
    assert len(protected) == 32


def test_expiration_uses_the_earliest_configured_boundary() -> None:
    value = checkpoint(expires_at=datetime(2026, 1, 3, tzinfo=UTC))
    configured = store(retention=timedelta(days=1))

    assert configured._expires_at(value) == datetime(2026, 1, 2, tzinfo=UTC)


@pytest.mark.parametrize(
    ("retention", "key", "message"),
    [
        (timedelta(0), None, "retenção"),
        (None, b"short", "HMAC"),
    ],
)
def test_invalid_configuration_is_rejected(
    retention: timedelta | None,
    key: bytes | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        store(retention=retention, key=key)


def test_versioned_migration_is_packaged() -> None:
    migration_root = (
        ROOT
        / "atlas-agent-adapters"
        / "src"
        / "atlas_agents"
        / "adapters"
        / "checkpoints"
        / "postgresql"
        / "sql"
    )

    initial = (migration_root / "001_create_checkpoint_store.sql").read_text(
        encoding="utf-8"
    )
    revision = (migration_root / "002_add_checkpoint_revision.sql").read_text(
        encoding="utf-8"
    )
    lease = (migration_root / "003_create_checkpoint_leases.sql").read_text(
        encoding="utf-8"
    )
    recovery = (migration_root / "004_create_recovery_attempts.sql").read_text(
        encoding="utf-8"
    )
    retention = (migration_root / "005_create_checkpoint_retention.sql").read_text(
        encoding="utf-8"
    )
    purge = (migration_root / "006_create_checkpoint_purge.sql").read_text(
        encoding="utf-8"
    )

    assert "CREATE TABLE atlas_agent.checkpoints" in initial
    assert "token_digest BYTEA PRIMARY KEY" in initial
    assert "payload JSONB NOT NULL" in initial
    assert "ADD COLUMN revision BIGINT NOT NULL DEFAULT 1" in revision
    assert "CREATE TABLE atlas_agent.checkpoint_leases" in lease
    assert "fencing_token BIGINT NOT NULL DEFAULT 0" in lease
    assert "CREATE TABLE atlas_agent.execution_recovery_attempts" in recovery
    assert "CREATE TABLE atlas_agent.checkpoint_tombstones" in retention
    assert "CREATE TABLE atlas_agent.checkpoint_purge_audit" in purge
    assert "ADD COLUMN legal_hold BOOLEAN" in purge


def test_expected_revision_must_be_positive() -> None:
    value = store()

    with pytest.raises(ValueError, match="revisão esperada"):
        asyncio.run(
            value.compare_and_swap(
                resume_token=ResumeToken(value="token"),
                checkpoint=checkpoint(),
                expected_revision=0,
            )
        )


def test_snapshot_is_immutable_and_requires_positive_revision() -> None:
    snapshot = PostgreSQLCheckpointSnapshot(
        checkpoint=checkpoint(),
        revision=1,
    )

    assert snapshot.revision == 1
    with pytest.raises(ValidationError):
        snapshot.revision = 2
    with pytest.raises(ValidationError):
        PostgreSQLCheckpointSnapshot(checkpoint=checkpoint(), revision=0)


def test_conflict_error_exposes_only_safe_revision_facts() -> None:
    error = CheckpointConcurrencyConflictError(
        checkpoint_id="execution-1",
        expected_revision=3,
        actual_revision=4,
    )

    assert error.error_code == "checkpoint_concurrency_conflict"
    assert error.checkpoint_id == "execution-1"
    assert error.expected_revision == 3
    assert error.actual_revision == 4
    assert "payload" not in str(error).casefold()
    assert "postgresql://" not in str(error)
