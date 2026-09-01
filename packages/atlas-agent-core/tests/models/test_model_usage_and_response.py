"""Tests for per-call model usage and complete responses."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas_agents import (
    FinishReason,
    ModelResponse,
    ModelUsage,
    TextContent,
    ToolCall,
)


def test_model_usage_accepts_zero_and_consistent_positive_counts() -> None:
    zero = ModelUsage()
    metadata: dict[str, object] = {"source": "reported"}
    positive = ModelUsage(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        cached_input_tokens=3,
        reasoning_tokens=2,
        estimated_cost=Decimal("0.012"),
        metadata=metadata,
    )
    metadata["source"] = "changed"

    assert zero.total_tokens == 0
    assert positive.total_tokens == 15
    assert positive.cached_input_tokens == 3
    assert positive.reasoning_tokens == 2
    assert positive.estimated_cost == Decimal("0.012")
    assert positive.metadata == {"source": "reported"}
    assert positive.model_dump(mode="json")["total_tokens"] == 15
    with pytest.raises(ValidationError):
        positive.total_tokens = 0


@pytest.mark.parametrize(
    "data",
    [
        {"input_tokens": -1},
        {"output_tokens": -1},
        {"total_tokens": -1},
        {"cached_input_tokens": -1},
        {"reasoning_tokens": -1},
        {"estimated_cost": Decimal("-0.01")},
        {"input_tokens": 2, "output_tokens": 3, "total_tokens": 4},
    ],
)
def test_model_usage_rejects_negative_or_inconsistent_values(
    data: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ModelUsage.model_validate(data)


def test_stop_and_length_responses_preserve_content() -> None:
    complete = ModelResponse(
        response_id="response-1",
        model="model",
        content=(TextContent(text="Resposta"),),
        finish_reason=FinishReason.STOP,
        usage=ModelUsage(input_tokens=2, output_tokens=1, total_tokens=3),
    )
    partial = ModelResponse(
        model="model",
        content=(TextContent(text="Parcial"),),
        finish_reason=FinishReason.LENGTH,
        usage=ModelUsage(),
    )

    assert isinstance(complete.content[0], TextContent)
    assert isinstance(partial.content[0], TextContent)
    assert complete.content[0].text == "Resposta"
    assert partial.content[0].text == "Parcial"


def test_tool_call_response_accepts_calls_with_simultaneous_content() -> None:
    call = ToolCall(
        tool_call_id="call-1",
        name="weather",
        arguments={"city": "Recife"},
    )
    response = ModelResponse(
        model="model",
        content=(TextContent(text="Vou consultar."),),
        tool_calls=(call,),
        finish_reason=FinishReason.TOOL_CALL,
        usage=ModelUsage(),
    )

    assert response.tool_calls == (call,)
    assert response.content
    assert response.model_dump(mode="json")["finish_reason"] == "tool_call"


def test_tool_call_response_accepts_multiple_calls() -> None:
    calls = tuple(
        ToolCall(tool_call_id=f"call-{index}", name="tool", arguments={})
        for index in (1, 2)
    )
    response = ModelResponse(
        model="model",
        tool_calls=calls,
        finish_reason=FinishReason.TOOL_CALL,
        usage=ModelUsage(),
    )

    assert response.tool_calls == calls


def test_stop_response_may_have_no_content() -> None:
    response = ModelResponse(
        model="model",
        finish_reason=FinishReason.STOP,
        usage=ModelUsage(),
    )

    assert response.content == ()


def test_tool_call_finish_requires_at_least_one_call() -> None:
    with pytest.raises(ValidationError, match="tool call"):
        ModelResponse(
            model="model",
            finish_reason=FinishReason.TOOL_CALL,
            usage=ModelUsage(),
        )


def test_model_response_is_immutable_and_isolates_metadata() -> None:
    metadata: dict[str, object] = {"trace": "opaque"}
    response = ModelResponse(
        model="model",
        finish_reason=FinishReason.STOP,
        usage=ModelUsage(),
        metadata=metadata,
    )
    metadata["trace"] = "changed"

    assert response.metadata == {"trace": "opaque"}
    with pytest.raises(ValidationError):
        response.model = "other"
