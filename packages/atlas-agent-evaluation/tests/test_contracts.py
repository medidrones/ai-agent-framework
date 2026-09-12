from datetime import UTC, datetime
from math import inf, nan

import pytest
from pydantic import JsonValue, ValidationError

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentErrorInfo,
    AgentEvent,
    AgentEventType,
    AgentInput,
    AgentResult,
    ExecutionState,
    ExecutionStatus,
    GuardrailDecision,
    ToolCallRecord,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolOutput,
    Usage,
)
from atlas_agents.evaluation import (
    ContainsEvaluator,
    DuplicateEvaluationCaseError,
    DuplicateEvaluatorError,
    DuplicateExpectationError,
    EvaluationCapturePolicy,
    EvaluationCase,
    EvaluationDataset,
    EvaluationExpectation,
    EvaluationInput,
    EvaluationMetric,
    EvaluationMetricError,
    EvaluationObservation,
    EvaluationObservationSummary,
    EvaluationResult,
    EvaluationResultStatus,
    EvaluationScore,
    EvaluatorNotRegisteredError,
    EvaluatorRegistry,
    ExactMatchEvaluator,
    MetricDirection,
    ObservedToolCall,
)


def expectation(
    evaluator_id: str = "exact-output",
    expected: JsonValue = "expected",
    *,
    expectation_id: str = "expectation",
) -> EvaluationExpectation:
    return EvaluationExpectation(
        expectation_id=expectation_id,
        evaluator_id=evaluator_id,
        expected=expected,
    )


def case(*expectations: EvaluationExpectation) -> EvaluationCase:
    return EvaluationCase(
        case_id="case-1",
        name="Caso",
        input=EvaluationInput(agent_input=AgentInput(message="entrada")),
        expectations=expectations,
    )


def test_case_and_dataset_are_frozen_ordered_serializable_and_isolated() -> None:
    nested: dict[str, JsonValue] = {"value": 1}
    metadata: dict[str, JsonValue] = {"nested": nested}
    first = expectation(expectation_id="first")
    second = expectation("contains", "fragment", expectation_id="second")
    evaluation_case = EvaluationCase(
        case_id=" opaque-case ",
        name=" Caso ",
        expectations=(first, second),
        metadata=metadata,
    )
    dataset = EvaluationDataset(
        dataset_id="dataset",
        name="Conjunto",
        version="2026.09",
        cases=(evaluation_case,),
    )
    nested["value"] = 99

    assert evaluation_case.case_id == "opaque-case"
    assert evaluation_case.name == "Caso"
    assert [item.expectation_id for item in evaluation_case.expectations] == [
        "first",
        "second",
    ]
    assert evaluation_case.metadata["nested"] == {"value": 1}
    assert EvaluationDataset.model_validate_json(dataset.model_dump_json()) == dataset
    with pytest.raises(ValidationError):
        dataset.version = "2"


@pytest.mark.parametrize(
    "values",
    [
        {"case_id": " ", "name": "Caso"},
        {"case_id": "case", "name": " "},
    ],
)
def test_case_rejects_blank_required_text(values: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate(values)


def test_duplicate_expectation_and_case_ids_are_rejected() -> None:
    duplicate = expectation()
    with pytest.raises(DuplicateExpectationError):
        case(duplicate, duplicate)
    item = case()
    with pytest.raises(DuplicateEvaluationCaseError):
        EvaluationDataset(
            dataset_id="dataset",
            name="Conjunto",
            version="1",
            cases=(item, item),
        )


def test_empty_dataset_is_valid() -> None:
    dataset = EvaluationDataset(dataset_id="dataset", name="Conjunto", version="1")
    assert dataset.cases == ()


def test_metric_threshold_direction_bounds_and_informational_semantics() -> None:
    higher = EvaluationMetric(
        metric_id="quality",
        name="Qualidade",
        description="Qualidade medida.",
        direction=MetricDirection.HIGHER_IS_BETTER,
        min_value=0,
        max_value=1,
    )
    lower = higher.model_copy(
        update={"metric_id": "error", "direction": MetricDirection.LOWER_IS_BETTER}
    )
    informational = higher.model_copy(
        update={"metric_id": "info", "direction": MetricDirection.NONE}
    )

    assert higher.evaluate_threshold(0.8, 0.7) is True
    assert higher.evaluate_threshold(0.6, 0.7) is False
    assert lower.evaluate_threshold(0.2, 0.3) is True
    assert lower.evaluate_threshold(0.4, 0.3) is False
    assert informational.evaluate_threshold(0.5, 0.5) is None
    assert higher.evaluate_threshold(0.5, None) is None
    assert EvaluationScore.from_metric(higher, value=1, threshold=1).passed is True


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_metric_and_score_reject_non_finite_values(value: float) -> None:
    metric = EvaluationMetric(
        metric_id="quality",
        name="Qualidade",
        description="Qualidade medida.",
        min_value=0,
        max_value=1,
    )
    with pytest.raises(EvaluationMetricError):
        metric.validate_value(value)
    with pytest.raises(ValidationError):
        EvaluationScore(value=value)


def test_metric_rejects_invalid_bounds_and_out_of_range_values() -> None:
    with pytest.raises(EvaluationMetricError):
        EvaluationMetric(
            metric_id="invalid",
            name="Inválida",
            description="Inválida.",
            min_value=2,
            max_value=1,
        )
    metric = EvaluationMetric(
        metric_id="bounded",
        name="Limitada",
        description="Limitada.",
        min_value=0,
        max_value=1,
    )
    with pytest.raises(EvaluationMetricError):
        metric.evaluate_threshold(2, 1)


def test_registry_is_ordered_local_and_has_typed_errors() -> None:
    exact = ExactMatchEvaluator()
    contains = ContainsEvaluator()
    registry = EvaluatorRegistry((exact, contains))

    assert registry.evaluators == (exact, contains)
    assert registry.get("exact-output") is exact
    assert registry.try_get("missing") is None
    with pytest.raises(DuplicateEvaluatorError):
        registry.register(ExactMatchEvaluator())
    assert registry.unregister("contains") is contains
    with pytest.raises(EvaluatorNotRegisteredError):
        registry.get("contains")
    with pytest.raises(EvaluatorNotRegisteredError):
        registry.unregister("contains")


def test_result_status_invariants_do_not_turn_errors_into_zero_score() -> None:
    metric = ExactMatchEvaluator().metric
    with pytest.raises(ValidationError):
        EvaluationResult(
            expectation_id="e",
            evaluator_id="exact-output",
            metric=metric,
            status=EvaluationResultStatus.ERROR,
            score=EvaluationScore(value=0, passed=False),
        )


def test_default_observation_capture_excludes_events_and_sensitive_error_message() -> (
    None
):
    event = AgentEvent(
        event_id="event",
        execution_id="execution",
        sequence=1,
        event_type=AgentEventType.MODEL_TEXT_DELTA,
        timestamp=datetime.now(UTC),
        data={"delta": "segredo intermediário"},
    )
    result = AgentResult[object](
        execution_id="execution",
        status=ExecutionStatus.FAILED,
        usage=Usage(),
        events=(event,),
        error=AgentErrorInfo(code="provider_error", message="credencial secreta"),
    )
    observation = EvaluationObservation.from_agent_result(result, agent_id="agent")

    assert observation.events == ()
    assert observation.error_code == "provider_error"
    assert "credencial secreta" not in observation.model_dump_json()
    explicit = EvaluationObservation.from_agent_result(
        result,
        agent_id="agent",
        capture_policy=EvaluationCapturePolicy(include_intermediate_model_content=True),
    )
    assert explicit.events == (event,)


def test_observation_summary_excludes_output_arguments_and_tool_outputs() -> None:
    observation = EvaluationObservation(
        execution_id="execution",
        agent_id="agent",
        status=ExecutionStatus.COMPLETED,
        output="segredo final",
        tool_calls=(
            ObservedToolCall(
                tool_call_id="call",
                tool_name="tool",
                status=ToolExecutionStatus.SUCCEEDED,
                arguments={"secret": "argumento"},
                output={"secret": "resultado"},
            ),
        ),
    )
    summary = EvaluationObservationSummary.from_observation(observation)
    serialized = summary.model_dump_json()

    assert summary.tool_call_count == 1
    assert "segredo final" not in serialized
    assert "argumento" not in serialized
    assert "resultado" not in serialized


def test_observation_capture_policy_requires_explicit_tool_data_opt_in() -> None:
    timestamp = datetime.now(UTC)
    record = ToolCallRecord(
        tool_call_id="call",
        tool_name="search",
        arguments={"query": "argumento secreto"},
        result=ToolExecutionResult(
            tool_call_id="call",
            tool_name="search",
            status=ToolExecutionStatus.SUCCEEDED,
            output=ToolOutput(content={"answer": "resultado secreto"}),
            started_at=timestamp,
            completed_at=timestamp,
        ),
    )
    result = AgentResult[object](
        execution_id="execution",
        status=ExecutionStatus.COMPLETED,
        output="final",
        usage=Usage(),
    )

    secure = EvaluationObservation.from_agent_result(
        result,
        agent_id="agent",
        tool_calls=(record,),
    )
    rich = EvaluationObservation.from_agent_result(
        result,
        agent_id="agent",
        tool_calls=(record,),
        capture_policy=EvaluationCapturePolicy(
            include_tool_arguments=True,
            include_tool_outputs=True,
        ),
    )

    assert secure.tool_calls[0].arguments is None
    assert secure.tool_calls[0].output is None
    assert rich.tool_calls[0].arguments == {"query": "argumento secreto"}
    assert rich.tool_calls[0].output == {"answer": "resultado secreto"}


def test_observation_derives_safe_tool_and_guardrail_facts_from_events() -> None:
    timestamp = datetime.now(UTC)
    events = (
        AgentEvent(
            event_id="tool",
            execution_id="execution",
            sequence=1,
            event_type=AgentEventType.TOOL_EXECUTION_COMPLETED,
            timestamp=timestamp,
            data={
                "tool_call_id": "call",
                "tool_name": "search",
                "status": "succeeded",
                "deduplicated": True,
            },
        ),
        AgentEvent(
            event_id="guardrail",
            execution_id="execution",
            sequence=2,
            event_type=AgentEventType.GUARDRAIL_TRANSFORMED,
            timestamp=timestamp,
            data={
                "stage": "input",
                "guardrail_id": "redaction",
                "decision": "transform",
                "violation_codes": [],
                "transformation_kinds": ["redact"],
            },
        ),
    )
    result = AgentResult[object](
        execution_id="execution",
        status=ExecutionStatus.COMPLETED,
        output="final",
        usage=Usage(),
        events=events,
    )

    observed = EvaluationObservation.from_agent_result(result, agent_id="agent")

    assert observed.tool_calls[0].deduplicated is True
    assert observed.guardrail_records[0].decision is GuardrailDecision.TRANSFORM
    assert observed.guardrail_records[0].transformation_kinds == ("redact",)


def test_snapshot_factory_uses_public_snapshot_without_runtime_reference() -> None:
    state = ExecutionState(
        execution_id="execution",
        agent=AgentDefinition(
            agent_id="agent",
            name="Agente",
            instructions="Responda.",
        ),
        input_data=AgentInput(message="entrada"),
        context=AgentContext(execution_id="execution"),
    )

    observed = EvaluationObservation.from_execution_snapshot(state.snapshot())

    assert observed.execution_id == "execution"
    assert observed.agent_id == "agent"
    assert observed.status is ExecutionStatus.CREATED
    assert "ExecutionState" not in repr(observed)
