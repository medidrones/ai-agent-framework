"""Safe public errors for the PostgreSQL checkpoint adapter."""

from atlas_agents.approvals import CheckpointError


class PostgreSQLCheckpointStoreError(CheckpointError):
    """Report an unavailable or failed PostgreSQL checkpoint operation."""


class PostgreSQLMigrationError(PostgreSQLCheckpointStoreError):
    """Report a migration that could not be validated or applied."""


class CheckpointConcurrencyConflictError(PostgreSQLCheckpointStoreError):
    """Report a failed checkpoint compare-and-swap operation."""

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
