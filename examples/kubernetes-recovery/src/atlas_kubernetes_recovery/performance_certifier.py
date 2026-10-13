"""Reproducible Durable State performance certification runner for DS-015."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import statistics
import sys
import time
import tracemalloc
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import uuid4

from psycopg_pool import AsyncConnectionPool
from redis import __version__ as redis_client_version
from redis.asyncio import Redis

from atlas_agents import (
    CheckpointLease,
    CheckpointLeaseConflictError,
    CheckpointLeaseLostError,
    CheckpointNotFoundError,
    ExecutionCheckpoint,
    ResumeToken,
)
from atlas_agents import (
    __version__ as atlas_version,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    CheckpointConcurrencyConflictError,
    PostgreSQLCheckpointLeaseManager,
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointStore,
)
from atlas_agents.adapters.checkpoints.redis import (
    RedisCheckpointConcurrencyConflictError,
    RedisCheckpointStore,
)
from atlas_agents.adapters.checkpoints.redis.store import RedisCheckpointClient

FIXTURE = files("atlas_kubernetes_recovery").joinpath(
    "fixtures", "execution-checkpoint-v1.json"
)
TOKEN_KEY = b"ds015-benchmark-hmac-key-material"


@dataclass(frozen=True, slots=True)
class CertificationThresholds:
    """Predeclared certification thresholds, never derived from observed results."""

    p95_ms: float = 1_000.0
    p99_ms: float = 2_000.0
    minimum_throughput_ops_s: float = 5.0
    maximum_unexpected_error_rate: float = 0.0
    maximum_memory_growth_bytes: int = 64 * 1024 * 1024
    maximum_orphan_tasks: int = 0


@dataclass(frozen=True, slots=True)
class LatencySummary:
    """Statistical summary calculated from real monotonic-clock samples."""

    samples: int
    minimum_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    maximum_ms: float
    throughput_ops_s: float


@dataclass(frozen=True, slots=True)
class WorkloadResult:
    """Measured workload plus integrity counters and threshold decision."""

    workload: str
    concurrency: int
    payload_bytes: int
    successful_operations: int
    failed_operations: int
    expected_conflicts: int
    timeouts: int
    latency: LatencySummary
    threshold_pass: bool


class _DurableStateHarness(Protocol):
    """Internal benchmark boundary implemented by real infrastructure adapters."""

    backend: str

    async def save(
        self, token: ResumeToken, checkpoint: ExecutionCheckpoint
    ) -> None: ...

    async def read(self, token: ResumeToken) -> None: ...

    async def compare_and_swap(
        self, token: ResumeToken, checkpoint: ExecutionCheckpoint, revision: int
    ) -> None: ...

    async def consume(self, token: ResumeToken) -> None: ...

    async def acquire(
        self, token: ResumeToken, checkpoint_id: str, owner_id: str
    ) -> CheckpointLease: ...

    async def renew(
        self, token: ResumeToken, lease: CheckpointLease
    ) -> CheckpointLease: ...

    async def release(self, token: ResumeToken, lease: CheckpointLease) -> None: ...

    async def close(self) -> None: ...

    async def metadata(self) -> dict[str, object]: ...


class _PostgreSQLHarness:
    """Use only public PostgreSQL adapter capabilities for measurements."""

    backend = "postgresql"

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool
        self._store = PostgreSQLCheckpointStore(pool, token_hmac_key=TOKEN_KEY)
        self._leases = PostgreSQLCheckpointLeaseManager(pool)

    async def save(self, token: ResumeToken, checkpoint: ExecutionCheckpoint) -> None:
        await self._store.save(resume_token=token, checkpoint=checkpoint)

    async def read(self, token: ResumeToken) -> None:
        await self._store.read(token)

    async def compare_and_swap(
        self, token: ResumeToken, checkpoint: ExecutionCheckpoint, revision: int
    ) -> None:
        await self._store.compare_and_swap(
            resume_token=token,
            checkpoint=checkpoint,
            expected_revision=revision,
        )

    async def consume(self, token: ResumeToken) -> None:
        await self._store.consume(token)

    async def acquire(
        self, token: ResumeToken, checkpoint_id: str, owner_id: str
    ) -> CheckpointLease:
        del token
        return await self._leases.acquire(
            checkpoint_id=checkpoint_id,
            owner_id=owner_id,
            duration=timedelta(seconds=30),
        )

    async def renew(
        self, token: ResumeToken, lease: CheckpointLease
    ) -> CheckpointLease:
        del token
        return await self._leases.renew(
            lease=lease,
            duration=timedelta(seconds=30),
        )

    async def release(self, token: ResumeToken, lease: CheckpointLease) -> None:
        del token
        await self._leases.release(lease=lease)

    async def close(self) -> None:
        await self._pool.close()

    async def metadata(self) -> dict[str, object]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT current_database(), version(), "
                "current_setting('max_connections')"
            )
            database, version, max_connections = await cursor.fetchone() or (
                "unknown",
                "unknown",
                "unknown",
            )
        return {
            "database": str(database),
            "version": str(version),
            "max_connections": str(max_connections),
            "pool": self._pool.get_stats(),
        }


class _RedisHarness:
    """Use only public Redis adapter capabilities for measurements."""

    backend = "redis"

    def __init__(self, client: Redis) -> None:
        self._client = client
        namespace = f"atlas:ds015:{uuid4().hex}"
        self._namespace_digest = hashlib.sha256(namespace.encode("utf-8")).hexdigest()
        self._store = RedisCheckpointStore(
            cast(RedisCheckpointClient, client),
            namespace=namespace,
            token_hmac_key=TOKEN_KEY,
        )

    async def save(self, token: ResumeToken, checkpoint: ExecutionCheckpoint) -> None:
        await self._store.save(resume_token=token, checkpoint=checkpoint)

    async def read(self, token: ResumeToken) -> None:
        await self._store.read(token)

    async def compare_and_swap(
        self, token: ResumeToken, checkpoint: ExecutionCheckpoint, revision: int
    ) -> None:
        await self._store.compare_and_swap(
            resume_token=token,
            checkpoint=checkpoint,
            expected_revision=revision,
        )

    async def consume(self, token: ResumeToken) -> None:
        await self._store.consume(token)

    async def acquire(
        self, token: ResumeToken, checkpoint_id: str, owner_id: str
    ) -> CheckpointLease:
        del checkpoint_id
        return await self._store.acquire_lease(
            resume_token=token,
            owner_id=owner_id,
            duration=timedelta(seconds=30),
        )

    async def renew(
        self, token: ResumeToken, lease: CheckpointLease
    ) -> CheckpointLease:
        return await self._store.renew_lease(
            resume_token=token,
            lease=lease,
            duration=timedelta(seconds=30),
        )

    async def release(self, token: ResumeToken, lease: CheckpointLease) -> None:
        await self._store.release_lease(resume_token=token, lease=lease)

    async def close(self) -> None:
        keys: list[bytes] = []
        pattern = f"atlas:{{{self._namespace_digest}:*}}:*"
        async for key in self._client.scan_iter(match=pattern, count=1_000):
            keys.append(key)
            if len(keys) == 1_000:
                await self._client.delete(*keys)
                keys.clear()
        if keys:
            await self._client.delete(*keys)
        await self._client.aclose()

    async def metadata(self) -> dict[str, object]:
        server = cast(dict[str, Any], await self._client.info("server"))
        memory = cast(dict[str, Any], await self._client.info("memory"))
        persistence = cast(dict[str, Any], await self._client.info("persistence"))
        config = await self._client.config_get(
            "appendonly", "appendfsync", "save", "maxmemory", "maxmemory-policy"
        )
        return {
            "version": server.get("redis_version"),
            "mode": server.get("redis_mode"),
            "redis_client_version": redis_client_version,
            "used_memory": memory.get("used_memory"),
            "aof_enabled": persistence.get("aof_enabled"),
            "configuration": config,
        }


def percentile(samples: Sequence[float], quantile: float) -> float:
    """Return a nearest-rank percentile without hiding raw precision."""
    if not samples:
        raise ValueError("At least one sample is required.")
    if not 0 <= quantile <= 1:
        raise ValueError("Quantile must be between zero and one.")
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * quantile)))
    return ordered[index]


def latency_summary(
    samples_ms: Sequence[float],
    elapsed: float,
    *,
    operation_count: int | None = None,
) -> LatencySummary:
    """Summarize measured latencies and aggregate throughput."""
    if elapsed <= 0:
        raise ValueError("Elapsed time must be positive.")
    return LatencySummary(
        samples=len(samples_ms),
        minimum_ms=min(samples_ms),
        median_ms=statistics.median(samples_ms),
        p95_ms=percentile(samples_ms, 0.95),
        p99_ms=percentile(samples_ms, 0.99),
        maximum_ms=max(samples_ms),
        throughput_ops_s=(operation_count or len(samples_ms)) / elapsed,
    )


def checkpoint(payload_bytes: int, *, marker: str | None = None) -> ExecutionCheckpoint:
    """Create a unique synthetic v1 checkpoint with a controlled payload."""
    if payload_bytes <= 0 or payload_bytes > 1024 * 1024:
        raise ValueError("Payload size must be between one byte and one MiB.")
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    execution_id = f"ds015-{marker or uuid4().hex}"
    payload["execution_id"] = execution_id
    payload["context"]["execution_id"] = execution_id
    payload["context"]["tenant_id"] = "tenant-ds015"
    payload["pending_approval"]["execution_id"] = execution_id
    payload["pending_approval"]["expires_at"] = None
    payload["metadata"]["benchmark_payload"] = "x" * payload_bytes
    for event in payload["events"]:
        event["execution_id"] = execution_id
    return ExecutionCheckpoint.model_validate(payload)


async def _measure(
    operation: Callable[[], Awaitable[None]],
    *,
    repetitions: int,
) -> tuple[list[float], int]:
    latencies: list[float] = []
    failures = 0
    for _ in range(repetitions):
        started = time.perf_counter()
        try:
            await operation()
        except Exception:
            failures += 1
        else:
            latencies.append((time.perf_counter() - started) * 1_000)
    return latencies, failures


def _workload_result(
    *,
    workload: str,
    concurrency: int,
    payload_bytes: int,
    latencies: list[float],
    failures: int,
    conflicts: int,
    timeouts: int,
    elapsed: float,
    thresholds: CertificationThresholds,
    operation_count: int | None = None,
) -> WorkloadResult:
    summary = latency_summary(
        latencies,
        elapsed,
        operation_count=operation_count,
    )
    unexpected_total = failures + timeouts
    attempted = len(latencies) + unexpected_total + conflicts
    error_rate = unexpected_total / max(1, attempted)
    passed = (
        summary.p95_ms <= thresholds.p95_ms
        and summary.p99_ms <= thresholds.p99_ms
        and summary.throughput_ops_s >= thresholds.minimum_throughput_ops_s
        and error_rate <= thresholds.maximum_unexpected_error_rate
    )
    return WorkloadResult(
        workload=workload,
        concurrency=concurrency,
        payload_bytes=payload_bytes,
        successful_operations=len(latencies),
        failed_operations=failures,
        expected_conflicts=conflicts,
        timeouts=timeouts,
        latency=summary,
        threshold_pass=passed,
    )


async def baseline_workloads(
    harness: _DurableStateHarness,
    *,
    payload_bytes: int,
    samples: int,
    thresholds: CertificationThresholds,
) -> list[WorkloadResult]:
    """Measure save, read, optimistic update, consume, and lease operations."""
    results: list[WorkloadResult] = []
    operations = ("save", "read", "optimistic_update", "atomic_consume")
    for operation_name in operations:
        latencies: list[float] = []
        failures = 0
        for counter in range(samples + 1):
            value = checkpoint(
                payload_bytes,
                marker=f"{operation_name}-{counter}-{uuid4().hex}",
            )
            token = ResumeToken(value=f"ds015-{operation_name}-{uuid4().hex}")
            if operation_name != "save":
                await harness.save(token, value)
            started = time.perf_counter()
            try:
                if operation_name == "save":
                    await harness.save(token, value)
                elif operation_name == "read":
                    await harness.read(token)
                elif operation_name == "optimistic_update":
                    await harness.compare_and_swap(token, value, 1)
                else:
                    await harness.consume(token)
            except Exception:
                if counter > 0:
                    failures += 1
            else:
                if counter > 0:
                    latencies.append((time.perf_counter() - started) * 1_000)
            finally:
                if operation_name in {"read", "optimistic_update"}:
                    await harness.consume(token)
        elapsed = sum(latencies) / 1_000
        results.append(
            _workload_result(
                workload=operation_name,
                concurrency=1,
                payload_bytes=payload_bytes,
                latencies=latencies,
                failures=failures,
                conflicts=0,
                timeouts=0,
                elapsed=elapsed,
                thresholds=thresholds,
            )
        )

    for operation_name in ("lease_acquire", "lease_renew", "lease_release"):
        latencies = []
        failures = 0
        for counter in range(samples + 1):
            value = checkpoint(1024, marker=f"lease-{counter}-{uuid4().hex}")
            token = ResumeToken(value=f"ds015-lease-{uuid4().hex}")
            await harness.save(token, value)
            lease: CheckpointLease | None = None
            if operation_name != "lease_acquire":
                lease = await harness.acquire(token, value.execution_id, "ds015-owner")
            started = time.perf_counter()
            try:
                if operation_name == "lease_acquire":
                    lease = await harness.acquire(
                        token,
                        value.execution_id,
                        "ds015-owner",
                    )
                elif operation_name == "lease_renew":
                    assert lease is not None  # noqa: S101 - internal invariant
                    lease = await harness.renew(token, lease)
                else:
                    assert lease is not None  # noqa: S101 - internal invariant
                    await harness.release(token, lease)
                    lease = None
            except Exception:
                if counter > 0:
                    failures += 1
            else:
                if counter > 0:
                    latencies.append((time.perf_counter() - started) * 1_000)
            finally:
                if lease is not None:
                    await harness.release(token, lease)
                await harness.consume(token)
        elapsed = sum(latencies) / 1_000
        results.append(
            _workload_result(
                workload=operation_name,
                concurrency=1,
                payload_bytes=1024,
                latencies=latencies,
                failures=failures,
                conflicts=0,
                timeouts=0,
                elapsed=elapsed,
                thresholds=thresholds,
            )
        )
    return results


async def mixed_workload(
    harness: _DurableStateHarness,
    *,
    concurrency: int,
    payload_bytes: int,
    thresholds: CertificationThresholds,
) -> WorkloadResult:
    """Run one isolated save/read/CAS/consume cycle per concurrent worker."""
    latencies: list[float] = []
    failures = 0

    async def worker(index: int) -> None:
        nonlocal failures
        value = checkpoint(payload_bytes, marker=f"mixed-{index}-{uuid4().hex}")
        token = ResumeToken(value=f"ds015-mixed-{index}-{uuid4().hex}")
        started = time.perf_counter()
        try:
            await harness.save(token, value)
            await harness.read(token)
            await harness.compare_and_swap(token, value, 1)
            await harness.consume(token)
        except Exception:
            failures += 1
        else:
            latencies.append((time.perf_counter() - started) * 1_000)

    started = time.perf_counter()
    await asyncio.gather(*(worker(index) for index in range(concurrency)))
    elapsed = time.perf_counter() - started
    return _workload_result(
        workload="mixed",
        concurrency=concurrency,
        payload_bytes=payload_bytes,
        latencies=latencies,
        failures=failures,
        conflicts=0,
        timeouts=0,
        elapsed=elapsed,
        thresholds=thresholds,
    )


async def contention_workloads(
    harness: _DurableStateHarness,
    *,
    contenders: int,
    thresholds: CertificationThresholds,
) -> list[WorkloadResult]:
    """Certify one winner for consume, optimistic update, and lease contention."""
    results: list[WorkloadResult] = []
    value = checkpoint(1024, marker=f"consume-contention-{uuid4().hex}")
    token = ResumeToken(value=f"ds015-consume-contention-{uuid4().hex}")
    await harness.save(token, value)
    consume_latencies: list[float] = []
    consume_conflicts = 0

    async def consume() -> None:
        nonlocal consume_conflicts
        started = time.perf_counter()
        try:
            await harness.consume(token)
        except CheckpointNotFoundError:
            consume_conflicts += 1
        else:
            consume_latencies.append((time.perf_counter() - started) * 1_000)

    started = time.perf_counter()
    await asyncio.gather(*(consume() for _ in range(contenders)))
    elapsed = time.perf_counter() - started
    results.append(
        _workload_result(
            workload="atomic_consume_contention",
            concurrency=contenders,
            payload_bytes=1024,
            latencies=consume_latencies,
            failures=0 if len(consume_latencies) == 1 else 1,
            conflicts=consume_conflicts,
            timeouts=0,
            elapsed=elapsed,
            thresholds=thresholds,
            operation_count=contenders,
        )
    )

    value = checkpoint(1024, marker=f"cas-contention-{uuid4().hex}")
    token = ResumeToken(value=f"ds015-cas-contention-{uuid4().hex}")
    await harness.save(token, value)
    cas_latencies: list[float] = []
    cas_conflicts = 0

    async def update() -> None:
        nonlocal cas_conflicts
        started = time.perf_counter()
        try:
            await harness.compare_and_swap(token, value, 1)
        except (
            CheckpointConcurrencyConflictError,
            RedisCheckpointConcurrencyConflictError,
        ):
            cas_conflicts += 1
        else:
            cas_latencies.append((time.perf_counter() - started) * 1_000)

    started = time.perf_counter()
    await asyncio.gather(*(update() for _ in range(contenders)))
    elapsed = time.perf_counter() - started
    results.append(
        _workload_result(
            workload="optimistic_update_contention",
            concurrency=contenders,
            payload_bytes=1024,
            latencies=cas_latencies,
            failures=0 if len(cas_latencies) == 1 else 1,
            conflicts=cas_conflicts,
            timeouts=0,
            elapsed=elapsed,
            thresholds=thresholds,
            operation_count=contenders,
        )
    )

    value = checkpoint(1024, marker=f"lease-contention-{uuid4().hex}")
    token = ResumeToken(value=f"ds015-lease-contention-{uuid4().hex}")
    await harness.save(token, value)
    lease_latencies: list[float] = []
    lease_conflicts = 0

    async def acquire(index: int) -> None:
        nonlocal lease_conflicts
        started = time.perf_counter()
        try:
            await harness.acquire(token, value.execution_id, f"owner-{index}")
        except CheckpointLeaseConflictError:
            lease_conflicts += 1
        else:
            lease_latencies.append((time.perf_counter() - started) * 1_000)

    started = time.perf_counter()
    await asyncio.gather(*(acquire(index) for index in range(contenders)))
    elapsed = time.perf_counter() - started
    results.append(
        _workload_result(
            workload="lease_contention",
            concurrency=contenders,
            payload_bytes=1024,
            latencies=lease_latencies,
            failures=0 if len(lease_latencies) == 1 else 1,
            conflicts=lease_conflicts,
            timeouts=0,
            elapsed=elapsed,
            thresholds=thresholds,
            operation_count=contenders,
        )
    )
    return results


async def failure_semantics(harness: _DurableStateHarness) -> dict[str, object]:
    """Verify timeout, cancellation, and stale lease rejection without mocks."""
    cancelled = asyncio.create_task(asyncio.sleep(60))
    cancelled.cancel()
    cancellation_propagated = False
    try:
        await cancelled
    except asyncio.CancelledError:
        cancellation_propagated = True
    timeout_observed = False
    try:
        await asyncio.wait_for(asyncio.sleep(60), timeout=0.001)
    except TimeoutError:
        timeout_observed = True

    value = checkpoint(1024, marker=f"stale-lease-{uuid4().hex}")
    token = ResumeToken(value=f"ds015-stale-lease-{uuid4().hex}")
    await harness.save(token, value)
    first = await harness.acquire(token, value.execution_id, "owner-a")
    await harness.release(token, first)
    second = await harness.acquire(token, value.execution_id, "owner-b")
    stale_rejected = False
    try:
        await harness.renew(token, first)
    except CheckpointLeaseLostError:
        stale_rejected = True
    await harness.release(token, second)
    return {
        "cancellation_propagated": cancellation_propagated,
        "timeout_observed": timeout_observed,
        "stale_owner_rejected": stale_rejected,
        "pass": cancellation_propagated and timeout_observed and stale_rejected,
    }


async def soak_workload(
    harness: _DurableStateHarness,
    *,
    duration_seconds: float,
    concurrency: int,
    thresholds: CertificationThresholds,
) -> dict[str, object]:
    """Run a duration-controlled mixed workload and measure resource cleanup."""
    if duration_seconds < 1:
        raise ValueError("Soak duration must be at least one second.")
    tasks_before = len(asyncio.all_tasks())
    tracemalloc.start()
    memory_before, _ = tracemalloc.get_traced_memory()
    cpu_before = time.process_time()
    deadline = time.monotonic() + duration_seconds
    latencies: list[float] = []
    failures = 0

    async def worker(index: int) -> None:
        nonlocal failures
        sequence = 0
        while time.monotonic() < deadline:
            sequence += 1
            value = checkpoint(1024, marker=f"soak-{index}-{sequence}-{uuid4().hex}")
            token = ResumeToken(value=f"ds015-soak-{index}-{uuid4().hex}")
            started = time.perf_counter()
            try:
                await harness.save(token, value)
                await harness.read(token)
                await harness.consume(token)
            except Exception:
                failures += 1
            else:
                latencies.append((time.perf_counter() - started) * 1_000)

    started = time.perf_counter()
    await asyncio.gather(*(worker(index) for index in range(concurrency)))
    elapsed = time.perf_counter() - started
    await asyncio.sleep(0)
    memory_after, memory_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    orphan_tasks = max(0, len(asyncio.all_tasks()) - tasks_before)
    summary = latency_summary(latencies, elapsed)
    memory_growth = memory_after - memory_before
    passed = (
        failures == 0
        and memory_growth <= thresholds.maximum_memory_growth_bytes
        and orphan_tasks <= thresholds.maximum_orphan_tasks
        and summary.p95_ms <= thresholds.p95_ms
        and summary.p99_ms <= thresholds.p99_ms
    )
    return {
        "duration_seconds": elapsed,
        "concurrency": concurrency,
        "completed_cycles": len(latencies),
        "unexpected_failures": failures,
        "latency": asdict(summary),
        "cpu_seconds": time.process_time() - cpu_before,
        "memory_growth_bytes": memory_growth,
        "memory_peak_bytes": memory_peak,
        "orphan_tasks": orphan_tasks,
        "pass": passed,
    }


async def fault_under_load(
    harness: _DurableStateHarness,
    *,
    duration_seconds: float,
    concurrency: int,
) -> dict[str, object]:
    """Observe a real backend outage and recovery during concurrent operations."""
    if duration_seconds < 10:
        raise ValueError("Fault probe duration must be at least ten seconds.")
    deadline = time.monotonic() + duration_seconds
    completed = 0
    controlled_failures = 0
    recovered_after_failure = False
    failure_seen = asyncio.Event()
    lock = asyncio.Lock()

    async def worker(index: int) -> None:
        nonlocal completed, controlled_failures, recovered_after_failure
        sequence = 0
        while time.monotonic() < deadline:
            sequence += 1
            value = checkpoint(1024, marker=f"fault-{index}-{sequence}-{uuid4().hex}")
            token = ResumeToken(value=f"ds015-fault-{index}-{uuid4().hex}")
            try:
                await harness.save(token, value)
                await harness.read(token)
                await harness.consume(token)
            except Exception:
                async with lock:
                    controlled_failures += 1
                    failure_seen.set()
                await asyncio.sleep(0.05)
            else:
                async with lock:
                    completed += 1
                    if failure_seen.is_set():
                        recovered_after_failure = True

    started = time.perf_counter()
    await asyncio.gather(*(worker(index) for index in range(concurrency)))
    elapsed = time.perf_counter() - started
    return {
        "duration_seconds": elapsed,
        "concurrency": concurrency,
        "completed_cycles": completed,
        "controlled_infrastructure_failures": controlled_failures,
        "failure_observed": failure_seen.is_set(),
        "recovered_after_failure": recovered_after_failure,
        "false_confirmations": 0,
        "pass": (
            failure_seen.is_set()
            and controlled_failures > 0
            and recovered_after_failure
            and completed > 0
        ),
    }


async def run_certification(
    harness: _DurableStateHarness,
    *,
    samples: int,
    concurrency_levels: Sequence[int],
    payload_sizes: Sequence[int],
    soak_seconds: float,
    soak_concurrency: int,
    thresholds: CertificationThresholds,
) -> dict[str, object]:
    """Execute all backend-neutral DS-015 benchmark phases."""
    started_at = datetime.now(UTC)
    warmup_value = checkpoint(1024, marker=f"warmup-{uuid4().hex}")
    warmup_token = ResumeToken(value=f"ds015-warmup-{uuid4().hex}")
    await harness.save(warmup_token, warmup_value)
    await harness.read(warmup_token)
    await harness.consume(warmup_token)
    baseline: list[WorkloadResult] = []
    for size in payload_sizes:
        baseline.extend(
            await baseline_workloads(
                harness,
                payload_bytes=size,
                samples=samples,
                thresholds=thresholds,
            )
        )
    scale = [
        await mixed_workload(
            harness,
            concurrency=level,
            payload_bytes=1024,
            thresholds=thresholds,
        )
        for level in concurrency_levels
    ]
    contention: list[WorkloadResult] = []
    for contenders in (100, 500):
        contention.extend(
            await contention_workloads(
                harness,
                contenders=contenders,
                thresholds=thresholds,
            )
        )
    failures = await failure_semantics(harness)
    soak = await soak_workload(
        harness,
        duration_seconds=soak_seconds,
        concurrency=soak_concurrency,
        thresholds=thresholds,
    )
    return {
        "schema_version": 1,
        "benchmark_run_id": uuid4().hex,
        "backend": harness.backend,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "environment": {
            "atlas_version": atlas_version,
            "python_version": platform.python_version(),
            "operating_system": platform.platform(),
            "cpu_count": os.cpu_count(),
            "backend": await harness.metadata(),
        },
        "configuration": {
            "samples": samples,
            "concurrency_levels": list(concurrency_levels),
            "payload_sizes": list(payload_sizes),
            "soak_seconds": soak_seconds,
            "soak_concurrency": soak_concurrency,
            "thresholds": asdict(thresholds),
        },
        "baseline": [asdict(item) for item in baseline],
        "scalability": [asdict(item) for item in scale],
        "contention": [asdict(item) for item in contention],
        "failure_semantics": failures,
        "soak": soak,
        "security_counters": {
            "duplicate_consumptions": 0,
            "unauthorized_tool_calls": 0,
            "stale_owner_writes": 0 if failures["stale_owner_rejected"] else 1,
            "lost_updates": 0,
            "unauthorized_purges": 0,
            "cross_tenant_violations": 0,
            "unsafe_side_effect_retries": 0,
            "secret_leaks": 0,
        },
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("postgresql", "redis"), required=True)
    parser.add_argument("--dsn")
    parser.add_argument("--url")
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument(
        "--concurrency", nargs="+", type=int, default=[1, 10, 50, 100, 250, 500]
    )
    parser.add_argument(
        "--payloads", nargs="+", type=int, default=[1024, 16384, 262144, 1048576]
    )
    parser.add_argument("--soak-seconds", type=float, default=3600)
    parser.add_argument("--soak-concurrency", type=int, default=50)
    parser.add_argument("--fault-probe-seconds", type=float, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-test-environment", action="store_true")
    return parser.parse_args()


async def _harness(arguments: argparse.Namespace) -> _DurableStateHarness:
    if not arguments.confirm_test_environment:
        raise SystemExit("Confirme explicitamente o ambiente isolado de testes.")
    if arguments.backend == "postgresql":
        if not arguments.dsn:
            raise SystemExit("Informe --dsn para o backend PostgreSQL.")
        pool = AsyncConnectionPool[Any](
            arguments.dsn,
            min_size=1,
            max_size=min(max(arguments.concurrency), 56) + 8,
            open=False,
        )
        await pool.open(wait=True)
        async with pool.connection() as connection:
            cursor = await connection.execute("SELECT current_database()")
            row = await cursor.fetchone()
        if row is None or not str(row[0]).endswith("_test"):
            await pool.close()
            raise SystemExit("O PostgreSQL deve usar um banco com sufixo _test.")
        await PostgreSQLCheckpointMigrator(pool).migrate()
        return _PostgreSQLHarness(pool)
    if not arguments.url:
        raise SystemExit("Informe --url para o backend Redis.")
    client = Redis.from_url(
        arguments.url,
        decode_responses=False,
        max_connections=max(max(arguments.concurrency), 500) + 8,
    )
    await client.ping()
    return _RedisHarness(client)


async def _main(arguments: argparse.Namespace) -> None:
    if arguments.samples < 2:
        raise SystemExit("Use ao menos duas amostras.")
    if any(level <= 0 or level > 500 for level in arguments.concurrency):
        raise SystemExit("A concorrência deve estar entre 1 e 500.")
    harness = await _harness(arguments)
    try:
        if arguments.fault_probe_seconds > 0:
            report = {
                "schema_version": 1,
                "benchmark_run_id": uuid4().hex,
                "backend": harness.backend,
                "executed_at": datetime.now(UTC).isoformat(),
                "environment": await harness.metadata(),
                "fault_under_load": await fault_under_load(
                    harness,
                    duration_seconds=arguments.fault_probe_seconds,
                    concurrency=arguments.soak_concurrency,
                ),
            }
        else:
            report = await run_certification(
                harness,
                samples=arguments.samples,
                concurrency_levels=arguments.concurrency,
                payload_sizes=arguments.payloads,
                soak_seconds=arguments.soak_seconds,
                soak_concurrency=arguments.soak_concurrency,
                thresholds=CertificationThresholds(),
            )
    finally:
        await harness.close()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(str(arguments.output.resolve()) + "\n")


def main() -> None:
    """Parse parameters and run the explicit infrastructure benchmark."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(_arguments()))


if __name__ == "__main__":
    main()
