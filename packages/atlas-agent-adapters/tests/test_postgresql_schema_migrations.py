from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from psycopg import errors
from psycopg_pool import AsyncConnectionPool

import atlas_agents.adapters.checkpoints.postgresql.migrations as migration_module
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLMigrationError,
    PostgreSQLSchemaCheckError,
    PostgreSQLSchemaCompatibilityChecker,
    PostgreSQLSchemaStatus,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

DSN = os.getenv("ATLAS_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(
    DSN is None,
    reason="ATLAS_TEST_POSTGRES_DSN não configurada para o PostgreSQL real.",
)


def pool(*, min_size: int = 1, max_size: int = 8) -> AsyncConnectionPool[Any]:
    assert DSN is not None
    return AsyncConnectionPool(DSN, min_size=min_size, max_size=max_size, open=False)


@pytest.fixture
async def isolated_pool() -> AsyncIterator[AsyncConnectionPool[Any]]:
    value = pool()
    await value.open(wait=True)
    async with value.connection() as connection:
        await connection.execute("DROP SCHEMA IF EXISTS atlas_agent CASCADE")
    try:
        yield value
    finally:
        async with value.connection() as connection:
            await connection.execute("DROP SCHEMA IF EXISTS atlas_agent CASCADE")
        await value.close()


async def test_checker_reports_not_initialized_without_mutating_database(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    result = await PostgreSQLSchemaCompatibilityChecker(isolated_pool).check()

    assert result.status is PostgreSQLSchemaStatus.NOT_INITIALIZED
    assert result.current_version is None
    async with isolated_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT to_regnamespace('atlas_agent') IS NULL"
        )
        assert await cursor.fetchone() == (True,)


async def test_fresh_install_is_compatible_and_idempotent(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    migrator = PostgreSQLCheckpointMigrator(isolated_pool)

    assert await migrator.migrate() == (1, 2, 3, 4, 5, 6, 7)
    assert await migrator.migrate() == ()
    result = await PostgreSQLSchemaCompatibilityChecker(isolated_pool).check()

    assert result.status is PostgreSQLSchemaStatus.COMPATIBLE
    assert result.current_version == 7
    assert result.issues == ()


async def test_upgrade_from_revision_five_preserves_durable_state(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    migrator = PostgreSQLCheckpointMigrator(isolated_pool)
    assert await migrator.migrate(target_version=5) == (1, 2, 3, 4, 5)
    async with isolated_pool.connection() as connection:
        await connection.execute(
            """
            INSERT INTO atlas_agent.checkpoints (
                token_digest, checkpoint_version, execution_id, agent_id,
                payload, checkpoint_created_at, revision, retention_class
            ) VALUES (decode('01', 'hex'), 1, 'execution-upgrade', 'agent',
                      '{}'::jsonb, clock_timestamp(), 7, 'active')
            """
        )
        await connection.execute(
            """
            INSERT INTO atlas_agent.checkpoint_leases (
                checkpoint_id, owner_id, fencing_token, acquired_at, expires_at
            ) VALUES ('execution-upgrade', 'worker', 11, clock_timestamp(),
                      clock_timestamp() + interval '1 hour')
            """
        )
    before = await PostgreSQLSchemaCompatibilityChecker(isolated_pool).check()
    assert before.status is PostgreSQLSchemaStatus.VERSION_UNSUPPORTED
    assert before.current_version == 5

    assert await migrator.migrate() == (6, 7)
    async with isolated_pool.connection() as connection:
        cursor = await connection.execute(
            """
            SELECT checkpoint.revision, checkpoint.legal_hold, lease.fencing_token
            FROM atlas_agent.checkpoints AS checkpoint
            JOIN atlas_agent.checkpoint_leases AS lease
              ON lease.checkpoint_id = checkpoint.execution_id
            WHERE checkpoint.execution_id = 'execution-upgrade'
            """
        )
        assert await cursor.fetchone() == (7, False, 11)


async def test_adjacent_revision_six_remains_operational_during_expansion(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    migrator = PostgreSQLCheckpointMigrator(isolated_pool)
    await migrator.migrate(target_version=6)
    async with isolated_pool.connection() as connection:
        await connection.execute(
            """
            INSERT INTO atlas_agent.checkpoints (
                token_digest, checkpoint_version, execution_id, agent_id,
                payload, checkpoint_created_at, retention_class
            ) VALUES (decode('02', 'hex'), 1, 'rolling-execution', 'agent',
                      '{"status":"running"}'::jsonb, clock_timestamp(), 'active')
            """
        )

    assert await migrator.migrate() == (7,)
    async with isolated_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT execution_id FROM atlas_agent.checkpoints "
            "WHERE token_digest = decode('02', 'hex')"
        )
        assert await cursor.fetchone() == ("rolling-execution",)


async def test_unknown_or_gapped_history_is_blocked(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    migrator = PostgreSQLCheckpointMigrator(isolated_pool)
    await migrator.migrate()
    async with isolated_pool.connection() as connection:
        await connection.execute(
            """
            INSERT INTO atlas_agent.schema_migrations (component, version, checksum)
            VALUES ('postgresql_checkpoint_store', 99, repeat('0', 64))
            """
        )

    result = await PostgreSQLSchemaCompatibilityChecker(isolated_pool).check()
    assert result.status is PostgreSQLSchemaStatus.VERSION_UNSUPPORTED
    with pytest.raises(PostgreSQLMigrationError, match="não suportada"):
        await migrator.migrate()


async def test_checksum_and_catalog_drift_are_detected(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    migrator = PostgreSQLCheckpointMigrator(isolated_pool)
    await migrator.migrate()
    async with isolated_pool.connection() as connection:
        await connection.execute(
            "DROP INDEX atlas_agent.atlas_checkpoints_execution_id_idx"
        )

    index_result = await PostgreSQLSchemaCompatibilityChecker(isolated_pool).check()
    assert index_result.status is PostgreSQLSchemaStatus.DRIFT_DETECTED
    assert {issue.code for issue in index_result.issues} == {"INDEX_MISSING"}

    async with isolated_pool.connection() as connection:
        await connection.execute(
            """
            CREATE INDEX atlas_checkpoints_execution_id_idx
            ON atlas_agent.checkpoints (execution_id)
            """
        )
        await connection.execute(
            """
            UPDATE atlas_agent.schema_migrations
            SET checksum = repeat('f', 64)
            WHERE component = 'postgresql_checkpoint_store' AND version = 2
            """
        )
    checksum_result = await PostgreSQLSchemaCompatibilityChecker(isolated_pool).check()
    assert checksum_result.status is PostgreSQLSchemaStatus.DRIFT_DETECTED
    assert checksum_result.issues[0].code == "MIGRATION_CHECKSUM_MISMATCH"


async def test_missing_required_column_is_detected(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    await PostgreSQLCheckpointMigrator(isolated_pool).migrate()
    async with isolated_pool.connection() as connection:
        await connection.execute(
            "ALTER TABLE atlas_agent.checkpoints DROP COLUMN legal_hold"
        )

    result = await PostgreSQLSchemaCompatibilityChecker(isolated_pool).check()

    assert result.status is PostgreSQLSchemaStatus.DRIFT_DETECTED
    assert any(
        issue.code == "COLUMN_MISSING"
        and issue.object_name == "atlas_agent.checkpoints.legal_hold"
        for issue in result.issues
    )


async def test_two_migration_runners_serialize_on_the_advisory_lock(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    results = await asyncio.gather(
        PostgreSQLCheckpointMigrator(isolated_pool).migrate(),
        PostgreSQLCheckpointMigrator(isolated_pool).migrate(),
    )

    assert sorted(len(result) for result in results) == [0, 7]
    async with isolated_pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT count(*) FROM atlas_agent.schema_migrations"
        )
        assert await cursor.fetchone() == (7,)


async def test_failed_migration_rolls_back_schema_and_history(
    isolated_pool: AsyncConnectionPool[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    migrator = PostgreSQLCheckpointMigrator(isolated_pool)
    await migrator.migrate()
    test_migration = migration_module._Migration(8, "008_test_failure.sql")
    monkeypatch.setattr(
        migration_module, "_MIGRATIONS", (*migration_module._MIGRATIONS, test_migration)
    )
    monkeypatch.setattr(migration_module, "LATEST_SCHEMA_VERSION", 8)
    original_loader = migration_module._migration_sql

    def migration_sql(resource: str) -> str:
        if resource == "008_test_failure.sql":
            return "CREATE TABLE atlas_agent.must_rollback (id int); SELECT 1 / 0;"
        return original_loader(resource)

    monkeypatch.setattr(migration_module, "_migration_sql", migration_sql)

    with pytest.raises(PostgreSQLMigrationError):
        await migrator.migrate()
    async with isolated_pool.connection() as connection:
        table_cursor = await connection.execute(
            "SELECT to_regclass('atlas_agent.must_rollback')"
        )
        history_cursor = await connection.execute(
            "SELECT count(*) FROM atlas_agent.schema_migrations WHERE version = 8"
        )
        assert await table_cursor.fetchone() == (None,)
        assert await history_cursor.fetchone() == (0,)


async def test_cancelled_migration_releases_waiter_without_partial_history(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    blocker = await isolated_pool.getconn()
    try:
        await blocker.execute("BEGIN")
        await blocker.execute("SELECT pg_advisory_xact_lock(4283002)")
        task = asyncio.create_task(
            PostgreSQLCheckpointMigrator(isolated_pool).migrate()
        )
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        await blocker.rollback()
        await isolated_pool.putconn(blocker)

    assert await PostgreSQLCheckpointMigrator(isolated_pool).migrate() == (
        1,
        2,
        3,
        4,
        5,
        6,
        7,
    )


async def test_runtime_role_operates_without_ddl_privileges(
    isolated_pool: AsyncConnectionPool[Any],
) -> None:
    await PostgreSQLCheckpointMigrator(isolated_pool).migrate()
    async with isolated_pool.connection() as connection:
        await connection.execute("DROP ROLE IF EXISTS atlas_ds009_runtime")
        await connection.execute("CREATE ROLE atlas_ds009_runtime NOLOGIN")
        await connection.execute(
            "GRANT USAGE ON SCHEMA atlas_agent TO atlas_ds009_runtime"
        )
        await connection.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA atlas_agent "
            "TO atlas_ds009_runtime"
        )
        await connection.commit()
        await connection.execute("SET ROLE atlas_ds009_runtime")
        cursor = await connection.execute(
            "SELECT count(*) FROM atlas_agent.checkpoints"
        )
        assert await cursor.fetchone() == (0,)
        with pytest.raises(errors.InsufficientPrivilege):
            await connection.execute("CREATE TABLE atlas_agent.forbidden (id int)")
        await connection.rollback()
        await connection.execute("RESET ROLE")
        await connection.execute("DROP OWNED BY atlas_ds009_runtime")
        await connection.execute("DROP ROLE IF EXISTS atlas_ds009_runtime")


async def test_closed_pool_schema_failure_is_safe() -> None:
    closed_pool = pool()

    with pytest.raises(PostgreSQLSchemaCheckError) as captured:
        await PostgreSQLSchemaCompatibilityChecker(closed_pool).check()

    assert "postgresql://" not in str(captured.value)


def test_invalid_target_version_is_rejected_before_pool_access() -> None:
    migrator = PostgreSQLCheckpointMigrator(cast(Any, object()))

    with pytest.raises(ValueError, match="versão alvo"):
        asyncio.run(migrator.migrate(target_version=0))
