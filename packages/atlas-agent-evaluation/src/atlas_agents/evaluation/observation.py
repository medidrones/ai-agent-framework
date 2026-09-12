"""Privacy-conscious immutable observations of production executions."""

from pydantic import Field, JsonValue, TypeAdapter, field_validator

from atlas_agents import (
    AgentEvent,
    AgentEventType,
    AgentResult,
    Citation,
    ExecutionSnapshot,
    ExecutionStatus,
    ExecutionSuspension,
    GuardrailDecision,
    GuardrailEnforcement,
    GuardrailRecord,
    GuardrailStage,
    ToolCallRecord,
    ToolExecutionStatus,
    Usage,
)
from atlas_agents.evaluation._models import (
    FrozenEvaluationModel,
    json_mapping,
    non_empty,
)
from atlas_agents.knowledge import extract_citations

_JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
_JSON_OBJECT: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


class EvaluationCapturePolicy(FrozenEvaluationModel):
    """Control explicit capture of sensitive execution artifacts."""

    include_tool_arguments: bool = False
    include_tool_outputs: bool = False
    include_intermediate_model_content: bool = False


class ObservedToolCall(FrozenEvaluationModel):
    """Describe safe facts about a requested or executed tool call."""

    tool_call_id: str
    tool_name: str
    status: ToolExecutionStatus
    turn_number: int | None = Field(default=None, ge=1)
    deduplicated: bool = False
    arguments: dict[str, JsonValue] | None = None
    output: JsonValue | None = None

    @field_validator("tool_call_id", "tool_name")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject blank tool identities."""
        return non_empty(value)

    @field_validator("arguments")
    @classmethod
    def validate_arguments(
        cls, value: dict[str, JsonValue] | None
    ) -> dict[str, JsonValue] | None:
        """Keep opt-in arguments JSON-compatible and isolated."""
        return None if value is None else json_mapping(value)


class EvaluationObservation(FrozenEvaluationModel):
    """Capture only immutable public facts required by evaluators."""

    execution_id: str
    agent_id: str
    status: ExecutionStatus
    output: JsonValue | None = None
    usage: Usage = Usage()
    events: tuple[AgentEvent, ...] = ()
    error_code: str | None = None
    citations: tuple[Citation, ...] = ()
    tool_calls: tuple[ObservedToolCall, ...] = ()
    guardrail_records: tuple[GuardrailRecord, ...] = ()
    suspended: bool = False
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("execution_id", "agent_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Reject blank execution and agent identifiers."""
        return non_empty(value)

    @field_validator("error_code")
    @classmethod
    def validate_error_code(cls, value: str | None) -> str | None:
        """Reject explicitly blank error codes."""
        return None if value is None else non_empty(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep observation metadata JSON-compatible and isolated."""
        return json_mapping(value)

    @classmethod
    def from_agent_result(
        cls,
        result: AgentResult[object],
        *,
        agent_id: str,
        capture_policy: EvaluationCapturePolicy | None = None,
        tool_calls: tuple[ToolCallRecord, ...] = (),
        guardrail_records: tuple[GuardrailRecord, ...] = (),
    ) -> "EvaluationObservation":
        """Map a public result and optional public artifacts into an observation."""
        policy = capture_policy or EvaluationCapturePolicy()
        observed_tools = (
            _tools_from_records(tool_calls, policy)
            if tool_calls
            else _tools_from_events(result.events)
        )
        observed_guardrails = (
            guardrail_records
            if guardrail_records
            else _guardrails_from_events(result.events)
        )
        return cls(
            execution_id=result.execution_id,
            agent_id=agent_id,
            status=result.status,
            output=_JSON_VALUE.validate_python(result.output),
            usage=result.usage,
            events=(result.events if policy.include_intermediate_model_content else ()),
            error_code=result.error.code if result.error is not None else None,
            citations=result.citations,
            tool_calls=observed_tools,
            guardrail_records=observed_guardrails,
        )

    @classmethod
    def from_execution_snapshot(
        cls,
        snapshot: ExecutionSnapshot,
        *,
        capture_policy: EvaluationCapturePolicy | None = None,
    ) -> "EvaluationObservation":
        """Map an immutable execution snapshot with optional rich capture."""
        policy = capture_policy or EvaluationCapturePolicy()
        return cls(
            execution_id=snapshot.execution_id,
            agent_id=snapshot.agent_id,
            status=snapshot.status,
            output=_JSON_VALUE.validate_python(snapshot.output),
            usage=snapshot.usage,
            events=(
                snapshot.events if policy.include_intermediate_model_content else ()
            ),
            error_code=(snapshot.error.code if snapshot.error is not None else None),
            citations=extract_citations(
                snapshot.output,
                (
                    snapshot.knowledge_context.citations
                    if snapshot.knowledge_context is not None
                    else ()
                ),
            ),
            tool_calls=_tools_from_records(snapshot.tool_calls, policy),
            guardrail_records=snapshot.guardrail_records,
            suspended=snapshot.status is ExecutionStatus.WAITING_FOR_APPROVAL,
        )

    @classmethod
    def from_execution_suspension(
        cls,
        suspension: ExecutionSuspension,
        *,
        agent_id: str,
    ) -> "EvaluationObservation":
        """Observe HITL suspension without retaining its resume token."""
        return cls(
            execution_id=suspension.execution_id,
            agent_id=agent_id,
            status=suspension.status,
            suspended=True,
        )


class EvaluationObservationSummary(FrozenEvaluationModel):
    """Persist a privacy-safe report projection without final output."""

    execution_id: str
    status: ExecutionStatus
    usage: Usage
    tool_call_count: int = Field(ge=0)
    citation_count: int = Field(ge=0)
    guardrail_record_count: int = Field(ge=0)
    suspended: bool = False

    @field_validator("execution_id")
    @classmethod
    def validate_execution_id(cls, value: str) -> str:
        """Reject a blank execution identifier."""
        return non_empty(value)

    @classmethod
    def from_observation(
        cls, observation: EvaluationObservation
    ) -> "EvaluationObservationSummary":
        """Remove evaluable content while retaining aggregate runtime facts."""
        return cls(
            execution_id=observation.execution_id,
            status=observation.status,
            usage=observation.usage,
            tool_call_count=sum(
                1 for item in observation.tool_calls if not item.deduplicated
            ),
            citation_count=len(observation.citations),
            guardrail_record_count=len(observation.guardrail_records),
            suspended=observation.suspended,
        )


def _tools_from_records(
    records: tuple[ToolCallRecord, ...],
    policy: EvaluationCapturePolicy,
) -> tuple[ObservedToolCall, ...]:
    observed: list[ObservedToolCall] = []
    for record in records:
        result = record.model_facing_result
        output: JsonValue | None = None
        if policy.include_tool_outputs and result.output is not None:
            output = _JSON_VALUE.validate_python(result.output.content)
        arguments: dict[str, JsonValue] | None = None
        if policy.include_tool_arguments:
            arguments = _JSON_OBJECT.validate_python(record.guarded_arguments)
        observed.append(
            ObservedToolCall(
                tool_call_id=record.tool_call_id,
                tool_name=record.tool_name,
                status=result.status,
                arguments=arguments,
                output=output,
            )
        )
    return tuple(observed)


def _tools_from_events(events: tuple[AgentEvent, ...]) -> tuple[ObservedToolCall, ...]:
    observed: list[ObservedToolCall] = []
    for event in events:
        if event.event_type is not AgentEventType.TOOL_EXECUTION_COMPLETED:
            continue
        call_id = event.data.get("tool_call_id")
        name = event.data.get("tool_name")
        status = event.data.get("status")
        if (
            not isinstance(call_id, str)
            or not isinstance(name, str)
            or not isinstance(status, str)
        ):
            continue
        try:
            parsed_status = ToolExecutionStatus(status)
        except (TypeError, ValueError):
            continue
        observed.append(
            ObservedToolCall(
                tool_call_id=call_id,
                tool_name=name,
                status=parsed_status,
                deduplicated=event.data.get("deduplicated") is True,
            )
        )
    return tuple(observed)


def _guardrails_from_events(
    events: tuple[AgentEvent, ...],
) -> tuple[GuardrailRecord, ...]:
    records: list[GuardrailRecord] = []
    relevant = {
        AgentEventType.GUARDRAIL_REJECTED,
        AgentEventType.GUARDRAIL_TRANSFORMED,
    }
    for event in events:
        if event.event_type not in relevant:
            continue
        data = event.data
        stage = data.get("stage")
        guardrail_id = data.get("guardrail_id")
        decision = data.get("decision")
        enforcement = data.get("enforcement")
        violation_codes = data.get("violation_codes", [])
        transformation_kinds = data.get("transformation_kinds", [])
        if (
            not isinstance(stage, str)
            or not isinstance(guardrail_id, str)
            or not isinstance(decision, str)
            or (enforcement is not None and not isinstance(enforcement, str))
            or not isinstance(violation_codes, list)
            or not isinstance(transformation_kinds, list)
        ):
            continue
        try:
            records.append(
                GuardrailRecord(
                    stage=GuardrailStage(stage),
                    guardrail_id=guardrail_id,
                    decision=GuardrailDecision(decision),
                    enforcement=(
                        GuardrailEnforcement(enforcement)
                        if enforcement is not None
                        else None
                    ),
                    violation_codes=tuple(str(item) for item in violation_codes),
                    transformation_kinds=tuple(
                        str(item) for item in transformation_kinds
                    ),
                    timestamp=event.timestamp,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(records)
