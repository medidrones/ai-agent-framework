"""Run reproducible DS-008 purge benchmarks against an explicit test database."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import statistics
import sys
import time
from typing import Any

from psycopg_pool import AsyncConnectionPool

from atlas_agents import (
    CheckpointPurgeConfig,
    CheckpointPurgeCoordinator,
    CheckpointRetentionPolicy,
    PurgeAuthorization,
    __version__,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointPurgeRepository,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.getenv("ATLAS_TEST_POSTGRES_DSN"))
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 1_000, 10_000])
    parser.add_argument("--workers", nargs="+", type=int, default=[2, 5])
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument("--confirm-test-database", action="store_true")
    return parser.parse_args()


def _policy() -> CheckpointRetentionPolicy:
    from datetime import timedelta

    return CheckpointRetentionPolicy(
        policy_version="ds008-benchmark-v1",
        active_ttl=timedelta(hours=1),
        hitl_ttl=timedelta(hours=2),
        consumed_retention=timedelta(days=7),
        expired_retention=timedelta(days=14),
        terminal_retention=timedelta(days=30),
        recovery_retention=timedelta(days=7),
    )


async def _prepare(pool: AsyncConnectionPool[Any], size: int) -> None:
    async with pool.connection() as connection:
        await connection.execute(
            """TRUNCATE atlas_agent.checkpoint_purge_audit,
                      atlas_agent.execution_recovery_attempts,
                      atlas_agent.checkpoint_leases,
                      atlas_agent.checkpoint_tombstones,
                      atlas_agent.checkpoints"""
        )
        await connection.execute(
            """INSERT INTO atlas_agent.checkpoints (
                   token_digest, checkpoint_version, execution_id, agent_id,
                   payload, checkpoint_created_at, expires_at, retention_class,
                   retention_until, retention_policy_version
               )
               SELECT decode(md5(value::text) || md5('atlas-' || value::text), 'hex'),
                      1, 'benchmark-' || value::text, 'benchmark-agent', '{}'::jsonb,
                      clock_timestamp() - interval '30 days',
                      clock_timestamp() - interval '20 days',
                      'waiting_for_approval',
                      clock_timestamp() - interval '1 day',
                      'ds008-benchmark-v1'
               FROM generate_series(1, %s) AS value""",
            (size,),
        )


async def _run_sample(
    pool: AsyncConnectionPool[Any], *, size: int, workers: int, batch_size: int
) -> dict[str, float | int]:
    await _prepare(pool, size)
    config = CheckpointPurgeConfig(
        batch_size=batch_size,
        max_batches_per_run=100,
        dry_run=False,
    )
    services = [
        CheckpointPurgeCoordinator(
            PostgreSQLCheckpointPurgeRepository(pool, policy=_policy())
        )
        for _ in range(workers)
    ]
    started = time.perf_counter()
    results = await asyncio.gather(
        *(
            service.purge_once(
                authorization=PurgeAuthorization(principal_id=f"benchmark-{index}"),
                config=config,
            )
            for index, service in enumerate(services)
        )
    )
    elapsed = time.perf_counter() - started
    purged = sum(result.purged for result in results)
    return {
        "latency_ms": elapsed * 1_000,
        "purged": purged,
        "throughput_per_second": purged / elapsed,
    }


async def _main(arguments: argparse.Namespace) -> list[dict[str, object]]:
    if not arguments.dsn or not arguments.confirm_test_database:
        raise SystemExit(
            "Informe --dsn e --confirm-test-database para autorizar o benchmark "
            "destrutivo."
        )
    if arguments.samples < 2:
        raise SystemExit("Use ao menos duas amostras para calcular mediana e p95.")
    pool = AsyncConnectionPool(
        arguments.dsn,
        min_size=1,
        max_size=max(arguments.workers) + 2,
        open=False,
    )
    await pool.open(wait=True)
    try:
        async with pool.connection() as connection:
            cursor = await connection.execute("SELECT current_database(), version()")
            database, postgres_version = await cursor.fetchone()
        if not str(database).endswith("_test"):
            raise SystemExit(
                "O benchmark só pode usar um banco cujo nome termine em _test."
            )
        await PostgreSQLCheckpointMigrator(pool).migrate()
        report: list[dict[str, object]] = []
        for size in arguments.sizes:
            for workers in arguments.workers:
                samples = [
                    await _run_sample(
                        pool,
                        size=size,
                        workers=workers,
                        batch_size=arguments.batch_size,
                    )
                    for _ in range(arguments.samples)
                ]
                latencies = [float(sample["latency_ms"]) for sample in samples]
                throughputs = [
                    float(sample["throughput_per_second"]) for sample in samples
                ]
                report.append(
                    {
                        "records": size,
                        "workers": workers,
                        "batch_size": arguments.batch_size,
                        "sample_count": arguments.samples,
                        "median_latency_ms": statistics.median(latencies),
                        "p95_latency_ms": statistics.quantiles(latencies, n=20)[18],
                        "median_throughput_per_second": statistics.median(throughputs),
                        "purged_per_sample": [sample["purged"] for sample in samples],
                        "lock_contention": "medida por distribuição SKIP LOCKED",
                        "postgresql": str(postgres_version),
                        "python": platform.python_version(),
                        "atlas": __version__,
                        "cpu_count": os.cpu_count(),
                    }
                )
        return report
    finally:
        await pool.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(  # noqa: T201
        json.dumps(asyncio.run(_main(_arguments())), indent=2, ensure_ascii=False)
    )
