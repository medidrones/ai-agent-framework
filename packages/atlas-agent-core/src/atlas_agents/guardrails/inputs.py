"""Stage-specific immutable values evaluated by runtime guardrails."""

from atlas_agents._models import _FrozenModel
from atlas_agents.agents import AgentDefinition, AgentInput
from atlas_agents.guardrails.base import Guardrail
from atlas_agents.knowledge import Citation
from atlas_agents.models import ModelResponse, ToolCall
from atlas_agents.tools import ToolDefinition, ToolExecutionResult


class InputGuardrailInput(_FrozenModel):
    """Provide immutable agent configuration and input to input policies."""

    agent: AgentDefinition
    input_data: AgentInput


class ModelOutputGuardrailInput(_FrozenModel):
    """Provide one complete model response and its turn number."""

    response: ModelResponse
    turn_number: int


class ToolCallGuardrailInput(_FrozenModel):
    """Provide a resolved tool call and definition before approval."""

    tool_call: ToolCall
    tool_definition: ToolDefinition


class ToolResultGuardrailInput(_FrozenModel):
    """Provide a normalized tool result before model disclosure."""

    tool_call: ToolCall
    tool_result: ToolExecutionResult


class FinalOutputGuardrailInput(_FrozenModel):
    """Provide the structurally valid candidate returned to consumers."""

    output: object
    citations: tuple[Citation, ...] = ()


type InputGuardrail = Guardrail[InputGuardrailInput]
type OutputGuardrail = Guardrail[FinalOutputGuardrailInput]
type ModelOutputGuardrail = Guardrail[ModelOutputGuardrailInput]
type ToolCallGuardrail = Guardrail[ToolCallGuardrailInput]
type ToolResultGuardrail = Guardrail[ToolResultGuardrailInput]
