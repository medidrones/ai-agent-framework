"""Public exception hierarchy for orchestration contracts."""

from atlas_agents.exceptions import AtlasAgentError


class WorkflowError(AtlasAgentError):
    """Base class for known workflow errors."""


class WorkflowDefinitionError(WorkflowError):
    """Base class for invalid workflow definitions."""


class WorkflowValidationError(WorkflowDefinitionError):
    """Report a known structural workflow validation failure."""


class WorkflowContractError(WorkflowError):
    """Report a violation of a public orchestration contract."""
