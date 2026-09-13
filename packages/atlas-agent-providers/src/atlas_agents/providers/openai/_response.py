"""Map OpenAI Responses objects to provider-neutral Atlas responses."""

import json
from collections.abc import Mapping
from typing import cast

from atlas_agents.exceptions import ModelResponseError
from atlas_agents.models import (
    FinishReason,
    ModelResponse,
    ModelUsage,
    TextContent,
    ToolCall,
)


def read_field(value: object, name: str, default: object = None) -> object:
    """Read one SDK model or test-double field without serializing the object."""
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def read_string(value: object, name: str, default: str = "") -> str:
    """Read a string field or return the safe default."""
    result = read_field(value, name, default)
    return result if isinstance(result, str) else default


class OpenAIResponseMapper:
    """Convert complete Responses API results without exposing SDK objects."""

    def map(self, response: object, *, requested_model: str) -> ModelResponse:
        """Map one complete provider response or reject malformed output."""
        status = read_string(response, "status")
        if status == "failed" or read_field(response, "error") is not None:
            raise ModelResponseError(
                "A OpenAI informou falha ao gerar a resposta.",
                provider="openai",
                model=requested_model,
            )
        contents: list[TextContent] = []
        tool_calls: list[ToolCall] = []
        refusal = False
        raw_output = read_field(response, "output", ())
        if not isinstance(raw_output, (list, tuple)):
            self._malformed(requested_model)
        for item in cast("list[object] | tuple[object, ...]", raw_output):
            item_type = read_string(item, "type")
            if item_type == "message":
                raw_content = read_field(item, "content", ())
                if not isinstance(raw_content, (list, tuple)):
                    self._malformed(requested_model)
                for part in cast("list[object] | tuple[object, ...]", raw_content):
                    part_type = read_string(part, "type")
                    if part_type == "output_text":
                        text = read_string(part, "text")
                        if text:
                            contents.append(TextContent(text=text))
                    elif part_type == "refusal":
                        refusal = True
            elif item_type == "function_call":
                tool_calls.append(self.map_tool_call(item, requested_model))
            elif item_type not in {"reasoning", "compaction"}:
                self._malformed(requested_model)
        finish_reason = self.finish_reason(
            response,
            has_tool_calls=bool(tool_calls),
            has_refusal=refusal,
        )
        return ModelResponse(
            response_id=read_string(response, "id") or None,
            model=read_string(response, "model", requested_model) or requested_model,
            content=tuple(contents),
            tool_calls=tuple(tool_calls),
            finish_reason=finish_reason,
            usage=self.map_usage(read_field(response, "usage")),
        )

    @staticmethod
    def map_tool_call(item: object, requested_model: str) -> ToolCall:
        """Parse one function call and require JSON object arguments."""
        call_id = read_string(item, "call_id")
        name = read_string(item, "name")
        raw_arguments = read_string(item, "arguments")
        try:
            arguments = json.loads(raw_arguments)
        except (json.JSONDecodeError, TypeError):
            raise ModelResponseError(
                "A OpenAI retornou argumentos de ferramenta com JSON inválido.",
                provider="openai",
                model=requested_model,
            ) from None
        if not call_id or not name or not isinstance(arguments, dict):
            raise ModelResponseError(
                "A OpenAI retornou uma chamada de ferramenta inválida.",
                provider="openai",
                model=requested_model,
            )
        return ToolCall(tool_call_id=call_id, name=name, arguments=arguments)

    @staticmethod
    def map_usage(raw_usage: object) -> ModelUsage:
        """Map only usage counters explicitly reported by the provider."""
        if raw_usage is None:
            return ModelUsage()
        input_tokens = read_field(raw_usage, "input_tokens", 0)
        output_tokens = read_field(raw_usage, "output_tokens", 0)
        total_tokens = read_field(raw_usage, "total_tokens", 0)
        input_details = read_field(raw_usage, "input_tokens_details")
        output_details = read_field(raw_usage, "output_tokens_details")
        values = (input_tokens, output_tokens, total_tokens)
        if any(not isinstance(item, int) or isinstance(item, bool) for item in values):
            raise ModelResponseError(
                "A OpenAI retornou usage inválido.", provider="openai"
            )
        input_count = cast("int", input_tokens)
        output_count = cast("int", output_tokens)
        total_count = cast("int", total_tokens)
        if total_count != input_count + output_count:
            raise ModelResponseError(
                "A OpenAI retornou um total de tokens inconsistente.",
                provider="openai",
            )
        cached = read_field(input_details, "cached_tokens", 0)
        reasoning = read_field(output_details, "reasoning_tokens", 0)
        cached = (
            cached if isinstance(cached, int) and not isinstance(cached, bool) else 0
        )
        reasoning = (
            reasoning
            if isinstance(reasoning, int) and not isinstance(reasoning, bool)
            else 0
        )
        return ModelUsage(
            input_tokens=input_count,
            output_tokens=output_count,
            total_tokens=total_count,
            cached_input_tokens=cached,
            reasoning_tokens=reasoning,
        )

    @staticmethod
    def finish_reason(
        response: object,
        *,
        has_tool_calls: bool,
        has_refusal: bool,
    ) -> FinishReason:
        """Normalize status and incomplete details with deterministic priority."""
        if has_tool_calls:
            return FinishReason.TOOL_CALL
        if has_refusal:
            return FinishReason.CONTENT_FILTER
        status = read_string(response, "status")
        incomplete = read_field(response, "incomplete_details")
        reason = read_string(incomplete, "reason")
        if status == "completed":
            return FinishReason.STOP
        if status == "incomplete" and reason == "max_output_tokens":
            return FinishReason.LENGTH
        if status == "incomplete" and reason in {"content_filter", "safety"}:
            return FinishReason.CONTENT_FILTER
        if status == "cancelled":
            return FinishReason.CANCELLED
        return FinishReason.UNKNOWN

    @staticmethod
    def _malformed(model: str) -> None:
        raise ModelResponseError(
            "A OpenAI retornou uma resposta em formato inesperado.",
            provider="openai",
            model=model,
        )
