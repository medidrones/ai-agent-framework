"""Normative tests for deterministic model stream reconstruction."""

from decimal import Decimal

import pytest

from atlas_agents import (
    FinishReason,
    InvalidModelStreamProtocolError,
    InvalidModelStreamSequenceError,
    ModelStreamAccumulator,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelStreamIncompleteError,
    ModelStreamReportedError,
    TextContent,
    ToolCall,
)


def _event(
    event_type: ModelStreamEventType,
    sequence: int,
    data: dict[str, object] | None = None,
    *,
    response_id: str | None = "response-1",
) -> ModelStreamEvent:
    return ModelStreamEvent(
        type=event_type,
        sequence=sequence,
        response_id=response_id,
        data=data or {},
    )


def _started(sequence: int = 1, *, model: str = "model-a") -> ModelStreamEvent:
    return _event(ModelStreamEventType.RESPONSE_STARTED, sequence, {"model": model})


def _completed(
    sequence: int,
    *,
    finish_reason: str = "stop",
    model: str = "model-a",
    usage: dict[str, object] | None = None,
) -> ModelStreamEvent:
    data: dict[str, object] = {
        "model": model,
        "finish_reason": finish_reason,
    }
    if usage is not None:
        data["usage"] = usage
    return _event(ModelStreamEventType.RESPONSE_COMPLETED, sequence, data)


def test_reconstructs_exact_text_and_uses_last_cumulative_usage_snapshot() -> None:
    accumulator = ModelStreamAccumulator()
    events = (
        _started(),
        _event(ModelStreamEventType.TEXT_DELTA, 2, {"text": "Olá "}),
        _event(ModelStreamEventType.TEXT_DELTA, 3, {"text": ""}),
        _event(ModelStreamEventType.TEXT_DELTA, 4, {"text": "🌎\n"}),
        _event(
            ModelStreamEventType.USAGE_UPDATED,
            5,
            {"usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}},
        ),
        _event(
            ModelStreamEventType.USAGE_UPDATED,
            6,
            {
                "usage": {
                    "input_tokens": 2,
                    "output_tokens": 4,
                    "total_tokens": 6,
                    "estimated_cost": "0.02",
                }
            },
        ),
        _completed(7),
    )

    for event in events:
        accumulator.consume(event)
    response = accumulator.finalize()

    assert response.content == (TextContent(text="Olá 🌎\n"),)
    assert response.usage.total_tokens == 6
    assert response.usage.estimated_cost == Decimal("0.02")
    assert response.finish_reason is FinishReason.STOP


def test_final_usage_replaces_intermediate_snapshot() -> None:
    accumulator = ModelStreamAccumulator()
    accumulator.consume(_started())
    accumulator.consume(
        _event(
            ModelStreamEventType.USAGE_UPDATED,
            2,
            {"usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}},
        )
    )
    accumulator.consume(
        _completed(
            3,
            usage={"input_tokens": 3, "output_tokens": 5, "total_tokens": 8},
        )
    )

    assert accumulator.finalize().usage.total_tokens == 8


def test_supports_interleaved_tool_calls_with_normalized_final_objects() -> None:
    accumulator = ModelStreamAccumulator()
    first = ToolCall(tool_call_id="call-1", name="search", arguments={"q": "a"})
    second = ToolCall(tool_call_id="call-2", name="fetch", arguments={"id": 2})
    events = (
        _started(),
        _event(
            ModelStreamEventType.TOOL_CALL_STARTED,
            2,
            {"tool_call_id": "call-1", "name": "search"},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_STARTED,
            3,
            {"tool_call_id": "call-2", "name": "fetch"},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA,
            4,
            {"tool_call_id": "call-1", "delta": '{"q":'},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA,
            5,
            {"tool_call_id": "call-2", "delta": '{"id":'},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA,
            6,
            {"tool_call_id": "call-1", "delta": '"a"}'},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA,
            7,
            {"tool_call_id": "call-2", "delta": "2}"},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_COMPLETED,
            8,
            {"tool_call": second.model_dump(mode="json")},
        ),
        _event(
            ModelStreamEventType.TOOL_CALL_COMPLETED,
            9,
            {"tool_call": first.model_dump(mode="json")},
        ),
        _completed(10, finish_reason="tool_call"),
    )
    for event in events:
        accumulator.consume(event)

    response = accumulator.finalize()

    assert response.tool_calls == (first, second)
    assert response.finish_reason is FinishReason.TOOL_CALL
    assert response.model_dump(mode="json")["finish_reason"] == "tool_call"


@pytest.mark.parametrize("sequence", [2, 3])
def test_rejects_invalid_initial_sequence(sequence: int) -> None:
    accumulator = ModelStreamAccumulator()

    with pytest.raises(InvalidModelStreamSequenceError) as captured:
        accumulator.consume(_started(sequence))

    assert captured.value.expected == 1
    assert captured.value.received == sequence


def test_rejects_gap_duplicate_and_event_before_start() -> None:
    gap = ModelStreamAccumulator()
    gap.consume(_started())
    with pytest.raises(InvalidModelStreamSequenceError):
        gap.consume(_completed(3))

    duplicate = ModelStreamAccumulator()
    duplicate.consume(_started())
    with pytest.raises(InvalidModelStreamSequenceError):
        duplicate.consume(_completed(1))

    before_start = ModelStreamAccumulator()
    with pytest.raises(InvalidModelStreamProtocolError):
        before_start.consume(_event(ModelStreamEventType.TEXT_DELTA, 1, {"text": "x"}))


def test_rejects_events_after_terminal_and_incomplete_stream() -> None:
    accumulator = ModelStreamAccumulator()
    accumulator.consume(_started())
    accumulator.consume(_completed(2))
    with pytest.raises(InvalidModelStreamProtocolError):
        accumulator.consume(_completed(3))

    with pytest.raises(ModelStreamIncompleteError):
        ModelStreamAccumulator().finalize()


def test_rejects_duplicate_response_started_event() -> None:
    accumulator = ModelStreamAccumulator()
    accumulator.consume(_started())

    with pytest.raises(InvalidModelStreamProtocolError):
        accumulator.consume(_started(2))


def test_rejects_response_and_model_identity_changes() -> None:
    response_change = ModelStreamAccumulator()
    response_change.consume(_started())
    with pytest.raises(InvalidModelStreamProtocolError):
        response_change.consume(
            _event(
                ModelStreamEventType.TEXT_DELTA,
                2,
                {"text": "x"},
                response_id="response-2",
            )
        )

    model_change = ModelStreamAccumulator()
    model_change.consume(_started())
    with pytest.raises(InvalidModelStreamProtocolError):
        model_change.consume(_completed(2, model="model-b"))


def test_error_event_is_terminal_and_surfaces_provider_message() -> None:
    accumulator = ModelStreamAccumulator()
    accumulator.consume(_started())
    accumulator.consume(
        _event(ModelStreamEventType.ERROR, 2, {"message": "Falha controlada"})
    )

    with pytest.raises(ModelStreamReportedError, match="Falha controlada"):
        accumulator.finalize()


@pytest.mark.parametrize(
    ("event"),
    [
        _event(ModelStreamEventType.TEXT_DELTA, 2, {"text": 1}),
        _event(ModelStreamEventType.USAGE_UPDATED, 2, {"usage": "invalid"}),
        _event(
            ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA,
            2,
            {"tool_call_id": "missing", "delta": "{}"},
        ),
        _event(ModelStreamEventType.TOOL_CALL_COMPLETED, 2, {"tool_call": {}}),
        _completed(2, finish_reason="nonstandard"),
    ],
)
def test_rejects_malformed_or_out_of_order_payloads(event: ModelStreamEvent) -> None:
    accumulator = ModelStreamAccumulator()
    accumulator.consume(_started())

    with pytest.raises(InvalidModelStreamProtocolError):
        accumulator.consume(event)


def test_rejects_incomplete_tool_call_at_finalization() -> None:
    accumulator = ModelStreamAccumulator()
    accumulator.consume(_started())
    accumulator.consume(
        _event(
            ModelStreamEventType.TOOL_CALL_STARTED,
            2,
            {"tool_call_id": "call-1", "name": "search"},
        )
    )
    accumulator.consume(_completed(3, finish_reason="tool_call"))

    with pytest.raises(InvalidModelStreamProtocolError):
        accumulator.finalize()


def test_rejects_duplicate_tool_start_and_completion_without_start() -> None:
    duplicate = ModelStreamAccumulator()
    duplicate.consume(_started())
    duplicate.consume(
        _event(
            ModelStreamEventType.TOOL_CALL_STARTED,
            2,
            {"tool_call_id": "call-1", "name": "search"},
        )
    )
    with pytest.raises(InvalidModelStreamProtocolError):
        duplicate.consume(
            _event(
                ModelStreamEventType.TOOL_CALL_STARTED,
                3,
                {"tool_call_id": "call-1", "name": "search"},
            )
        )

    no_start = ModelStreamAccumulator()
    no_start.consume(_started())
    tool_call = ToolCall(tool_call_id="call-1", name="search", arguments={})
    with pytest.raises(InvalidModelStreamProtocolError):
        no_start.consume(
            _event(
                ModelStreamEventType.TOOL_CALL_COMPLETED,
                2,
                {"tool_call": tool_call.model_dump(mode="json")},
            )
        )


def test_rejects_tool_call_finish_without_completed_calls() -> None:
    accumulator = ModelStreamAccumulator()
    accumulator.consume(_started())
    accumulator.consume(_completed(2, finish_reason="tool_call"))

    with pytest.raises(InvalidModelStreamProtocolError):
        accumulator.finalize()


def test_defaults_to_zero_usage_when_provider_does_not_report_it() -> None:
    accumulator = ModelStreamAccumulator()
    accumulator.consume(_started())
    accumulator.consume(_event(ModelStreamEventType.TEXT_DELTA, 2, {"text": "ok"}))
    accumulator.consume(_completed(3))

    assert accumulator.finalize().usage.total_tokens == 0
