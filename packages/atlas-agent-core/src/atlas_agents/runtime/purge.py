"""Provider-neutral contracts for authorized checkpoint purge operations."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
from typing import Protocol, Self
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from atlas_agents._models import _FrozenModel, _non_empty
from atlas_agents.observability import ObservabilityManager, SpanStatus


class PurgeOutcome(StrEnum):
    """Describe the durable result of processing one purge candidate."""

    PURGED = "purged"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class PurgeAuthorization(_FrozenModel):
    """Carry an explicit host-authorized scope for a destructive operation."""

    principal_id: str
    tenant_id: str | None = None
    permission: str = "checkpoint:purge"

    @field_validator("principal_id", "permission")
    @classmethod
    def validate_strings(cls, value: str) -> str:
        """Reject missing authorization facts."""
        return _non_empty(value)

    @model_validator(mode="after")
    def validate_permission(self) -> Self:
        """Require the dedicated destructive permission."""
        if self.permission != "checkpoint:purge":
            raise ValueError("A autorização não permite executar purge de checkpoints")
        return self


class CheckpointPurgeConfig(_FrozenModel):
    """Bound one incremental purge run without scheduling it automatically."""

    batch_size: int = Field(default=100, gt=0, le=1_000)
    max_batches_per_run: int = Field(default=1, gt=0, le=100)
    statement_timeout: timedelta = timedelta(seconds=30)
    lock_timeout: timedelta = timedelta(seconds=5)
    dry_run: bool = True

    @field_validator("statement_timeout", "lock_timeout")
    @classmethod
    def validate_timeout(cls, value: timedelta) -> timedelta:
        """Reject non-positive database timeouts."""
        if value <= timedelta(0):
            raise ValueError("O timeout do purge deve ser positivo")
        return value


class PurgeItemResult(_FrozenModel):
    """Report one candidate outcome without exposing checkpoint payloads."""

    operation_id: str
    checkpoint_id: str
    execution_id: str
    outcome: PurgeOutcome
    reason_code: str
    policy_version: str
    tenant_id: str | None = None

    @field_validator(
        "operation_id",
        "checkpoint_id",
        "execution_id",
        "reason_code",
        "policy_version",
    )
    @classmethod
    def validate_strings(cls, value: str) -> str:
        """Reject incomplete audit facts."""
        return _non_empty(value)


class PurgeBatchResult(_FrozenModel):
    """Summarize one committed or reconciled bounded batch."""

    purge_run_id: str
    discovered: int = Field(ge=0)
    purged: int = Field(ge=0)
    skipped: int = Field(ge=0)
    blocked: int = Field(ge=0)
    failed: int = Field(ge=0)
    outcome_unknown: int = Field(ge=0)
    results: tuple[PurgeItemResult, ...] = ()

    @field_validator("purge_run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        """Reject an empty run identifier."""
        return _non_empty(value)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Require exactly one counted result per discovered candidate."""
        counts = {
            PurgeOutcome.PURGED: self.purged,
            PurgeOutcome.SKIPPED: self.skipped,
            PurgeOutcome.BLOCKED: self.blocked,
            PurgeOutcome.FAILED: self.failed,
            PurgeOutcome.OUTCOME_UNKNOWN: self.outcome_unknown,
        }
        actual = dict.fromkeys(PurgeOutcome, 0)
        for result in self.results:
            actual[result.outcome] += 1
        if self.discovered != len(self.results) or counts != actual:
            raise ValueError("Os totais do purge não correspondem aos resultados")
        return self


class CheckpointPurgeRepository(Protocol):
    """Execute one database-authoritative purge batch."""

    async def purge_batch(
        self,
        *,
        purge_run_id: str,
        authorization: PurgeAuthorization,
        config: CheckpointPurgeConfig,
    ) -> PurgeBatchResult:
        """Process at most one configured batch and return durable outcomes."""
        ...


class CheckpointPurgeCoordinator:
    """Coordinate explicitly authorized, bounded purge batches."""

    def __init__(
        self,
        repository: CheckpointPurgeRepository,
        *,
        observability: ObservabilityManager | None = None,
    ) -> None:
        """Use injected persistence and fail-open observability adapters."""
        self._repository = repository
        self._observability = observability or ObservabilityManager()

    async def purge_once(
        self,
        *,
        authorization: PurgeAuthorization,
        config: CheckpointPurgeConfig | None = None,
    ) -> PurgeBatchResult:
        """Execute a bounded run and stop when no further batch can progress."""
        effective_config = config or CheckpointPurgeConfig()
        purge_run_id = str(uuid4())
        span = self._observability.start_span(
            "checkpoint.purge",
            attributes={
                "atlas.purge.dry_run": effective_config.dry_run,
                "atlas.purge.batch_size": effective_config.batch_size,
            },
        )
        started_at = self._observability.now()
        batches: list[PurgeBatchResult] = []
        try:
            span.add_event("checkpoint.purge.started")
            for _ in range(effective_config.max_batches_per_run):
                batch = await self._repository.purge_batch(
                    purge_run_id=purge_run_id,
                    authorization=authorization,
                    config=effective_config,
                )
                batches.append(batch)
                if (
                    effective_config.dry_run
                    or batch.discovered < effective_config.batch_size
                ):
                    break
            result = self._aggregate(purge_run_id, batches)
            span.add_event(
                "checkpoint.purge.completed",
                {"atlas.purge.deleted": result.purged},
            )
            self._record_metrics(result, started_at)
            span.set_status(SpanStatus.OK)
            return result
        except BaseException as error:
            span.add_event("checkpoint.purge.failed")
            span.record_exception(error)
            span.set_status(SpanStatus.ERROR)
            self._observability.increment("atlas.checkpoint.purge.failed")
            raise
        finally:
            span.end()

    @staticmethod
    def _aggregate(
        purge_run_id: str, batches: list[PurgeBatchResult]
    ) -> PurgeBatchResult:
        results = tuple(item for batch in batches for item in batch.results)
        return PurgeBatchResult(
            purge_run_id=purge_run_id,
            discovered=len(results),
            purged=sum(item.outcome is PurgeOutcome.PURGED for item in results),
            skipped=sum(item.outcome is PurgeOutcome.SKIPPED for item in results),
            blocked=sum(item.outcome is PurgeOutcome.BLOCKED for item in results),
            failed=sum(item.outcome is PurgeOutcome.FAILED for item in results),
            outcome_unknown=sum(
                item.outcome is PurgeOutcome.OUTCOME_UNKNOWN for item in results
            ),
            results=results,
        )

    def _record_metrics(self, result: PurgeBatchResult, started_at: float) -> None:
        self._observability.increment("atlas.checkpoint.purge.runs")
        self._observability.increment(
            "atlas.checkpoint.purge.candidates", result.discovered
        )
        self._observability.increment("atlas.checkpoint.purge.deleted", result.purged)
        self._observability.increment("atlas.checkpoint.purge.blocked", result.blocked)
        self._observability.increment("atlas.checkpoint.purge.failed", result.failed)
        self._observability.record(
            "atlas.checkpoint.purge.duration",
            self._observability.elapsed_since(started_at),
        )
