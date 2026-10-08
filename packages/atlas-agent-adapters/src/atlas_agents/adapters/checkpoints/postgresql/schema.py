"""Read-only compatibility checks for the PostgreSQL checkpoint schema."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Final

from psycopg import DatabaseError
from psycopg_pool import AsyncConnectionPool, PoolTimeout
from pydantic import BaseModel, ConfigDict, Field

from atlas_agents.adapters.checkpoints.postgresql.errors import (
    PostgreSQLSchemaCheckError,
)
from atlas_agents.adapters.checkpoints.postgresql.migrations import (
    _COMPONENT,
    _MIGRATIONS,
    LATEST_SCHEMA_VERSION,
    _migration_sql,
)


class PostgreSQLSchemaStatus(StrEnum):
    """Classify the compatibility of a deployed checkpoint schema."""

    COMPATIBLE = "SCHEMA_COMPATIBLE"
    DRIFT_DETECTED = "SCHEMA_DRIFT_DETECTED"
    VERSION_UNSUPPORTED = "SCHEMA_VERSION_UNSUPPORTED"
    NOT_INITIALIZED = "SCHEMA_NOT_INITIALIZED"


class PostgreSQLSchemaIssue(BaseModel):
    """Describe one safe schema incompatibility without exposing stored data."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    object_name: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class PostgreSQLSchemaCompatibilityResult(BaseModel):
    """Return the deterministic result of one read-only schema check."""

    model_config = ConfigDict(frozen=True)

    status: PostgreSQLSchemaStatus
    current_version: int | None
    target_version: int = LATEST_SCHEMA_VERSION
    issues: tuple[PostgreSQLSchemaIssue, ...] = ()


_EXPECTED_COLUMNS: Final = {
    "schema_migrations": {
        "component": ("text", False),
        "version": ("int4", False),
        "checksum": ("text", False),
        "applied_at": ("timestamptz", False),
    },
    "checkpoints": {
        "token_digest": ("bytea", False),
        "checkpoint_version": ("int4", False),
        "execution_id": ("text", False),
        "agent_id": ("text", False),
        "tenant_id": ("text", True),
        "payload": ("jsonb", False),
        "checkpoint_created_at": ("timestamptz", False),
        "stored_at": ("timestamptz", False),
        "expires_at": ("timestamptz", True),
        "revision": ("int8", False),
        "modified_at": ("timestamptz", False),
        "retention_class": ("text", False),
        "retention_until": ("timestamptz", True),
        "retention_policy_version": ("text", True),
        "legal_hold": ("bool", False),
    },
    "checkpoint_leases": {
        "checkpoint_id": ("text", False),
        "owner_id": ("text", True),
        "fencing_token": ("int8", False),
        "acquired_at": ("timestamptz", True),
        "expires_at": ("timestamptz", True),
    },
    "execution_recovery_attempts": {
        "attempt_id": ("uuid", False),
        "execution_id": ("text", False),
        "checkpoint_id": ("text", False),
        "owner_id": ("text", False),
        "fencing_token": ("int8", False),
        "attempt_number": ("int4", False),
        "started_at": ("timestamptz", False),
        "completed_at": ("timestamptz", True),
        "outcome": ("text", True),
        "reason_code": ("text", True),
        "retention_until": ("timestamptz", True),
        "retention_policy_version": ("text", True),
    },
    "checkpoint_tombstones": {
        "token_digest": ("bytea", False),
        "execution_id": ("text", False),
        "agent_id": ("text", False),
        "tenant_id": ("text", True),
        "consumed_at": ("timestamptz", False),
        "retention_until": ("timestamptz", False),
        "retention_policy_version": ("text", False),
        "fencing_token": ("int8", True),
        "legal_hold": ("bool", False),
    },
    "checkpoint_purge_audit": {
        "audit_id": ("uuid", False),
        "purge_run_id": ("uuid", False),
        "operation_id": ("uuid", False),
        "checkpoint_id": ("text", False),
        "execution_id": ("text", False),
        "tenant_id": ("text", True),
        "record_kind": ("text", False),
        "outcome": ("text", False),
        "reason_code": ("text", False),
        "policy_version": ("text", False),
        "occurred_at": ("timestamptz", False),
    },
}

_EXPECTED_INDEXES: Final = frozenset(
    {
        "atlas_checkpoints_execution_id_idx",
        "atlas_checkpoints_tenant_id_idx",
        "atlas_checkpoints_expires_at_idx",
        "atlas_checkpoint_leases_expiration_idx",
        "atlas_recovery_attempts_execution_idx",
        "atlas_checkpoints_retention_idx",
        "atlas_checkpoint_tombstones_retention_idx",
        "atlas_checkpoint_tombstones_tenant_idx",
        "atlas_checkpoints_purge_candidates_idx",
        "atlas_tombstones_purge_candidates_idx",
        "atlas_checkpoint_purge_audit_run_idx",
        "atlas_checkpoint_purge_audit_tenant_idx",
        "atlas_checkpoints_recovery_candidates_idx",
    }
)

_EXPECTED_CONSTRAINTS: Final = frozenset(
    {
        "schema_migrations_pkey",
        "checkpoints_pkey",
        "atlas_checkpoint_expiration_order",
        "atlas_checkpoint_revision_positive",
        "checkpoint_leases_pkey",
        "atlas_checkpoint_lease_fencing_non_negative",
        "atlas_checkpoint_lease_state_consistent",
        "execution_recovery_attempts_pkey",
        "atlas_recovery_attempt_number_unique",
        "atlas_recovery_completion_consistent",
        "atlas_checkpoint_retention_class_valid",
        "checkpoint_tombstones_pkey",
        "atlas_tombstone_retention_order",
        "atlas_tombstone_fencing_positive",
        "checkpoint_purge_audit_pkey",
        "checkpoint_purge_audit_operation_id_key",
    }
)


class PostgreSQLSchemaCompatibilityChecker:
    """Inspect schema metadata without applying migrations or loading payloads."""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        """Use a caller-owned connection pool."""
        self._pool = pool

    async def check(self) -> PostgreSQLSchemaCompatibilityResult:
        """Compare migration history and catalog objects with the certified schema."""
        try:
            async with self._pool.connection() as connection:
                initialized = await connection.execute(
                    "SELECT to_regclass('atlas_agent.schema_migrations')"
                )
                initialized_row = await initialized.fetchone()
                if initialized_row is None or initialized_row[0] is None:
                    return PostgreSQLSchemaCompatibilityResult(
                        status=PostgreSQLSchemaStatus.NOT_INITIALIZED,
                        current_version=None,
                    )

                history_cursor = await connection.execute(
                    """
                    SELECT version, checksum
                    FROM atlas_agent.schema_migrations
                    WHERE component = %s
                    ORDER BY version
                    """,
                    (_COMPONENT,),
                )
                history = dict(await history_cursor.fetchall())
                history_result = _check_history(history)
                if history_result is not None:
                    return history_result

                columns_cursor = await connection.execute(
                    """
                    SELECT table_name, column_name, udt_name, is_nullable = 'YES'
                    FROM information_schema.columns
                    WHERE table_schema = 'atlas_agent'
                    ORDER BY table_name, ordinal_position
                    """
                )
                column_rows = await columns_cursor.fetchall()
                actual_columns = {
                    (str(table), str(column)): (str(data_type), bool(nullable))
                    for table, column, data_type, nullable in column_rows
                }
                indexes_cursor = await connection.execute(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = 'atlas_agent'"
                )
                actual_indexes = {
                    str(row[0]) for row in await indexes_cursor.fetchall()
                }
                constraints_cursor = await connection.execute(
                    """
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'atlas_agent'
                    """
                )
                actual_constraints = {
                    str(row[0]) for row in await constraints_cursor.fetchall()
                }
        except (DatabaseError, PoolTimeout) as error:
            raise PostgreSQLSchemaCheckError(
                "Não foi possível verificar o schema PostgreSQL."
            ) from error

        issues = _catalog_issues(
            actual_columns=actual_columns,
            actual_indexes=actual_indexes,
            actual_constraints=actual_constraints,
        )
        return PostgreSQLSchemaCompatibilityResult(
            status=(
                PostgreSQLSchemaStatus.DRIFT_DETECTED
                if issues
                else PostgreSQLSchemaStatus.COMPATIBLE
            ),
            current_version=LATEST_SCHEMA_VERSION,
            issues=issues,
        )


def _check_history(
    history: dict[int, str],
) -> PostgreSQLSchemaCompatibilityResult | None:
    expected = {
        migration.version: hashlib.sha256(
            _migration_sql(migration.resource).encode("utf-8")
        ).hexdigest()
        for migration in _MIGRATIONS
    }
    versions = sorted(history)
    if not versions:
        return PostgreSQLSchemaCompatibilityResult(
            status=PostgreSQLSchemaStatus.VERSION_UNSUPPORTED,
            current_version=0,
            issues=(
                PostgreSQLSchemaIssue(
                    code="MIGRATION_HISTORY_EMPTY",
                    object_name="atlas_agent.schema_migrations",
                    detail="O componente não possui revisões registradas.",
                ),
            ),
        )
    unknown = set(versions).difference(expected)
    if unknown or versions != list(range(1, versions[-1] + 1)):
        return PostgreSQLSchemaCompatibilityResult(
            status=PostgreSQLSchemaStatus.VERSION_UNSUPPORTED,
            current_version=versions[-1],
            issues=(
                PostgreSQLSchemaIssue(
                    code="MIGRATION_HISTORY_UNSUPPORTED",
                    object_name="atlas_agent.schema_migrations",
                    detail="O histórico contém revisão desconhecida ou lacuna.",
                ),
            ),
        )
    checksum_issues = tuple(
        PostgreSQLSchemaIssue(
            code="MIGRATION_CHECKSUM_MISMATCH",
            object_name=f"migration:{version}",
            detail="O checksum persistido diverge da migration imutável.",
        )
        for version, checksum in history.items()
        if expected[version] != checksum
    )
    if checksum_issues:
        return PostgreSQLSchemaCompatibilityResult(
            status=PostgreSQLSchemaStatus.DRIFT_DETECTED,
            current_version=versions[-1],
            issues=checksum_issues,
        )
    if versions[-1] != LATEST_SCHEMA_VERSION:
        return PostgreSQLSchemaCompatibilityResult(
            status=PostgreSQLSchemaStatus.VERSION_UNSUPPORTED,
            current_version=versions[-1],
            issues=(
                PostgreSQLSchemaIssue(
                    code="MIGRATION_REQUIRED",
                    object_name="atlas_agent.schema_migrations",
                    detail="O schema requer migrations antes do uso por esta versão.",
                ),
            ),
        )
    return None


def _catalog_issues(
    *,
    actual_columns: dict[tuple[str, str], tuple[str, bool]],
    actual_indexes: set[str],
    actual_constraints: set[str],
) -> tuple[PostgreSQLSchemaIssue, ...]:
    issues: list[PostgreSQLSchemaIssue] = []
    for table, columns in _EXPECTED_COLUMNS.items():
        for column, expected in columns.items():
            name = f"atlas_agent.{table}.{column}"
            actual = actual_columns.get((table, column))
            if actual is None:
                issues.append(
                    PostgreSQLSchemaIssue(
                        code="COLUMN_MISSING",
                        object_name=name,
                        detail="A coluna obrigatória não existe.",
                    )
                )
            elif actual != expected:
                issues.append(
                    PostgreSQLSchemaIssue(
                        code="COLUMN_INCOMPATIBLE",
                        object_name=name,
                        detail="Tipo ou nulabilidade diverge do schema certificado.",
                    )
                )
    issues.extend(
        PostgreSQLSchemaIssue(
            code="INDEX_MISSING",
            object_name=f"atlas_agent.{index}",
            detail="O índice obrigatório não existe.",
        )
        for index in sorted(_EXPECTED_INDEXES.difference(actual_indexes))
    )
    issues.extend(
        PostgreSQLSchemaIssue(
            code="CONSTRAINT_MISSING",
            object_name=f"atlas_agent.{constraint}",
            detail="A constraint obrigatória não existe.",
        )
        for constraint in sorted(_EXPECTED_CONSTRAINTS.difference(actual_constraints))
    )
    return tuple(issues)
