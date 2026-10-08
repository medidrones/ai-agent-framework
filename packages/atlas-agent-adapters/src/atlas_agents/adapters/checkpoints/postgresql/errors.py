"""Safe public errors for the PostgreSQL checkpoint adapter."""

from atlas_agents.approvals import CheckpointError


class PostgreSQLCheckpointStoreError(CheckpointError):
    """Report an unavailable or failed PostgreSQL checkpoint operation."""


class PostgreSQLMigrationError(PostgreSQLCheckpointStoreError):
    """Report a migration that could not be validated or applied."""
