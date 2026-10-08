"""Safe public errors for the Redis checkpoint adapter."""

from atlas_agents.approvals import CheckpointError


class RedisCheckpointStoreError(CheckpointError):
    """Report an unavailable or failed Redis checkpoint operation."""


class RedisCheckpointConcurrencyConflictError(RedisCheckpointStoreError):
    """Report a failed Redis checkpoint compare-and-swap operation."""

    error_code = "checkpoint_concurrency_conflict"

    def __init__(
        self,
        *,
        checkpoint_id: str,
        expected_revision: int,
        actual_revision: int,
    ) -> None:
        """Expose only safe conflict facts without token or payload data."""
        super().__init__("O checkpoint foi alterado por outro consumidor ou writer.")
        self.checkpoint_id = checkpoint_id
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision


class RedisCheckpointOutcomeUnknownError(RedisCheckpointStoreError):
    """Report an operation whose durable outcome cannot be inferred safely."""

    error_code = "checkpoint_outcome_unknown"
