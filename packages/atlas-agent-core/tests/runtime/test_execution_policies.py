"""Tests for immutable execution limits, budgets, checks, and deadlines."""

import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas_agents import (
    ExecutionBudget,
    ExecutionBudgetViolation,
    ExecutionLimitChecker,
    ExecutionLimitReason,
    ExecutionLimits,
    ExecutionLimitViolation,
    Usage,
)
from atlas_agents.runtime.deadline import (
    ExecutionDeadline,
    ExecutionDeadlineExpiredError,
)


def test_empty_and_positive_limits_are_immutable_and_serializable() -> None:
    empty = ExecutionLimits()
    limits = ExecutionLimits(
        max_turns=1,
        max_tool_calls=2,
        max_input_tokens=3,
        max_output_tokens=4,
        max_total_tokens=7,
        timeout_seconds=0.5,
    )

    assert empty.model_dump() == {
        "max_turns": None,
        "max_tool_calls": None,
        "max_input_tokens": None,
        "max_output_tokens": None,
        "max_total_tokens": None,
        "timeout_seconds": None,
    }
    assert limits.model_dump(mode="json")["timeout_seconds"] == 0.5
    with pytest.raises(ValidationError):
        limits.max_turns = 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_turns", 0),
        ("max_turns", -1),
        ("max_tool_calls", 0),
        ("max_input_tokens", 0),
        ("max_output_tokens", -1),
        ("max_total_tokens", True),
        ("timeout_seconds", 0),
        ("timeout_seconds", -1),
        ("timeout_seconds", float("nan")),
        ("timeout_seconds", float("inf")),
    ],
)
def test_invalid_execution_limits_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        ExecutionLimits.model_validate({field: value})


def test_budget_accepts_zero_and_normalizes_currency_without_conversion() -> None:
    assert ExecutionBudget().model_dump() == {
        "max_estimated_cost": None,
        "currency": None,
    }
    budget = ExecutionBudget(max_estimated_cost=Decimal("0"), currency=" USD ")

    assert budget.max_estimated_cost == Decimal("0")
    assert budget.currency == "USD"
    assert budget.model_dump(mode="json") == {
        "max_estimated_cost": "0",
        "currency": "USD",
    }
    with pytest.raises(ValidationError):
        budget.currency = "BRL"


@pytest.mark.parametrize(
    "value",
    [Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity"), True],
)
def test_invalid_budget_values_are_rejected(value: object) -> None:
    with pytest.raises(ValidationError):
        ExecutionBudget(max_estimated_cost=value)  # type: ignore[arg-type]


def test_blank_currency_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExecutionBudget(currency="  ")


def test_violation_value_objects_are_immutable_and_serializable() -> None:
    limit = ExecutionLimitViolation(
        reason=ExecutionLimitReason.MAX_TOTAL_TOKENS,
        limit=10,
        observed=11,
    )
    budget = ExecutionBudgetViolation(limit=Decimal("1"), observed=Decimal("1.1"))

    assert limit.model_dump(mode="json") == {
        "reason": "max_total_tokens",
        "limit": 10,
        "observed": 11,
    }
    assert budget.model_dump(mode="json") == {"limit": "1", "observed": "1.1"}
    with pytest.raises(ValidationError):
        limit.observed = 12


def test_turn_and_tool_checks_apply_next_operation_semantics() -> None:
    checker = ExecutionLimitChecker()
    limits = ExecutionLimits(max_turns=1, max_tool_calls=1)

    assert checker.check_turn_allowed(limits=limits, current_turn_count=0) is None
    turn = checker.check_turn_allowed(limits=limits, current_turn_count=1)
    assert turn == ExecutionLimitViolation(
        reason=ExecutionLimitReason.MAX_TURNS,
        limit=1,
        observed=2,
    )
    assert (
        checker.check_tool_call_allowed(limits=limits, current_tool_call_count=0)
        is None
    )
    tool = checker.check_tool_call_allowed(limits=limits, current_tool_call_count=1)
    assert tool is not None
    assert tool.reason is ExecutionLimitReason.MAX_TOOL_CALLS
    assert tool.observed == 2


def test_usage_checks_allow_equality_and_apply_specific_precedence() -> None:
    checker = ExecutionLimitChecker()
    limits = ExecutionLimits(
        max_input_tokens=10,
        max_output_tokens=20,
        max_total_tokens=30,
    )

    assert (
        checker.check_usage(
            limits=limits,
            usage=Usage(input_tokens=10, output_tokens=20),
        )
        is None
    )
    input_violation = checker.check_usage(
        limits=limits,
        usage=Usage(input_tokens=11, output_tokens=21),
    )
    assert input_violation is not None
    assert input_violation.reason is ExecutionLimitReason.MAX_INPUT_TOKENS

    output_violation = checker.check_usage(
        limits=ExecutionLimits(max_output_tokens=20, max_total_tokens=30),
        usage=Usage(input_tokens=10, output_tokens=21),
    )
    assert output_violation is not None
    assert output_violation.reason is ExecutionLimitReason.MAX_OUTPUT_TOKENS

    total_violation = checker.check_usage(
        limits=ExecutionLimits(max_total_tokens=30),
        usage=Usage(input_tokens=11, output_tokens=20),
    )
    assert total_violation is not None
    assert total_violation.reason is ExecutionLimitReason.MAX_TOTAL_TOKENS


@pytest.mark.parametrize(
    ("cost", "expected"),
    [
        (None, None),
        (Decimal("0.50"), None),
        (Decimal("1.00"), None),
        (
            Decimal("1.01"),
            ExecutionBudgetViolation(
                limit=Decimal("1"),
                observed=Decimal("1.01"),
            ),
        ),
    ],
)
def test_budget_check_preserves_unknown_and_allows_equality(
    cost: Decimal | None,
    expected: ExecutionBudgetViolation | None,
) -> None:
    violation = ExecutionLimitChecker().check_budget(
        budget=ExecutionBudget(max_estimated_cost=Decimal("1.00")),
        usage=Usage(estimated_cost=cost),
    )

    assert violation == expected


def test_deadline_uses_one_absolute_monotonic_instant() -> None:
    now = [10.0]
    deadline = ExecutionDeadline.start(5, clock=lambda: now[0])

    assert deadline.started_at == 10
    assert deadline.deadline_at == 15
    now[0] = 12
    assert deadline.remaining_seconds() == 3
    assert deadline.elapsed_seconds == 2
    assert not deadline.expired
    now[0] = 15
    assert deadline.remaining_seconds() == 0
    assert deadline.expired


async def test_deadline_without_timeout_does_not_wrap_operation() -> None:
    deadline = ExecutionDeadline.start(None)

    assert deadline.remaining_seconds() is None
    assert await deadline.wait_for(lambda: asyncio.sleep(0, result="ok")) == "ok"


async def test_deadline_translates_only_its_own_expiration() -> None:
    deadline = ExecutionDeadline.start(0.001)

    with pytest.raises(ExecutionDeadlineExpiredError):
        await deadline.wait_for(lambda: asyncio.sleep(0.05))

    with pytest.raises(TimeoutError, match="provider"):
        await ExecutionDeadline.start(1).wait_for(_raise_timeout_from_operation)


async def test_expired_deadline_does_not_start_another_operation() -> None:
    now = [1.0]
    called = False
    deadline = ExecutionDeadline.start(1, clock=lambda: now[0])
    now[0] = 2.0

    async def operation() -> None:
        nonlocal called
        called = True

    with pytest.raises(ExecutionDeadlineExpiredError):
        await deadline.wait_for(operation)

    assert not called


async def _raise_timeout_from_operation() -> None:
    raise TimeoutError("provider")
