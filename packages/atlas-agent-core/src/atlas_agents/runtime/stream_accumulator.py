"""Deterministic reconstruction of complete responses from model stream events."""

from dataclasses import dataclass

from pydantic import ValidationError

from atlas_agents.models import (
    FinishReason,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelUsage,
    TextContent,
    ToolCall,
)
from atlas_agents.runtime.errors import (
    InvalidModelStreamProtocolError,
    InvalidModelStreamSequenceError,
    ModelStreamIncompleteError,
    ModelStreamReportedError,
)


@dataclass
class _PendingToolCall:
    name: str
    argument_fragments: list[str]
    completed: ToolCall | None = None


class ModelStreamAccumulator:
    """Validate one model stream and reconstruct its final response."""

    def __init__(self) -> None:
        """Initialize isolated mutable protocol state for one model invocation."""
        self._next_sequence = 1
        self._started = False
        self._terminal: ModelStreamEventType | None = None
        self._response_id: str | None = None
        self._model: str | None = None
        self._text_fragments: list[str] = []
        self._tool_calls: dict[str, _PendingToolCall] = {}
        self._usage = ModelUsage()
        self._finish_reason: FinishReason | None = None
        self._error_message: str | None = None

    @property
    def is_terminal(self) -> bool:
        """Return whether a completed or error terminal event was consumed."""
        return self._terminal is not None

    def consume(self, event: ModelStreamEvent) -> None:
        """Validate and apply exactly one ordered model stream event."""
        if self._terminal is not None:
            raise InvalidModelStreamProtocolError(
                "O stream de modelo não aceita eventos após o terminal."
            )
        if event.sequence != self._next_sequence:
            raise InvalidModelStreamSequenceError(
                expected=self._next_sequence,
                received=event.sequence,
            )
        if (
            not self._started
            and event.type is not ModelStreamEventType.RESPONSE_STARTED
        ):
            raise InvalidModelStreamProtocolError(
                "O primeiro evento do stream deve ser response_started."
            )

        self._validate_response_id(event.response_id)
        self._consume_by_type(event)
        self._next_sequence += 1

    def finalize(self) -> ModelResponse:
        """Build a response only after one successful terminal completion event."""
        if self._terminal is None:
            raise ModelStreamIncompleteError(
                "O stream de modelo terminou sem evento terminal."
            )
        if self._terminal is ModelStreamEventType.ERROR:
            raise ModelStreamReportedError(
                self._error_message or "O provider encerrou o stream com erro."
            )
        if self._model is None or self._finish_reason is None:
            raise InvalidModelStreamProtocolError(
                "O evento response_completed deve informar model e finish_reason."
            )
        incomplete_calls = [
            tool_call_id
            for tool_call_id, pending in self._tool_calls.items()
            if pending.completed is None
        ]
        if incomplete_calls:
            raise InvalidModelStreamProtocolError(
                "Todas as tool calls iniciadas devem ser concluídas."
            )
        text = "".join(self._text_fragments)
        content = (TextContent(text=text),) if text else ()
        tool_calls = tuple(
            pending.completed
            for pending in self._tool_calls.values()
            if pending.completed is not None
        )
        try:
            return ModelResponse(
                response_id=self._response_id,
                model=self._model,
                content=content,
                tool_calls=tool_calls,
                finish_reason=self._finish_reason,
                usage=self._usage,
            )
        except ValidationError as exc:
            raise InvalidModelStreamProtocolError(
                "O stream não representa uma resposta final válida."
            ) from exc

    def _consume_by_type(self, event: ModelStreamEvent) -> None:
        if event.type is ModelStreamEventType.RESPONSE_STARTED:
            if self._started:
                raise InvalidModelStreamProtocolError(
                    "response_started deve ocorrer exatamente uma vez."
                )
            self._started = True
            self._set_model(self._optional_string(event.data, "model"))
        elif event.type is ModelStreamEventType.TEXT_DELTA:
            self._text_fragments.append(self._required_string(event.data, "text"))
        elif event.type is ModelStreamEventType.TOOL_CALL_STARTED:
            self._start_tool_call(event.data)
        elif event.type is ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA:
            self._append_tool_delta(event.data)
        elif event.type is ModelStreamEventType.TOOL_CALL_COMPLETED:
            self._complete_tool_call(event.data)
        elif event.type is ModelStreamEventType.USAGE_UPDATED:
            self._usage = self._parse_usage(event.data)
        elif event.type is ModelStreamEventType.RESPONSE_COMPLETED:
            self._complete_response(event.data)
        elif event.type is ModelStreamEventType.ERROR:
            self._terminal = ModelStreamEventType.ERROR
            self._error_message = self._optional_string(event.data, "message")

    def _validate_response_id(self, response_id: str | None) -> None:
        if response_id is None:
            return
        if self._response_id is None:
            self._response_id = response_id
        elif self._response_id != response_id:
            raise InvalidModelStreamProtocolError(
                "O response_id não pode mudar durante o stream."
            )

    def _set_model(self, model: str | None) -> None:
        if model is None:
            return
        if self._model is None:
            self._model = model
        elif self._model != model:
            raise InvalidModelStreamProtocolError(
                "A identidade do modelo não pode mudar durante o stream."
            )

    def _start_tool_call(self, data: dict[str, object]) -> None:
        tool_call_id = self._required_string(data, "tool_call_id")
        name = self._required_string(data, "name")
        if tool_call_id in self._tool_calls:
            raise InvalidModelStreamProtocolError(
                "Uma tool call não pode ser iniciada mais de uma vez."
            )
        self._tool_calls[tool_call_id] = _PendingToolCall(name, [])

    def _append_tool_delta(self, data: dict[str, object]) -> None:
        tool_call_id = self._required_string(data, "tool_call_id")
        pending = self._tool_calls.get(tool_call_id)
        if pending is None or pending.completed is not None:
            raise InvalidModelStreamProtocolError(
                "O delta deve referenciar uma tool call ativa."
            )
        pending.argument_fragments.append(self._required_string(data, "delta"))

    def _complete_tool_call(self, data: dict[str, object]) -> None:
        raw_tool_call = data.get("tool_call")
        if not isinstance(raw_tool_call, dict):
            raise InvalidModelStreamProtocolError(
                "tool_call_completed deve conter uma tool_call estruturada."
            )
        try:
            tool_call = ToolCall.model_validate(raw_tool_call)
        except ValidationError as exc:
            raise InvalidModelStreamProtocolError(
                "A tool call final do stream é inválida."
            ) from exc
        pending = self._tool_calls.get(tool_call.tool_call_id)
        if pending is None or pending.completed is not None:
            raise InvalidModelStreamProtocolError(
                "A tool call deve ser iniciada exatamente uma vez antes de concluir."
            )
        if pending.name != tool_call.name:
            raise InvalidModelStreamProtocolError(
                "O nome da tool call não pode mudar durante o stream."
            )
        pending.completed = tool_call

    def _complete_response(self, data: dict[str, object]) -> None:
        self._set_model(self._required_string(data, "model"))
        raw_finish_reason = self._required_string(data, "finish_reason")
        try:
            self._finish_reason = FinishReason(raw_finish_reason)
        except ValueError as exc:
            raise InvalidModelStreamProtocolError(
                "O finish_reason do stream não é reconhecido."
            ) from exc
        raw_usage = data.get("usage")
        if raw_usage is not None:
            if not isinstance(raw_usage, dict):
                raise InvalidModelStreamProtocolError(
                    "O usage final do stream deve ser estruturado."
                )
            self._usage = self._validate_usage(raw_usage)
        self._terminal = ModelStreamEventType.RESPONSE_COMPLETED

    def _parse_usage(self, data: dict[str, object]) -> ModelUsage:
        raw_usage = data.get("usage")
        if not isinstance(raw_usage, dict):
            raise InvalidModelStreamProtocolError(
                "usage_updated deve conter um snapshot de usage estruturado."
            )
        return self._validate_usage(raw_usage)

    @staticmethod
    def _validate_usage(value: dict[str, object]) -> ModelUsage:
        try:
            return ModelUsage.model_validate(value)
        except ValidationError as exc:
            raise InvalidModelStreamProtocolError(
                "O snapshot de usage do stream é inválido."
            ) from exc

    @staticmethod
    def _required_string(data: dict[str, object], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str):
            raise InvalidModelStreamProtocolError(
                f"O campo '{key}' deve ser uma string no protocolo de streaming."
            )
        return value

    @staticmethod
    def _optional_string(data: dict[str, object], key: str) -> str | None:
        value = data.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise InvalidModelStreamProtocolError(
                f"O campo opcional '{key}' deve ser uma string."
            )
        return value
