"""Tests for generic agent result invariants."""

import pytest
from pydantic import ValidationError

from atlas_agents import AgentErrorInfo, AgentResult, ExecutionStatus, Usage


def _error() -> AgentErrorInfo:
    return AgentErrorInfo(code="MODEL_UNAVAILABLE", message="Model unavailable.")


def test_error_info_accepts_safe_structured_details() -> None:
    error = AgentErrorInfo(
        code="TEMPORARY_FAILURE",
        message="Try again later.",
        retryable=True,
        details={"attempt": 2},
    )

    assert error.retryable is True
    assert error.details == {"attempt": 2}


@pytest.mark.parametrize(
    ("code", "message"),
    [(" ", "Failure."), ("FAILURE", " ")],
)
def test_error_info_rejects_blank_required_text(code: str, message: str) -> None:
    with pytest.raises(ValidationError):
        AgentErrorInfo(code=code, message=message)


def test_completed_result_without_error_is_valid() -> None:
    result = AgentResult[str](
        execution_id="execution",
        status=ExecutionStatus.COMPLETED,
        output="done",
        usage=Usage(),
    )

    assert result.output == "done"
    assert result.error is None


def test_completed_result_with_error_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentResult[str](
            execution_id="execution",
            status=ExecutionStatus.COMPLETED,
            usage=Usage(),
            error=_error(),
        )


def test_failed_result_with_error_is_valid() -> None:
    result = AgentResult[str](
        execution_id="execution",
        status=ExecutionStatus.FAILED,
        usage=Usage(),
        error=_error(),
    )

    assert result.error == _error()


def test_failed_result_without_error_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentResult[str](
            execution_id="execution",
            status=ExecutionStatus.FAILED,
            usage=Usage(),
        )


def test_cancelled_result_without_output_or_error_is_valid() -> None:
    result = AgentResult[str](
        execution_id="execution",
        status=ExecutionStatus.CANCELLED,
        usage=Usage(),
    )

    assert result.output is None
    assert result.error is None


def test_error_info_is_immutable() -> None:
    error = _error()

    with pytest.raises(ValidationError):
        error.message = "Changed"


def test_agent_result_is_immutable() -> None:
    result = AgentResult[str](
        execution_id="execution",
        status=ExecutionStatus.COMPLETED,
        usage=Usage(),
    )

    with pytest.raises(ValidationError):
        result.status = ExecutionStatus.FAILED


@pytest.mark.parametrize(
    "status",
    [
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
        ExecutionStatus.LIMIT_EXCEEDED,
        ExecutionStatus.BUDGET_EXCEEDED,
        ExecutionStatus.REJECTED,
    ],
)
def test_non_failure_terminal_result_allows_optional_error(
    status: ExecutionStatus,
) -> None:
    without_error = AgentResult[str](
        execution_id="execution",
        status=status,
        usage=Usage(),
    )
    with_error = AgentResult[str](
        execution_id="execution",
        status=status,
        usage=Usage(),
        error=_error(),
    )

    assert without_error.error is None
    assert with_error.error is not None
