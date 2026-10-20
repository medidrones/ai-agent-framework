"""Async orchestration boundaries without concrete execution behavior."""

from typing import Protocol

from atlas_agents.orchestration.context import WorkflowContext, WorkflowInput
from atlas_agents.orchestration.definitions import WorkflowDefinition
from atlas_agents.orchestration.results import WorkflowResult


class WorkflowOrchestrator(Protocol):
    """Coordinate a workflow while delegating single-agent execution elsewhere."""

    async def execute(
        self,
        definition: WorkflowDefinition,
        workflow_input: WorkflowInput,
        context: WorkflowContext,
    ) -> WorkflowResult:
        """Execute one workflow according to the supplied contracts."""
        ...
