from datetime import UTC, datetime

import pytest
from pydantic import JsonValue

from atlas_agents import (
    Citation,
    ExecutionStatus,
    GuardrailDecision,
    GuardrailEnforcement,
    GuardrailRecord,
    GuardrailStage,
    ToolExecutionStatus,
)
from atlas_agents.evaluation import (
    CitationEvaluator,
    ContainsEvaluator,
    EvaluationCase,
    EvaluationContext,
    EvaluationExpectation,
    EvaluationFindingSeverity,
    EvaluationObservation,
    EvaluationResultStatus,
    ExactMatchEvaluator,
    ExecutionStatusEvaluator,
    GuardrailOutcomeEvaluator,
    JudgeEvaluator,
    JudgeRequest,
    JudgeResponse,
    ObservedToolCall,
    ToolUsageEvaluator,
)


def case(
    evaluator_id: str, expected: JsonValue
) -> tuple[EvaluationCase, EvaluationExpectation]:
    expectation = EvaluationExpectation(
        expectation_id="expectation",
        evaluator_id=evaluator_id,
        expected=expected,
    )
    return (
        EvaluationCase(case_id="case", name="Caso", expectations=(expectation,)),
        expectation,
    )


def observation(
    output: JsonValue = "Resposta esperada com fragmento",
    **updates: object,
) -> EvaluationObservation:
    values: dict[str, object] = {
        "execution_id": "execution",
        "agent_id": "agent",
        "status": ExecutionStatus.COMPLETED,
        "output": output,
    }
    values.update(updates)
    return EvaluationObservation.model_validate(values)


def context() -> EvaluationContext:
    return EvaluationContext(
        evaluation_run_id="run",
        dataset_id="dataset",
        case_id="case",
    )


@pytest.mark.parametrize(
    ("evaluator", "expected", "output", "passed"),
    [
        (ExactMatchEvaluator(), "Resposta", "Resposta", True),
        (ExactMatchEvaluator(), "Resposta", "resposta", False),
        (ExactMatchEvaluator(case_sensitive=False), "Resposta", "resposta", True),
        (ExactMatchEvaluator(strip=True), "Resposta", " Resposta ", True),
        (ExactMatchEvaluator(), "1", 1, False),
        (ContainsEvaluator(), "fragmento", "um fragmento aqui", True),
        (ContainsEvaluator(), "Fragmento", "um fragmento aqui", False),
        (ContainsEvaluator(case_sensitive=False), "Fragmento", "fragmento", True),
        (ContainsEvaluator(), "fragmento", {"not": "text"}, False),
    ],
)
async def test_text_evaluators(
    evaluator: ExactMatchEvaluator | ContainsEvaluator,
    expected: str,
    output: JsonValue,
    passed: bool,
) -> None:
    evaluation_case, expectation = case(evaluator.evaluator_id, expected)
    result = await evaluator.evaluate(
        evaluation_case,
        expectation,
        observation(output),
        context(),
    )

    assert result.status is EvaluationResultStatus.COMPLETED
    assert result.score is not None
    assert result.score.passed is passed
    assert bool(result.findings) is (not passed)


@pytest.mark.parametrize("status", list(ExecutionStatus))
async def test_status_evaluator_supports_every_public_status(
    status: ExecutionStatus,
) -> None:
    evaluator = ExecutionStatusEvaluator()
    evaluation_case, expectation = case(evaluator.evaluator_id, status.value)
    result = await evaluator.evaluate(
        evaluation_case,
        expectation,
        observation(status=status),
        context(),
    )
    assert result.score is not None
    assert result.score.passed is True


@pytest.mark.parametrize(
    ("expected", "passed"),
    [
        ({"required_tool_names": ["search"]}, True),
        ({"required_tool_names": ["missing"]}, False),
        ({"forbidden_tool_names": ["search"]}, False),
        ({"minimum_executions": 2}, True),
        ({"maximum_executions": 1}, False),
    ],
)
async def test_tool_usage_evaluator_counts_only_actual_non_replayed_calls(
    expected: JsonValue,
    passed: bool,
) -> None:
    evaluator = ToolUsageEvaluator()
    evaluation_case, expectation = case(evaluator.evaluator_id, expected)
    calls = (
        ObservedToolCall(
            tool_call_id="1",
            tool_name="search",
            status=ToolExecutionStatus.SUCCEEDED,
        ),
        ObservedToolCall(
            tool_call_id="2",
            tool_name="other",
            status=ToolExecutionStatus.FAILED,
        ),
        ObservedToolCall(
            tool_call_id="1",
            tool_name="search",
            status=ToolExecutionStatus.SUCCEEDED,
            deduplicated=True,
        ),
    )
    result = await evaluator.evaluate(
        evaluation_case,
        expectation,
        observation(tool_calls=calls),
        context(),
    )
    assert result.score is not None
    assert result.score.passed is passed


@pytest.mark.parametrize(
    ("expected", "passed"),
    [
        ({"minimum_count": 1}, True),
        ({"minimum_count": 2}, False),
        ({"required_citation_ids": ["K1"]}, True),
        ({"required_citation_ids": ["K2"]}, False),
        (
            {
                "allowed_citation_ids": ["K2"],
                "forbid_unknown": True,
            },
            False,
        ),
    ],
)
async def test_citation_evaluator_measures_structure_not_groundedness(
    expected: JsonValue,
    passed: bool,
) -> None:
    evaluator = CitationEvaluator()
    evaluation_case, expectation = case(evaluator.evaluator_id, expected)
    citation = Citation(
        citation_key="K1",
        source_id="source",
        document_id="document",
        passage_id="passage",
    )
    result = await evaluator.evaluate(
        evaluation_case,
        expectation,
        observation(citations=(citation,)),
        context(),
    )
    assert result.score is not None
    assert result.score.passed is passed


@pytest.mark.parametrize(
    ("expected", "passed"),
    [
        ({"stage": "input"}, True),
        ({"stage": "input", "decision": "reject"}, True),
        ({"stage": "input", "violation_code": "blocked"}, True),
        ({"stage": "final_output"}, False),
    ],
)
async def test_guardrail_evaluator_uses_only_safe_audit_records(
    expected: JsonValue,
    passed: bool,
) -> None:
    evaluator = GuardrailOutcomeEvaluator()
    evaluation_case, expectation = case(evaluator.evaluator_id, expected)
    record = GuardrailRecord(
        stage=GuardrailStage.INPUT,
        guardrail_id="policy",
        decision=GuardrailDecision.REJECT,
        enforcement=GuardrailEnforcement.EXECUTION,
        violation_codes=("blocked",),
        timestamp=datetime.now(UTC),
    )
    result = await evaluator.evaluate(
        evaluation_case,
        expectation,
        observation(guardrail_records=(record,)),
        context(),
    )
    assert result.score is not None
    assert result.score.passed is passed


class FakeJudge:
    def __init__(self, response: JudgeResponse) -> None:
        self.response = response
        self.requests: list[JudgeRequest] = []

    async def judge(
        self, request: JudgeRequest, evaluation_context: EvaluationContext
    ) -> JudgeResponse:
        assert evaluation_context.case_id == "case"
        self.requests.append(request)
        return self.response


async def test_judge_evaluator_maps_opt_in_score_reason_and_reference() -> None:
    judge = FakeJudge(JudgeResponse(score=0.8, reason="Atendeu ao critério."))
    evaluator = JudgeEvaluator(judge=judge, criteria="Avalie qualidade.")
    evaluation_case, expectation = case(evaluator.evaluator_id, "referência")
    result = await evaluator.evaluate(
        evaluation_case,
        expectation,
        observation("candidato"),
        context(),
    )

    assert result.score is not None
    assert result.score.value == 0.8
    assert result.score.passed is True
    assert result.findings[0].severity is EvaluationFindingSeverity.INFO
    assert result.findings[0].message == "Atendeu ao critério."
    assert judge.requests[0].candidate == "candidato"
    assert judge.requests[0].reference == "referência"
