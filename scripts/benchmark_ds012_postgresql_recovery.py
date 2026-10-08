"""Measure DS-012 PostgreSQL recovery primitives in an explicit test database."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from psycopg_pool import AsyncConnectionPool

from atlas_agents import ExecutionCheckpoint, ResumeToken
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointLeaseManager,
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointStore,
    PostgreSQLRecoveryCandidateRepository,
)

ROOT = Path(__file__).parents[1]
FIXTURE = (
    ROOT
    / "packages"
    / "atlas-agent-core"
    / "tests"
    / "fixtures"
    / "checkpoints"
    / "execution-checkpoint-v1.json"
)


def percentile(values: list[float], quantile: float) -> float:
    """Return one nearest-rank percentile."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * quantile))]


def checkpoint(index: int) -> ExecutionCheckpoint:
    """Create one valid distinct checkpoint from the compatibility fixture."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    execution_id = f"ds012-benchmark-{index:04d}"
    payload["execution_id"] = execution_id
    payload["context"]["execution_id"] = execution_id
    payload["pending_approval"]["execution_id"] = execution_id
    payload["pending_approval"]["expires_at"] = (
        datetime.now(UTC) + timedelta(hours=1)
    ).isoformat()
    for event in payload["events"]:
        event["execution_id"] = execution_id
    return ExecutionCheckpoint.model_validate(payload)


async def run(dsn: str, samples: int) -> dict[str, object]:
    """Measure save, discovery, lease, and atomic consume operations."""
    pool = AsyncConnectionPool[Any](dsn, min_size=1, max_size=4, open=False)
    await pool.open(wait=True)
    await PostgreSQLCheckpointMigrator(pool).migrate()
    store = PostgreSQLCheckpointStore(pool)
    repository = PostgreSQLRecoveryCandidateRepository(pool)
    leases = PostgreSQLCheckpointLeaseManager(pool)
    measurements = {name: [] for name in ("save", "discovery", "lease", "consume")}
    try:
        for index in range(samples):
            token = ResumeToken(value=f"ds012-benchmark-token-{index:04d}")
            value = checkpoint(index)
            started = time.perf_counter()
            await store.save(resume_token=token, checkpoint=value)
            measurements["save"].append((time.perf_counter() - started) * 1_000)
            started = time.perf_counter()
            candidates = await repository.list_candidates(limit=samples + 1)
            measurements["discovery"].append((time.perf_counter() - started) * 1_000)
            assert any(item.execution_id == value.execution_id for item in candidates)  # noqa: S101
            started = time.perf_counter()
            lease = await leases.acquire(
                checkpoint_id=value.execution_id,
                owner_id="ds012-benchmark",
                duration=timedelta(seconds=30),
            )
            await leases.release(lease=lease)
            measurements["lease"].append((time.perf_counter() - started) * 1_000)
            started = time.perf_counter()
            await store.consume(token)
            measurements["consume"].append((time.perf_counter() - started) * 1_000)
        return {
            "samples": samples,
            "operations_ms": {
                name: {
                    "median": statistics.median(values),
                    "p95": percentile(values, 0.95),
                }
                for name, values in measurements.items()
            },
        }
    finally:
        await pool.close()


def main() -> None:
    """Parse explicit parameters and print structured benchmark evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--samples", type=int, default=100)
    arguments = parser.parse_args()
    print(  # noqa: T201
        json.dumps(asyncio.run(run(arguments.dsn, arguments.samples)), indent=2)
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()
