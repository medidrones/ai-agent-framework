from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from atlas_kubernetes_recovery.performance_certifier import (
    CertificationThresholds,
    baseline_workloads,
    checkpoint,
    contention_workloads,
    failure_semantics,
    fault_under_load,
    latency_summary,
    mixed_workload,
    percentile,
    soak_workload,
)

from atlas_agents import (
    CheckpointLease,
    CheckpointLeaseConflictError,
    CheckpointLeaseLostError,
    CheckpointNotFoundError,
    ExecutionCheckpoint,
    ResumeToken,
)
from atlas_agents.adapters.checkpoints.postgresql import (
    CheckpointConcurrencyConflictError,
)


class FakeHarness:
    backend = "fake"

    def __init__(self) -> None:
        self.values: dict[str, tuple[ExecutionCheckpoint, int]] = {}
        self.leases: dict[str, CheckpointLease] = {}
        self.fencing = 0

    async def save(self, token: ResumeToken, checkpoint: ExecutionCheckpoint) -> None:
        self.values[token.value] = (checkpoint, 1)

    async def read(self, token: ResumeToken) -> None:
        if token.value not in self.values:
            raise CheckpointNotFoundError("missing")

    async def compare_and_swap(
        self, token: ResumeToken, checkpoint: ExecutionCheckpoint, revision: int
    ) -> None:
        current = self.values.get(token.value)
        if current is None:
            raise CheckpointNotFoundError("missing")
        if current[1] != revision:
            raise CheckpointConcurrencyConflictError(
                checkpoint_id=checkpoint.execution_id,
                expected_revision=revision,
                actual_revision=current[1],
            )
        self.values[token.value] = (checkpoint, revision + 1)

    async def consume(self, token: ResumeToken) -> None:
        if self.values.pop(token.value, None) is None:
            raise CheckpointNotFoundError("missing")

    async def acquire(
        self, token: ResumeToken, checkpoint_id: str, owner_id: str
    ) -> CheckpointLease:
        del token
        active = self.leases.get(checkpoint_id)
        if active is not None:
            raise CheckpointLeaseConflictError("active")
        self.fencing += 1
        now = datetime.now(UTC)
        lease = CheckpointLease(
            checkpoint_id=checkpoint_id,
            owner_id=owner_id,
            fencing_token=self.fencing,
            acquired_at=now,
            expires_at=now + timedelta(seconds=30),
        )
        self.leases[checkpoint_id] = lease
        return lease

    async def renew(
        self, token: ResumeToken, lease: CheckpointLease
    ) -> CheckpointLease:
        del token
        if self.leases.get(lease.checkpoint_id) != lease:
            raise CheckpointLeaseLostError("stale")
        renewed = lease.model_copy(
            update={"expires_at": datetime.now(UTC) + timedelta(seconds=30)}
        )
        self.leases[lease.checkpoint_id] = renewed
        return renewed

    async def release(self, token: ResumeToken, lease: CheckpointLease) -> None:
        del token
        if self.leases.get(lease.checkpoint_id) != lease:
            raise CheckpointLeaseLostError("stale")
        del self.leases[lease.checkpoint_id]

    async def close(self) -> None:
        return None

    async def metadata(self) -> dict[str, object]:
        return {"fake": True}


def test_percentile_and_summary_use_real_samples() -> None:
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(samples, 0.50) == 3.0
    assert percentile(samples, 0.95) == 5.0
    result = latency_summary(samples, elapsed=0.5)
    assert result.samples == 5
    assert result.median_ms == 3.0
    assert result.p99_ms == 5.0
    assert result.throughput_ops_s == 10.0


@pytest.mark.parametrize("quantile", [-0.1, 1.1])
def test_percentile_rejects_invalid_quantile(quantile: float) -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        percentile([1.0], quantile)


def test_checkpoint_has_unique_identity_and_controlled_payload() -> None:
    value = checkpoint(1024, marker="fixture")
    assert value.execution_id == "ds015-fixture"
    assert value.context.execution_id == "ds015-fixture"
    assert value.context.tenant_id == "tenant-ds015"
    assert len(value.metadata["benchmark_payload"]) == 1024


@pytest.mark.parametrize("payload_bytes", [0, 1024 * 1024 + 1])
def test_checkpoint_rejects_unsupported_payload(payload_bytes: int) -> None:
    with pytest.raises(ValueError, match="between one byte and one MiB"):
        checkpoint(payload_bytes)


async def test_fake_harness_covers_baseline_and_scalability() -> None:
    harness = FakeHarness()
    thresholds = CertificationThresholds(
        p95_ms=10_000,
        p99_ms=10_000,
        minimum_throughput_ops_s=0.01,
    )
    baseline = await baseline_workloads(
        harness,
        payload_bytes=1024,
        samples=2,
        thresholds=thresholds,
    )
    mixed = await mixed_workload(
        harness,
        concurrency=10,
        payload_bytes=1024,
        thresholds=thresholds,
    )
    assert len(baseline) == 7
    assert all(result.failed_operations == 0 for result in baseline)
    assert mixed.successful_operations == 10
    assert mixed.threshold_pass


async def test_contention_has_one_winner_for_each_primitive() -> None:
    results = await contention_workloads(
        FakeHarness(),
        contenders=100,
        thresholds=CertificationThresholds(
            p95_ms=10_000,
            p99_ms=10_000,
            minimum_throughput_ops_s=0.01,
        ),
    )
    assert len(results) == 3
    assert all(result.successful_operations == 1 for result in results)
    assert all(result.expected_conflicts == 99 for result in results)


async def test_failure_semantics_reject_stale_owner() -> None:
    result = await failure_semantics(FakeHarness())
    assert result == {
        "cancellation_propagated": True,
        "timeout_observed": True,
        "stale_owner_rejected": True,
        "pass": True,
    }


async def test_short_soak_cleans_tasks_and_preserves_integrity() -> None:
    result = await soak_workload(
        FakeHarness(),
        duration_seconds=1,
        concurrency=2,
        thresholds=CertificationThresholds(
            p95_ms=10_000,
            p99_ms=10_000,
            minimum_throughput_ops_s=0.01,
        ),
    )
    assert result["completed_cycles"] > 0
    assert result["unexpected_failures"] == 0
    assert result["orphan_tasks"] == 0
    assert result["pass"] is True


async def test_cancelled_measurement_does_not_leave_background_work() -> None:
    harness = FakeHarness()
    task = asyncio.create_task(
        soak_workload(
            harness,
            duration_seconds=60,
            concurrency=1,
            thresholds=CertificationThresholds(),
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_fault_probe_requires_a_real_observed_failure() -> None:
    result = await fault_under_load(
        FakeHarness(),
        duration_seconds=10,
        concurrency=2,
    )
    assert result["completed_cycles"] > 0
    assert result["controlled_infrastructure_failures"] == 0
    assert result["false_confirmations"] == 0
    assert result["pass"] is False
