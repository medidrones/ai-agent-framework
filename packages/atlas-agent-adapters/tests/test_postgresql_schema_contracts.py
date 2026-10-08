from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from psycopg import OperationalError
from psycopg_pool import PoolTimeout
from pydantic import ValidationError

from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLMigrationError,
    PostgreSQLSchemaCheckError,
    PostgreSQLSchemaCompatibilityChecker,
    PostgreSQLSchemaCompatibilityResult,
    PostgreSQLSchemaStatus,
)
from atlas_agents.adapters.checkpoints.postgresql.migrations import (
    _MIGRATIONS,
    _migration_sql,
)
from atlas_agents.adapters.checkpoints.postgresql.schema import (
    _EXPECTED_COLUMNS,
    _EXPECTED_CONSTRAINTS,
    _EXPECTED_INDEXES,
    _catalog_issues,
    _check_history,
)


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    async def fetchone(self) -> tuple[object, ...] | None:
        return None if not self._rows else self._rows[0]

    async def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _Connection:
    def __init__(self, responses: list[list[tuple[object, ...]]]) -> None:
        self._responses = iter(responses)

    async def execute(
        self, query: str, parameters: tuple[object, ...] | None = None
    ) -> _Cursor:
        del query, parameters
        return _Cursor(next(self._responses))


class _Pool:
    def __init__(
        self,
        responses: list[list[tuple[object, ...]]],
        *,
        unavailable: bool = False,
    ) -> None:
        self._responses = responses
        self._unavailable = unavailable

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[_Connection]:
        if self._unavailable:
            raise PoolTimeout("test timeout")
        yield _Connection(self._responses)


class _MigrationConnection:
    def __init__(self, history: dict[int, str]) -> None:
        self._history = history
        self.statements: list[str] = []

    async def execute(
        self, query: str, parameters: tuple[object, ...] | None = None
    ) -> _Cursor:
        del parameters
        self.statements.append(query)
        if "FROM atlas_agent.schema_migrations" in query:
            return _Cursor(list(self._history.items()))
        return _Cursor([])


class _MigrationPool:
    def __init__(self, history: dict[int, str], *, unavailable: bool = False) -> None:
        self.connection_value = _MigrationConnection(history)
        self._unavailable = unavailable

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[_MigrationConnection]:
        if self._unavailable:
            raise OperationalError("postgresql://secret")
        yield self.connection_value


def _history(*, through: int = 7) -> dict[int, str]:
    return {
        migration.version: hashlib.sha256(
            _migration_sql(migration.resource).encode("utf-8")
        ).hexdigest()
        for migration in _MIGRATIONS
        if migration.version <= through
    }


def _compatible_responses() -> list[list[tuple[object, ...]]]:
    columns: list[tuple[object, ...]] = [
        (table, column, data_type, nullable)
        for table, expected_columns in _EXPECTED_COLUMNS.items()
        for column, (data_type, nullable) in expected_columns.items()
    ]
    return [
        [("atlas_agent.schema_migrations",)],
        [(version, checksum) for version, checksum in _history().items()],
        columns,
        [(index,) for index in _EXPECTED_INDEXES],
        [(constraint,) for constraint in _EXPECTED_CONSTRAINTS],
    ]


async def test_checker_reports_compatible_catalog_from_read_only_metadata() -> None:
    checker = PostgreSQLSchemaCompatibilityChecker(
        cast(Any, _Pool(_compatible_responses()))
    )

    result = await checker.check()

    assert result.status is PostgreSQLSchemaStatus.COMPATIBLE
    assert result.current_version == 7
    assert result.issues == ()


async def test_checker_reports_not_initialized() -> None:
    checker = PostgreSQLSchemaCompatibilityChecker(cast(Any, _Pool([[(None,)]])))

    result = await checker.check()

    assert result.status is PostgreSQLSchemaStatus.NOT_INITIALIZED
    assert result.current_version is None


async def test_checker_wraps_pool_timeout_without_connection_details() -> None:
    checker = PostgreSQLSchemaCompatibilityChecker(
        cast(Any, _Pool([], unavailable=True))
    )

    with pytest.raises(PostgreSQLSchemaCheckError) as captured:
        await checker.check()

    assert "test timeout" not in str(captured.value)


@pytest.mark.parametrize(
    ("history", "status", "code"),
    [
        ({}, PostgreSQLSchemaStatus.VERSION_UNSUPPORTED, "MIGRATION_HISTORY_EMPTY"),
        (
            _history(through=6),
            PostgreSQLSchemaStatus.VERSION_UNSUPPORTED,
            "MIGRATION_REQUIRED",
        ),
        (
            {1: _history()[1], 3: _history()[3]},
            PostgreSQLSchemaStatus.VERSION_UNSUPPORTED,
            "MIGRATION_HISTORY_UNSUPPORTED",
        ),
        (
            {**_history(), 99: "0" * 64},
            PostgreSQLSchemaStatus.VERSION_UNSUPPORTED,
            "MIGRATION_HISTORY_UNSUPPORTED",
        ),
        (
            {**_history(), 2: "f" * 64},
            PostgreSQLSchemaStatus.DRIFT_DETECTED,
            "MIGRATION_CHECKSUM_MISMATCH",
        ),
    ],
)
def test_history_classification(
    history: dict[int, str], status: PostgreSQLSchemaStatus, code: str
) -> None:
    result = _check_history(history)

    assert result is not None
    assert result.status is status
    assert result.issues[0].code == code


def test_current_history_is_accepted() -> None:
    assert _check_history(_history()) is None


def test_catalog_issues_cover_columns_indexes_and_constraints() -> None:
    columns = {
        (table, column): expected
        for table, expected_columns in _EXPECTED_COLUMNS.items()
        for column, expected in expected_columns.items()
    }
    del columns[("checkpoints", "legal_hold")]
    columns[("checkpoints", "revision")] = ("int4", True)

    issues = _catalog_issues(
        actual_columns=columns,
        actual_indexes=set(_EXPECTED_INDEXES).difference(
            {"atlas_checkpoints_recovery_candidates_idx"}
        ),
        actual_constraints=set(_EXPECTED_CONSTRAINTS).difference(
            {"atlas_checkpoint_revision_positive"}
        ),
    )

    assert {issue.code for issue in issues} == {
        "COLUMN_INCOMPATIBLE",
        "COLUMN_MISSING",
        "CONSTRAINT_MISSING",
        "INDEX_MISSING",
    }


def test_compatibility_result_is_immutable() -> None:
    result = PostgreSQLSchemaCompatibilityResult(
        status=PostgreSQLSchemaStatus.COMPATIBLE,
        current_version=7,
    )

    with pytest.raises(ValidationError):
        result.current_version = 6


async def test_migrator_applies_every_pending_revision_with_history_records() -> None:
    pool = _MigrationPool({})
    migrator = PostgreSQLCheckpointMigrator(cast(Any, pool))

    assert await migrator.migrate() == (1, 2, 3, 4, 5, 6, 7)
    statements = pool.connection_value.statements
    assert (
        sum("INSERT INTO atlas_agent.schema_migrations" in sql for sql in statements)
        == 7
    )
    assert any("pg_advisory_xact_lock" in sql for sql in statements)


async def test_migrator_is_idempotent_for_valid_history() -> None:
    pool = _MigrationPool(_history())

    assert await PostgreSQLCheckpointMigrator(cast(Any, pool)).migrate() == ()
    assert not any(
        "INSERT INTO atlas_agent.schema_migrations" in sql
        for sql in pool.connection_value.statements
    )


@pytest.mark.parametrize(
    ("history", "target", "message"),
    [
        ({**_history(), 99: "0" * 64}, None, "não suportada"),
        ({1: _history()[1], 3: _history()[3]}, None, "lacuna"),
        (_history(), 6, "mais recente"),
        ({**_history(), 2: "f" * 64}, None, "checksum"),
    ],
)
async def test_migrator_blocks_incompatible_history(
    history: dict[int, str], target: int | None, message: str
) -> None:
    migrator = PostgreSQLCheckpointMigrator(cast(Any, _MigrationPool(history)))

    with pytest.raises(PostgreSQLMigrationError, match=message):
        await migrator.migrate(target_version=target)


async def test_migrator_wraps_database_failure_without_leaking_dsn() -> None:
    migrator = PostgreSQLCheckpointMigrator(
        cast(Any, _MigrationPool({}, unavailable=True))
    )

    with pytest.raises(PostgreSQLMigrationError) as captured:
        await migrator.migrate()

    assert "secret" not in str(captured.value)


@pytest.mark.parametrize("target", [0, 8])
async def test_migrator_rejects_invalid_target_before_database_access(
    target: int,
) -> None:
    migrator = PostgreSQLCheckpointMigrator(cast(Any, object()))

    with pytest.raises(ValueError, match="versão alvo"):
        await migrator.migrate(target_version=target)
