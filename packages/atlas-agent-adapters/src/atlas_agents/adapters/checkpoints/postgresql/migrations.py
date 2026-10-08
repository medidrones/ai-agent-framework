"""Versioned migration runner for the PostgreSQL checkpoint schema."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Final

from psycopg import DatabaseError
from psycopg_pool import AsyncConnectionPool, PoolTimeout

from atlas_agents.adapters.checkpoints.postgresql.errors import (
    PostgreSQLMigrationError,
)

_COMPONENT: Final = "postgresql_checkpoint_store"
_ADVISORY_LOCK_ID: Final = 4_283_002
_BOOTSTRAP_SQL: Final = """
CREATE SCHEMA IF NOT EXISTS atlas_agent;
CREATE TABLE IF NOT EXISTS atlas_agent.schema_migrations (
    component TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (component, version)
);
"""


@dataclass(frozen=True, slots=True)
class _Migration:
    version: int
    resource: str


_MIGRATIONS: Final = (
    _Migration(1, "001_create_checkpoint_store.sql"),
    _Migration(2, "002_add_checkpoint_revision.sql"),
    _Migration(3, "003_create_checkpoint_leases.sql"),
    _Migration(4, "004_create_recovery_attempts.sql"),
)


class PostgreSQLCheckpointMigrator:
    """Apply immutable checkpoint migrations under a transaction advisory lock."""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        """Use a caller-owned pool with an explicit lifecycle."""
        self._pool = pool

    async def migrate(self) -> tuple[int, ...]:
        """Apply pending migrations and return the versions applied now."""
        try:
            async with self._pool.connection() as connection:
                await connection.execute(
                    "SELECT pg_advisory_xact_lock(%s)", (_ADVISORY_LOCK_ID,)
                )
                await connection.execute(_BOOTSTRAP_SQL)
                cursor = await connection.execute(
                    """
                    SELECT version, checksum
                    FROM atlas_agent.schema_migrations
                    WHERE component = %s
                    ORDER BY version
                    """,
                    (_COMPONENT,),
                )
                applied = dict(await cursor.fetchall())
                completed: list[int] = []
                for migration in _MIGRATIONS:
                    sql = _migration_sql(migration.resource)
                    checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                    previous = applied.get(migration.version)
                    if previous is not None:
                        if previous != checksum:
                            raise PostgreSQLMigrationError(
                                "A migration PostgreSQL aplicada possui checksum "
                                "incompatível."
                            )
                        continue
                    await connection.execute(sql)
                    await connection.execute(
                        """
                        INSERT INTO atlas_agent.schema_migrations
                            (component, version, checksum)
                        VALUES (%s, %s, %s)
                        """,
                        (_COMPONENT, migration.version, checksum),
                    )
                    completed.append(migration.version)
                return tuple(completed)
        except PostgreSQLMigrationError:
            raise
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLMigrationError(
                "Não foi possível aplicar as migrations do checkpoint PostgreSQL."
            ) from error


def _migration_sql(resource: str) -> str:
    migration = files("atlas_agents.adapters.checkpoints.postgresql.sql").joinpath(
        resource
    )
    return migration.read_text(encoding="utf-8")
