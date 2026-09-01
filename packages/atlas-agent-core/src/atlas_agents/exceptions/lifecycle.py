"""Public exceptions raised by execution lifecycle operations."""

from atlas_agents.agents.status import ExecutionStatus
from atlas_agents.exceptions.base import AtlasAgentError


class InvalidExecutionTransitionError(AtlasAgentError):
    """Report a transition that is not allowed by the execution state machine."""

    def __init__(
        self,
        current_status: ExecutionStatus,
        requested_status: ExecutionStatus,
    ) -> None:
        """Initialize the error with current and requested statuses."""
        self.current_status = current_status
        self.requested_status = requested_status
        message = (
            "Não é permitido alterar a execução de "
            f"{current_status.value} para {requested_status.value}."
        )
        super().__init__(message)
