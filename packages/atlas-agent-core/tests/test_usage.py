"""Tests for provider-neutral usage accounting."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas_agents import Usage


def test_usage_calculates_total_tokens() -> None:
    usage = Usage(
        input_tokens=12,
        output_tokens=8,
        cached_input_tokens=4,
        reasoning_tokens=3,
        estimated_cost=Decimal("0.04"),
    )

    assert usage.total_tokens == 20
    assert usage.cached_input_tokens == 4
    assert usage.reasoning_tokens == 3
    assert usage.estimated_cost == Decimal("0.04")


@pytest.mark.parametrize(
    ("input_tokens", "output_tokens"),
    [(-1, 0), (0, -1)],
)
def test_usage_rejects_negative_token_values(
    input_tokens: int,
    output_tokens: int,
) -> None:
    with pytest.raises(ValidationError):
        Usage(input_tokens=input_tokens, output_tokens=output_tokens)


def test_usage_rejects_negative_cost() -> None:
    with pytest.raises(ValidationError):
        Usage(estimated_cost=Decimal("-0.01"))


@pytest.mark.parametrize("field", ["cached_input_tokens", "reasoning_tokens"])
def test_usage_rejects_negative_specialized_tokens(field: str) -> None:
    with pytest.raises(ValidationError):
        Usage.model_validate({field: -1})


def test_usage_is_immutable() -> None:
    usage = Usage()

    with pytest.raises(ValidationError):
        usage.input_tokens = 1
