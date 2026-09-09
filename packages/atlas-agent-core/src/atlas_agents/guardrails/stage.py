"""Provider-neutral guardrail stages and decisions."""

from enum import StrEnum


class GuardrailStage(StrEnum):
    """Identify a precise runtime enforcement boundary."""

    INPUT = "input"
    MODEL_OUTPUT = "model_output"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINAL_OUTPUT = "final_output"


class GuardrailDecision(StrEnum):
    """Describe the explicit outcome of one policy evaluation."""

    ALLOW = "allow"
    TRANSFORM = "transform"
    REJECT = "reject"


class GuardrailEnforcement(StrEnum):
    """Define whether rejection stops an operation or the execution."""

    OPERATION = "operation"
    EXECUTION = "execution"


class GuardrailSeverity(StrEnum):
    """Classify a violation independently from its enforcement decision."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
