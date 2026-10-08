"""Measure DS-009 critical PostgreSQL access paths in an explicit test database."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from atlas_agents.adapters.checkpoints.postgresql import PostgreSQLCheckpointMigrator


@dataclass(frozen=True, slots=True)
class _Query:
    identifier: str
    sql: str
    parameters: tuple[object, ...]


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.getenv("ATLAS_TEST_POSTGRES_DSN"))
    parser.add_argument("--records", type=int, default=10_000)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--confirm-test-database", action="store_true")
    return parser.parse_args()


async def _prepare(connection: AsyncConnection[Any], records: int) -> bytes:
    await connection.execute(
        """TRUNCATE atlas_agent.checkpoint_purge_audit,
                  atlas_agent.execution_recovery_attempts,
                  atlas_agent.checkpoint_leases,
                  atlas_agent.checkpoint_tombstones,
                  atlas_agent.checkpoints"""
    )
    await connection.execute(
        """INSERT INTO atlas_agent.checkpoints (
               token_digest, checkpoint_version, execution_id, agent_id, tenant_id,
               payload, checkpoint_created_at, expires_at, revision,
               retention_class, retention_until, retention_policy_version
           )
           SELECT decode(md5(value::text) || md5('atlas-' || value::text), 'hex'),
                  1, 'execution-' || value, 'agent', 'tenant-a',
                  '{"status":"running"}'::jsonb,
                  clock_timestamp() - interval '30 days',
                  clock_timestamp() + interval '1 day', 1, 'active',
                  clock_timestamp() - interval '1 day', 'ds009-v1'
           FROM generate_series(1, %s) AS value""",
        (records,),
    )
    await connection.execute(
        """INSERT INTO atlas_agent.checkpoint_leases (
               checkpoint_id, owner_id, fencing_token, acquired_at, expires_at
           )
           SELECT 'execution-' || value, 'worker', 1, clock_timestamp(),
                  clock_timestamp() + interval '1 hour'
           FROM generate_series(1, %s) AS value""",
        (records,),
    )
    await connection.execute(
        """INSERT INTO atlas_agent.checkpoint_tombstones (
               token_digest, execution_id, agent_id, tenant_id, retention_until,
               retention_policy_version
           )
           SELECT decode(md5(value::text) || md5('tomb-' || value::text), 'hex'),
                  'consumed-' || value, 'agent', 'tenant-a',
                  clock_timestamp() + interval '7 days', 'ds009-v1'
           FROM generate_series(1, %s) AS value""",
        (records,),
    )
    await connection.execute("ANALYZE atlas_agent.checkpoints")
    await connection.execute("ANALYZE atlas_agent.checkpoint_leases")
    await connection.execute("ANALYZE atlas_agent.checkpoint_tombstones")
    cursor = await connection.execute(
        "SELECT token_digest FROM atlas_agent.checkpoints LIMIT 1"
    )
    row = await cursor.fetchone()
    if row is None:
        raise RuntimeError("O dataset do benchmark não foi criado.")
    return bytes(row[0])


def _queries(digest: bytes) -> tuple[_Query, ...]:
    return (
        _Query(
            "checkpoint_lookup",
            "SELECT payload, revision FROM atlas_agent.checkpoints "
            "WHERE token_digest = %s",
            (digest,),
        ),
        _Query(
            "atomic_consume",
            "DELETE FROM atlas_agent.checkpoints WHERE token_digest = %s "
            "RETURNING token_digest",
            (digest,),
        ),
        _Query(
            "optimistic_update",
            "UPDATE atlas_agent.checkpoints SET revision = revision + 1 "
            "WHERE token_digest = %s AND revision = 1 RETURNING revision",
            (digest,),
        ),
        _Query(
            "lease_acquisition",
            "UPDATE atlas_agent.checkpoint_leases SET owner_id = 'worker-2', "
            "fencing_token = fencing_token + 1 WHERE checkpoint_id = 'execution-1'",
            (),
        ),
        _Query(
            "lease_renewal",
            "UPDATE atlas_agent.checkpoint_leases SET expires_at = "
            "clock_timestamp() + interval '1 hour' WHERE checkpoint_id = "
            "'execution-1' AND owner_id = 'worker' AND fencing_token = 1",
            (),
        ),
        _Query(
            "recovery_discovery",
            "SELECT execution_id FROM atlas_agent.checkpoints "
            "WHERE tenant_id = 'tenant-a' AND (expires_at IS NULL OR "
            "expires_at > clock_timestamp()) ORDER BY checkpoint_created_at, "
            "execution_id, token_digest LIMIT 100",
            (),
        ),
        _Query(
            "retention_classification",
            "SELECT execution_id FROM atlas_agent.checkpoints "
            "WHERE retention_until <= clock_timestamp() "
            "ORDER BY retention_until, execution_id LIMIT 100",
            (),
        ),
        _Query(
            "purge_discovery",
            "SELECT token_digest FROM atlas_agent.checkpoints "
            "WHERE retention_until <= clock_timestamp() AND legal_hold = FALSE "
            "ORDER BY retention_until, execution_id, token_digest LIMIT 100",
            (),
        ),
        _Query(
            "tombstone_lookup",
            "SELECT execution_id FROM atlas_agent.checkpoint_tombstones "
            "WHERE token_digest = %s",
            (digest,),
        ),
    )


def _index_names(node: dict[str, object]) -> set[str]:
    names: set[str] = set()
    index = node.get("Index Name")
    if isinstance(index, str):
        names.add(index)
    plans = node.get("Plans", [])
    if isinstance(plans, list):
        for child in plans:
            if isinstance(child, dict):
                names.update(_index_names(child))
    return names


async def _measure(
    connection: AsyncConnection[Any], query: _Query, samples: int
) -> dict[str, object]:
    latencies: list[float] = []
    indexes: set[str] = set()
    plan_name = ""
    for _ in range(samples):
        cursor = await connection.execute(
            f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query.sql}",
            query.parameters,
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("O PostgreSQL não retornou o plano solicitado.")
        report = row[0][0]
        plan = report["Plan"]
        latencies.append(float(report["Execution Time"]))
        indexes.update(_index_names(plan))
        plan_name = str(plan["Node Type"])
        await connection.rollback()
    ordered = sorted(latencies)
    return {
        "query_identifier": query.identifier,
        "plan": plan_name,
        "indexes": sorted(indexes),
        "median_latency_ms": statistics.median(latencies),
        "p95_latency_ms": ordered[max(0, round(samples * 0.95) - 1)],
        "sample_count": samples,
    }


async def _main(arguments: argparse.Namespace) -> dict[str, object]:
    if not arguments.dsn or not arguments.confirm_test_database:
        raise SystemExit(
            "Informe --dsn e --confirm-test-database para autorizar o benchmark."
        )
    if arguments.records < 1_000 or arguments.samples < 2:
        raise SystemExit("Use ao menos 1.000 registros e duas amostras.")
    pool = AsyncConnectionPool(arguments.dsn, min_size=1, max_size=2, open=False)
    await pool.open(wait=True)
    try:
        await PostgreSQLCheckpointMigrator(pool).migrate()
        async with pool.connection() as connection:
            metadata = await connection.execute("SELECT current_database(), version()")
            database, version = await metadata.fetchone() or ("", "")
            if not str(database).endswith("_test"):
                raise SystemExit("O benchmark exige um banco com sufixo _test.")
            digest = await _prepare(connection, arguments.records)
            await connection.commit()
            results = [
                await _measure(connection, query, arguments.samples)
                for query in _queries(digest)
            ]
        return {
            "postgresql": str(version),
            "records": arguments.records,
            "queries": results,
        }
    finally:
        await pool.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(  # noqa: T201
        json.dumps(asyncio.run(_main(_arguments())), indent=2, ensure_ascii=False)
    )
