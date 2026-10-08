from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from atlas_agents import ExecutionCheckpoint, ResumeToken
from atlas_agents.adapters.checkpoints.postgresql import PostgreSQLCheckpointStore

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
    migration = (
        ROOT
        / "atlas-agent-adapters"
        / "src"
        / "atlas_agents"
        / "adapters"
        / "checkpoints"
        / "postgresql"
        / "sql"
        / "001_create_checkpoint_store.sql"
    )

    sql = migration.read_text(encoding="utf-8")

    assert "CREATE TABLE atlas_agent.checkpoints" in sql
    assert "token_digest BYTEA PRIMARY KEY" in sql
    assert "payload JSONB NOT NULL" in sql
