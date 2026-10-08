from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError

from atlas_agents import (
    CheckpointPurgeConfig,
    CheckpointPurgeCoordinator,
    ObservabilityManager,
    PurgeAuthorization,
    PurgeBatchResult,
    PurgeItemResult,
    PurgeOutcome,
)


def item(
    operation_id: str, outcome: PurgeOutcome = PurgeOutcome.PURGED
) -> PurgeItemResult:
    return PurgeItemResult(
        operation_id=operation_id,
        checkpoint_id=f"checkpoint-{operation_id}",
        execution_id=f"execution-{operation_id}",
        outcome=outcome,
        reason_code="retention_elapsed",
        policy_version="ds008-v1",
    )


def batch(run_id: str, *results: PurgeItemResult) -> PurgeBatchResult:
    return PurgeBatchResult(
        purge_run_id=run_id,
        discovered=len(results),
        purged=sum(value.outcome is PurgeOutcome.PURGED for value in results),
        skipped=sum(value.outcome is PurgeOutcome.SKIPPED for value in results),
        blocked=sum(value.outcome is PurgeOutcome.BLOCKED for value in results),
        failed=sum(value.outcome is PurgeOutcome.FAILED for value in results),
        outcome_unknown=sum(
            value.outcome is PurgeOutcome.OUTCOME_UNKNOWN for value in results
        ),
        results=results,
    )


class Repository:
    def __init__(self, responses: list[tuple[PurgeItemResult, ...]]) -> None:
        self.responses = responses
        self.calls = 0
        self.run_ids: list[str] = []

    async def purge_batch(
        self,
        *,
        purge_run_id: str,
        authorization: PurgeAuthorization,
        config: CheckpointPurgeConfig,
    ) -> PurgeBatchResult:
        del authorization, config
        self.run_ids.append(purge_run_id)
        response = self.responses[self.calls]
        self.calls += 1
        return batch(purge_run_id, *response)


class CancelledRepository(Repository):
    async def purge_batch(
        self,
        *,
        purge_run_id: str,
        authorization: PurgeAuthorization,
        config: CheckpointPurgeConfig,
    ) -> PurgeBatchResult:
        del purge_run_id, authorization, config
        raise asyncio.CancelledError


class BrokenMetrics:
    def increment(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("metrics unavailable")

    def record(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("metrics unavailable")


async def test_empty_purge_run_returns_a_valid_result() -> None:
    result = await CheckpointPurgeCoordinator(Repository([()])).purge_once(
        authorization=PurgeAuthorization(principal_id="maintenance-worker")
    )
    assert result.discovered == 0
    assert result.results == ()


async def test_coordinator_aggregates_only_bounded_batches() -> None:
    repository = Repository(
        [
            (item("1"), item("2")),
            (item("3", PurgeOutcome.BLOCKED),),
        ]
    )
    result = await CheckpointPurgeCoordinator(repository).purge_once(
        authorization=PurgeAuthorization(principal_id="maintenance-worker"),
        config=CheckpointPurgeConfig(
            batch_size=2, max_batches_per_run=2, dry_run=False
        ),
    )
    assert result.discovered == 3
    assert result.purged == 2
    assert result.blocked == 1
    assert repository.calls == 2
    assert len(set(repository.run_ids)) == 1


async def test_dry_run_never_repeats_the_same_candidates() -> None:
    repository = Repository([tuple(item(str(index)) for index in range(2))])
    await CheckpointPurgeCoordinator(repository).purge_once(
        authorization=PurgeAuthorization(principal_id="maintenance-worker"),
        config=CheckpointPurgeConfig(batch_size=2, max_batches_per_run=10),
    )
    assert repository.calls == 1


async def test_cancellation_is_propagated() -> None:
    coordinator = CheckpointPurgeCoordinator(CancelledRepository([]))
    with pytest.raises(asyncio.CancelledError):
        await coordinator.purge_once(
            authorization=PurgeAuthorization(principal_id="maintenance-worker")
        )


async def test_observability_failure_does_not_change_functional_result() -> None:
    result = await CheckpointPurgeCoordinator(
        Repository([()]),
        observability=ObservabilityManager(metrics=BrokenMetrics()),
    ).purge_once(authorization=PurgeAuthorization(principal_id="maintenance-worker"))
    assert result.discovered == 0


def test_destructive_permission_is_explicit() -> None:
    with pytest.raises(ValidationError):
        PurgeAuthorization(principal_id="worker", permission="checkpoint:read")


def test_configuration_is_bounded_and_positive() -> None:
    with pytest.raises(ValidationError):
        CheckpointPurgeConfig(batch_size=0)
    with pytest.raises(ValidationError):
        CheckpointPurgeConfig(batch_size=1_001)
    with pytest.raises(ValidationError):
        CheckpointPurgeConfig(statement_timeout=timedelta(0))


def test_batch_rejects_inconsistent_totals() -> None:
    with pytest.raises(ValidationError):
        PurgeBatchResult(
            purge_run_id="run",
            discovered=1,
            purged=0,
            skipped=0,
            blocked=0,
            failed=0,
            outcome_unknown=0,
            results=(item("1"),),
        )


def test_unknown_commit_is_a_first_class_outcome() -> None:
    result = batch("run", item("1", PurgeOutcome.OUTCOME_UNKNOWN))
    assert result.outcome_unknown == 1
    assert result.purged == 0
