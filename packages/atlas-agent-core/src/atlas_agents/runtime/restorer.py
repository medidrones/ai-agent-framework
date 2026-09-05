"""Checkpoint construction and controlled execution state restoration."""

from atlas_agents.approvals import (
    InvalidCheckpointError,
    UnsupportedCheckpointVersionError,
)
from atlas_agents.models import ToolCall
from atlas_agents.runtime.budget import ExecutionBudget
from atlas_agents.runtime.checkpoint import (
    CURRENT_CHECKPOINT_VERSION,
    ExecutionCheckpoint,
    ExecutionMode,
)
from atlas_agents.runtime.deadline import ExecutionDeadline
from atlas_agents.runtime.limits import ExecutionLimits
from atlas_agents.runtime.state import ExecutionState


class ExecutionStateRestorer:
    """Build and restore versioned checkpoints without using snapshots."""

    def build_checkpoint(
        self,
        *,
        state: ExecutionState,
        execution_mode: ExecutionMode,
        pending_tool_calls: tuple[ToolCall, ...],
        limits: ExecutionLimits,
        budget: ExecutionBudget,
        deadline: ExecutionDeadline,
    ) -> ExecutionCheckpoint:
        """Capture all serializable facts required by the next invocation."""
        if state.pending_approval is None or state.model_selection is None:
            raise InvalidCheckpointError(
                "O estado não possui aprovação e seleção necessárias ao checkpoint."
            )
        return ExecutionCheckpoint(
            checkpoint_version=CURRENT_CHECKPOINT_VERSION,
            execution_id=state.execution_id,
            execution_mode=execution_mode,
            agent=state.agent,
            input_data=state.input_data,
            context=state.context,
            status=state.status,
            messages=state.messages,
            model_selection=state.model_selection,
            usage=state.usage,
            has_model_usage=state.has_model_usage,
            turn_count=state.turn_count,
            tool_call_count=state.tool_call_count,
            events=state.events,
            transitions=state.transitions,
            tool_call_records=state.tool_calls,
            pending_approval=state.pending_approval,
            pending_tool_calls=pending_tool_calls,
            approval_history=state.approval_history,
            limits=limits,
            budget=budget,
            remaining_timeout_seconds=deadline.remaining_seconds(),
            created_at=state.created_at,
            updated_at=state.updated_at,
            metadata=state.metadata,
        )

    def restore(self, checkpoint: ExecutionCheckpoint) -> ExecutionState:
        """Restore a state after validating the supported checkpoint version."""
        if checkpoint.checkpoint_version != CURRENT_CHECKPOINT_VERSION:
            raise UnsupportedCheckpointVersionError(
                "A versão do checkpoint não é suportada por este runtime."
            )
        try:
            validated = ExecutionCheckpoint.model_validate(
                checkpoint.model_dump(mode="python")
            )
            return ExecutionState.restore(
                execution_id=validated.execution_id,
                agent=validated.agent,
                input_data=validated.input_data,
                context=validated.context,
                messages=validated.messages,
                model_selection=validated.model_selection,
                usage=validated.usage,
                has_model_usage=validated.has_model_usage,
                turn_count=validated.turn_count,
                tool_call_count=validated.tool_call_count,
                tool_calls=validated.tool_call_records,
                events=validated.events,
                transitions=validated.transitions,
                pending_approval=validated.pending_approval,
                approval_history=validated.approval_history,
                created_at=validated.created_at,
                updated_at=validated.updated_at,
                metadata=validated.metadata,
            )
        except Exception as error:
            if isinstance(error, UnsupportedCheckpointVersionError):
                raise
            raise InvalidCheckpointError(
                "O checkpoint não pôde restaurar um estado de execução válido."
            ) from error
