"""Evaluate five deterministic observations without an LLM judge."""

import asyncio

from atlas_agents import ExecutionStatus
from atlas_agents.evaluation import (
    ContainsEvaluator,
    EvaluationCase,
    EvaluationDataset,
    EvaluationExpectation,
    EvaluationObservation,
    EvaluationRunner,
    EvaluatorRegistry,
    ExactMatchEvaluator,
)


def _case(index: int, expected: str) -> EvaluationCase:
    return EvaluationCase(
        case_id=f"case-{index}",
        name=f"Caso {index}",
        expectations=(
            EvaluationExpectation(
                expectation_id=f"expectation-{index}",
                evaluator_id=("exact-output" if index < 5 else "contains"),
                expected=expected,
            ),
        ),
    )


async def _run() -> None:
    cases = tuple(_case(index, "ok") for index in range(1, 6))
    dataset = EvaluationDataset(
        dataset_id="official-example",
        name="Dataset local",
        version="1",
        cases=cases,
    )
    registry = EvaluatorRegistry((ExactMatchEvaluator(), ContainsEvaluator()))
    observations = {
        case.case_id: EvaluationObservation(
            execution_id=f"execution-{index}",
            agent_id="example-agent",
            status=ExecutionStatus.COMPLETED,
            output=("falhou" if index == 4 else "ok"),
        )
        for index, case in enumerate(cases, start=1)
    }
    report = await EvaluationRunner(registry=registry).evaluate_dataset(
        dataset=dataset,
        observations=observations,
        evaluation_run_id="evaluation-example",
    )
    print(f"Casos: {report.summary.case_count}")  # noqa: T201
    print(f"Aprovados: {report.summary.passed_case_count}")  # noqa: T201
    print(f"Reprovados: {report.summary.failed_case_count}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
