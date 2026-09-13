"""Incrementally map OpenAI Responses events to the Atlas stream protocol."""

from dataclasses import dataclass, field

from atlas_agents.models import (
    ModelStreamEvent,
    ModelStreamEventType,
)
from atlas_agents.providers.openai._response import (
    OpenAIResponseMapper,
    read_field,
    read_string,
)


@dataclass(slots=True)
class _PendingCall:
    call_id: str
    name: str
    fragments: list[str] = field(default_factory=list)
    completed: bool = False


class OpenAIStreamMapper:
    """Keep isolated state for exactly one Responses streaming invocation."""

    def __init__(self, *, requested_model: str) -> None:
        """Initialize a fresh sequence and function-call assembly map."""
        self._requested_model = requested_model
        self._sequence = 0
        self._response_id: str | None = None
        self._model = requested_model
        self._model_captured = False
        self._started = False
        self._terminal = False
        self._calls_by_item: dict[str, _PendingCall] = {}
        self._calls_by_id: dict[str, _PendingCall] = {}
        self._has_tool_calls = False
        self._has_refusal = False
        self._response_mapper = OpenAIResponseMapper()

    def map(self, event: object) -> tuple[ModelStreamEvent, ...]:
        """Map one SDK event to zero or more ordered Atlas events."""
        if self._terminal:
            return ()
        event_type = read_string(event, "type")
        if event_type == "response.created":
            if self._started:
                return self._protocol_error()
            response = read_field(event, "response")
            if not self._capture_response(response):
                return self._start() + self._protocol_error()
            return self._start()
        prefix = self._start() if not self._started else ()
        return prefix + self._map_started(event_type, event)

    def _map_started(
        self, event_type: str, event: object
    ) -> tuple[ModelStreamEvent, ...]:
        """Map an event after guaranteeing a valid Atlas start event."""
        if event_type == "response.output_text.delta":
            return (
                self._emit(
                    ModelStreamEventType.TEXT_DELTA,
                    {"text": read_string(event, "delta")},
                ),
            )
        if event_type == "response.refusal.delta":
            self._has_refusal = True
            return ()
        if event_type == "response.output_item.added":
            return self._output_item_added(event)
        if event_type == "response.function_call_arguments.delta":
            return self._argument_delta(event)
        if event_type == "response.function_call_arguments.done":
            return self._arguments_done(event)
        if event_type == "response.output_item.done":
            return self._output_item_done(event)
        if event_type == "response.completed":
            return self._complete(read_field(event, "response"))
        if event_type == "response.incomplete":
            return self._complete(read_field(event, "response"))
        if event_type in {"response.failed", "error"}:
            response = read_field(event, "response")
            if not self._capture_response(response):
                return self._protocol_error()
            self._terminal = True
            return (
                self._emit(
                    ModelStreamEventType.ERROR,
                    {"message": "A OpenAI encerrou o stream com erro."},
                ),
            )
        return ()

    def _output_item_added(self, event: object) -> tuple[ModelStreamEvent, ...]:
        item = read_field(event, "item")
        if read_string(item, "type") != "function_call":
            return ()
        item_id = read_string(item, "id") or read_string(event, "item_id")
        call_id = read_string(item, "call_id")
        name = read_string(item, "name")
        if not item_id or not call_id or not name or call_id in self._calls_by_id:
            return self._protocol_error()
        pending = _PendingCall(call_id=call_id, name=name)
        self._calls_by_item[item_id] = pending
        self._calls_by_id[call_id] = pending
        self._has_tool_calls = True
        return (
            self._emit(
                ModelStreamEventType.TOOL_CALL_STARTED,
                {"tool_call_id": call_id, "name": name},
            ),
        )

    def _argument_delta(self, event: object) -> tuple[ModelStreamEvent, ...]:
        pending = self._pending(event)
        delta = read_string(event, "delta")
        if pending is None or pending.completed:
            return self._protocol_error()
        pending.fragments.append(delta)
        return (
            self._emit(
                ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA,
                {"tool_call_id": pending.call_id, "delta": delta},
            ),
        )

    def _arguments_done(self, event: object) -> tuple[ModelStreamEvent, ...]:
        pending = self._pending(event)
        if pending is None or pending.completed:
            return self._protocol_error()
        arguments = read_string(event, "arguments") or "".join(pending.fragments)
        return self._complete_call(pending, arguments)

    def _output_item_done(self, event: object) -> tuple[ModelStreamEvent, ...]:
        item = read_field(event, "item")
        if read_string(item, "type") != "function_call":
            return ()
        pending = self._pending(event, item=item)
        if pending is None:
            return self._protocol_error()
        if pending.completed:
            return ()
        return self._complete_call(pending, read_string(item, "arguments"))

    def _complete_call(
        self, pending: _PendingCall, arguments: str
    ) -> tuple[ModelStreamEvent, ...]:
        try:
            tool_call = self._response_mapper.map_tool_call(
                {
                    "call_id": pending.call_id,
                    "name": pending.name,
                    "arguments": arguments,
                },
                self._requested_model,
            )
        except Exception:
            return self._protocol_error()
        pending.completed = True
        return (
            self._emit(
                ModelStreamEventType.TOOL_CALL_COMPLETED,
                {"tool_call": tool_call.model_dump(mode="json")},
            ),
        )

    def _complete(self, response: object) -> tuple[ModelStreamEvent, ...]:
        if not self._capture_response(response):
            return self._protocol_error()
        unfinished = [call for call in self._calls_by_id.values() if not call.completed]
        if unfinished:
            return self._protocol_error()
        usage = self._response_mapper.map_usage(read_field(response, "usage"))
        finish_reason = self._response_mapper.finish_reason(
            response,
            has_tool_calls=self._has_tool_calls,
            has_refusal=self._has_refusal,
        )
        events: list[ModelStreamEvent] = []
        if read_field(response, "usage") is not None:
            events.append(
                self._emit(
                    ModelStreamEventType.USAGE_UPDATED,
                    {"usage": usage.model_dump(mode="json")},
                )
            )
        events.append(
            self._emit(
                ModelStreamEventType.RESPONSE_COMPLETED,
                {
                    "model": self._model,
                    "finish_reason": finish_reason.value,
                    "usage": usage.model_dump(mode="json"),
                },
            )
        )
        self._terminal = True
        return tuple(events)

    def _pending(
        self, event: object, *, item: object | None = None
    ) -> _PendingCall | None:
        item_id = read_string(event, "item_id")
        if not item_id and item is not None:
            item_id = read_string(item, "id")
        if item_id:
            return self._calls_by_item.get(item_id)
        call_id = read_string(item if item is not None else event, "call_id")
        return self._calls_by_id.get(call_id)

    def _capture_response(self, response: object) -> bool:
        response_id = read_string(response, "id")
        model = read_string(response, "model")
        if response_id:
            if self._response_id is not None and self._response_id != response_id:
                return False
            self._response_id = response_id
        if model:
            if self._model_captured and self._model != model:
                return False
            self._model = model
            self._model_captured = True
        return True

    def _start(self) -> tuple[ModelStreamEvent, ...]:
        self._started = True
        data: dict[str, object] = {}
        if self._model_captured:
            data["model"] = self._model
        return (self._emit(ModelStreamEventType.RESPONSE_STARTED, data),)

    def _protocol_error(self) -> tuple[ModelStreamEvent, ...]:
        self._terminal = True
        return (
            self._emit(
                ModelStreamEventType.ERROR,
                {"message": "A OpenAI retornou um stream inconsistente."},
            ),
        )

    def _emit(
        self, event_type: ModelStreamEventType, data: dict[str, object]
    ) -> ModelStreamEvent:
        self._sequence += 1
        return ModelStreamEvent(
            type=event_type,
            sequence=self._sequence,
            response_id=self._response_id,
            data=data,
        )
