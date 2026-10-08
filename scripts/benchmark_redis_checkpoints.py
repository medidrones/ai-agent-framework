"""Measure a reproducible Redis checkpoint performance baseline."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

import redis
from redis.asyncio import Redis

from atlas_agents import ExecutionCheckpoint, ResumeToken
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


def checkpoint(payload_bytes: int) -> ExecutionCheckpoint:
    """Create a valid fixture with a controlled JSON metadata payload."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["pending_approval"]["expires_at"] = None
    payload["metadata"]["benchmark_payload"] = "x" * payload_bytes
    return ExecutionCheckpoint.model_validate(payload)


def summary(values: list[float]) -> dict[str, float]:
    """Return median and inclusive p95 latency in milliseconds."""
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return {
        "median_ms": round(statistics.median(ordered) * 1000, 3),
        "p95_ms": round(ordered[p95_index] * 1000, 3),
    }


async def measure(
    store: RedisCheckpointStore,
    *,
    samples: int,
    payload_bytes: int,
) -> dict[str, Any]:
    """Measure save, read, CAS, and consume with independent keys."""
    value = checkpoint(payload_bytes)
    save_times: list[float] = []
    read_times: list[float] = []
    cas_times: list[float] = []
    consume_times: list[float] = []
    started = perf_counter()
    for index in range(samples):
        token = ResumeToken(value=f"benchmark-{payload_bytes}-{index}-{uuid4().hex}")
        before = perf_counter()
        await store.save(resume_token=token, checkpoint=value)
        save_times.append(perf_counter() - before)
        before = perf_counter()
        await store.read(token)
        read_times.append(perf_counter() - before)
        before = perf_counter()
        await store.compare_and_swap(
            resume_token=token,
            checkpoint=value,
            expected_revision=1,
        )
        cas_times.append(perf_counter() - before)
        before = perf_counter()
        await store.consume(token)
        consume_times.append(perf_counter() - before)
    elapsed = perf_counter() - started
    return {
        "payload_bytes": payload_bytes,
        "samples": samples,
        "save": summary(save_times),
        "read": summary(read_times),
        "conditional_update": summary(cas_times),
        "atomic_consume": summary(consume_times),
        "throughput_operations_per_second": round(samples * 4 / elapsed, 2),
    }


async def concurrent_workload(
    store: RedisCheckpointStore, *, workers: int
) -> dict[str, float | int]:
    """Measure one save/read/consume cycle per concurrent worker."""
    value = checkpoint(1024)

    async def worker(index: int) -> None:
        token = ResumeToken(value=f"concurrent-{index}-{uuid4().hex}")
        await store.save(resume_token=token, checkpoint=value)
        await store.read(token)
        await store.consume(token)

    started = perf_counter()
    await asyncio.gather(*(worker(index) for index in range(workers)))
    elapsed = perf_counter() - started
    return {
        "workers": workers,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_operations_per_second": round(workers * 3 / elapsed, 2),
    }


async def run(*, url: str, samples: int, workers: int) -> None:
    """Execute the baseline against an explicit Redis endpoint."""
    client = Redis.from_url(url, decode_responses=False, max_connections=workers + 8)
    try:
        info = cast(dict[str, Any], await client.info("server"))
        persistence = cast(dict[str, Any], await client.info("persistence"))
        memory = cast(dict[str, Any], await client.info("memory"))
        config = await client.config_get("maxmemory-policy")
        store = RedisCheckpointStore(
            cast(RedisCheckpointClient, client),
            namespace=f"benchmark:{uuid4().hex}",
            token_hmac_key=b"benchmark-hmac-key-material-32bytes",
        )
        workloads = [
            await measure(store, samples=samples, payload_bytes=size)
            for size in (1024, 16 * 1024, 256 * 1024)
        ]
        result = {
            "redis_version": info.get("redis_version"),
            "redis_mode": info.get("redis_mode"),
            "aof_enabled": persistence.get("aof_enabled"),
            "rdb_last_bgsave_status": persistence.get("rdb_last_bgsave_status"),
            "eviction_policy": config.get("maxmemory-policy"),
            "python_version": platform.python_version(),
            "redis_client_version": redis.__version__,
            "operating_system": platform.platform(),
            "memory_used_bytes": memory.get("used_memory"),
            "connection_pool_max": workers + 8,
            "workloads": workloads,
            "concurrent": await concurrent_workload(store, workers=workers),
        }
        sys.stdout.write(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    finally:
        await client.aclose()


def main() -> None:
    """Parse explicit benchmark parameters."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=100)
    arguments = parser.parse_args()
    if arguments.samples <= 0 or arguments.workers <= 0:
        parser.error("samples e workers devem ser positivos")
    asyncio.run(
        run(url=arguments.url, samples=arguments.samples, workers=arguments.workers)
    )


if __name__ == "__main__":
    main()
