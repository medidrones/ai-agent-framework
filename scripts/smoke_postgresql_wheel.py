"""Validate an installed adapters wheel against an explicit PostgreSQL test DB."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from psycopg_pool import AsyncConnectionPool

from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLSchemaCompatibilityChecker,
    PostgreSQLSchemaStatus,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--confirm-test-database", action="store_true")
    return parser.parse_args()


async def _main(arguments: argparse.Namespace) -> dict[str, object]:
    if not arguments.confirm_test_database:
        raise SystemExit("Confirme explicitamente o banco de teste.")
    pool: AsyncConnectionPool[Any] = AsyncConnectionPool(
        arguments.dsn, min_size=1, max_size=2, open=False
    )
    await pool.open(wait=True)
    try:
        async with pool.connection() as connection:
            cursor = await connection.execute("SELECT current_database()")
            row = await cursor.fetchone()
            database = "" if row is None else str(row[0])
        if not database.endswith("_test"):
            raise SystemExit("O smoke test exige banco com sufixo _test.")
        applied = await PostgreSQLCheckpointMigrator(pool).migrate()
        result = await PostgreSQLSchemaCompatibilityChecker(pool).check()
        if result.status is not PostgreSQLSchemaStatus.COMPATIBLE:
            raise SystemExit(f"Schema incompatível: {result.status.value}")
        return {
            "database": database,
            "applied": list(applied),
            "schema_version": result.current_version,
            "status": result.status.value,
        }
    finally:
        await pool.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(  # noqa: T201
        json.dumps(asyncio.run(_main(_arguments())), indent=2, ensure_ascii=False)
    )
