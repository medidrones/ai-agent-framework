"""Measure Redis atomic resume operations against an explicitly selected host."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from datetime import timedelta
from pathlib import Path
from typing import cast
from uuid import uuid4

from redis.asyncio import Redis

from atlas_agents import CheckpointNotFoundError, ExecutionCheckpoint, ResumeToken
from atlas_agents.adapters.checkpoints.redis import RedisCheckpointStore
from atlas_agents.adapters.checkpoints.redis.store import RedisCheckpointClient

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
    """Return one nearest-rank latency percentile."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * quantile))]


async def run(url: str, samples: int) -> dict[str, object]:
    """Execute consume, fenced consume, and contention measurements."""
    client = Redis.from_url(url, decode_responses=False)
    store = RedisCheckpointStore(
        cast(RedisCheckpointClient, client),
        namespace=f"ds011-benchmark:{uuid4().hex}",
        token_hmac_key=b"benchmark-hmac-key-material-at-least-32",
    )
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["pending_approval"]["expires_at"] = None
    checkpoint = ExecutionCheckpoint.model_validate(payload)
    consume_latencies: list[float] = []
    lease_latencies: list[float] = []
    try:
        for index in range(samples):
            token = ResumeToken(value=f"consume-{index}-{uuid4().hex}")
            await store.save(resume_token=token, checkpoint=checkpoint)
            started = time.perf_counter()
            await store.consume(token)
            consume_latencies.append((time.perf_counter() - started) * 1_000)

        for index in range(min(samples, 300)):
            token = ResumeToken(value=f"lease-{index}-{uuid4().hex}")
            await store.save(resume_token=token, checkpoint=checkpoint)
            started = time.perf_counter()
            lease = await store.acquire_lease(
                resume_token=token,
                owner_id="benchmark-worker",
                duration=timedelta(seconds=30),
            )
            await store.consume_authorized_leased(
                resume_token=token, lease=lease, authorize=lambda _: None
            )
            lease_latencies.append((time.perf_counter() - started) * 1_000)

        contention_token = ResumeToken(value=f"contention-{uuid4().hex}")
        await store.save(resume_token=contention_token, checkpoint=checkpoint)
        started = time.perf_counter()
        outcomes = await asyncio.gather(
            *(store.consume(contention_token) for _ in range(100)),
            return_exceptions=True,
        )
        elapsed = time.perf_counter() - started
        return {
            "samples": samples,
            "atomic_consume_ms": {
                "median": statistics.median(consume_latencies),
                "p95": percentile(consume_latencies, 0.95),
            },
            "lease_and_fenced_consume_ms": {
                "samples": len(lease_latencies),
                "median": statistics.median(lease_latencies),
                "p95": percentile(lease_latencies, 0.95),
            },
            "contention_100": {
                "elapsed_ms": elapsed * 1_000,
                "throughput_ops_s": 100 / elapsed,
                "winners": sum(
                    isinstance(item, ExecutionCheckpoint) for item in outcomes
                ),
                "conflicts": sum(
                    isinstance(item, CheckpointNotFoundError) for item in outcomes
                ),
            },
        }
    finally:
        await client.aclose()


def main() -> None:
    """Parse explicit benchmark parameters and render structured evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--samples", type=int, default=1_000)
    arguments = parser.parse_args()
    print(  # noqa: T201
        json.dumps(asyncio.run(run(arguments.url, arguments.samples)), indent=2)
    )


if __name__ == "__main__":
    main()
