"""Safe errors for approval and checkpoint operations."""

from atlas_agents.exceptions import AtlasAgentError


class ApprovalError(AtlasAgentError):
    """Base error for human approval contracts."""


class ApprovalDecisionValidationError(ApprovalError):
    """Report a decision rejected by the configured validator."""


class ApprovalDecisionMismatchError(ApprovalDecisionValidationError):
    """Report a decision targeting a different approval request."""


class CheckpointError(AtlasAgentError):
    """Base error for checkpoint persistence and restoration."""


class CheckpointStoreRequiredError(CheckpointError):
    """Report approval use without an explicitly injected checkpoint store."""


class CheckpointNotFoundError(CheckpointError):
    """Report an unknown or already consumed resume token."""


class CheckpointSaveError(CheckpointError):
    """Report a checkpoint that could not be persisted."""


class UnsupportedCheckpointVersionError(CheckpointError):
    """Report a checkpoint version unsupported by this runtime."""


class InvalidCheckpointError(CheckpointError):
    """Report checkpoint facts that violate restoration invariants."""
