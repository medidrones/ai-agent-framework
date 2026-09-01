"""Tests for structured model streaming events."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from atlas_agents import ModelStreamEvent, ModelStreamEventType


def test_stream_event_types_are_stable() -> None:
    assert tuple(item.value for item in ModelStreamEventType) == (
        "response_started",
        "text_delta",
        "tool_call_started",
        "tool_call_argument_delta",
        "tool_call_completed",
        "usage_updated",
        "response_completed",
        "error",
    )


@pytest.mark.parametrize(
    ("event_type", "data"),
    [
        (ModelStreamEventType.RESPONSE_STARTED, {}),
        (ModelStreamEventType.TEXT_DELTA, {"text": "Olá"}),
        (
            ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA,
            {"tool_call_id": "call-1", "delta": '{"city":'},
        ),
        (ModelStreamEventType.USAGE_UPDATED, {"output_tokens": 2}),
        (ModelStreamEventType.RESPONSE_COMPLETED, {"finish_reason": "stop"}),
    ],
)
def test_stream_events_preserve_structured_data_and_serialize(
    event_type: ModelStreamEventType,
    data: dict[str, object],
) -> None:
    timestamp = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    event = ModelStreamEvent(
        type=event_type,
        sequence=1,
        response_id="response-1",
        data=data,
        timestamp=timestamp,
    )
    data["changed"] = True

    assert "changed" not in event.data
    assert event.timestamp is timestamp
    assert event.model_dump(mode="json")["type"] == event_type.value


def test_stream_event_rejects_zero_sequence_and_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        ModelStreamEvent(
            type=ModelStreamEventType.TEXT_DELTA,
            sequence=0,
            timestamp=datetime.now(UTC),
        )
    with pytest.raises(ValidationError, match="fuso horário"):
        ModelStreamEvent(
            type=ModelStreamEventType.TEXT_DELTA,
            sequence=1,
            timestamp=datetime(2026, 9, 1),
        )


def test_stream_event_is_immutable() -> None:
    event = ModelStreamEvent(
        type=ModelStreamEventType.ERROR,
        sequence=1,
        timestamp=datetime.now(UTC),
    )

    with pytest.raises(ValidationError):
        event.sequence = 2
