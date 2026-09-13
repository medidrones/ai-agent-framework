"""Map provider-neutral Atlas requests to OpenAI Responses parameters."""

import json
from typing import cast
from urllib.parse import urlparse

from openai.types.responses.response_create_params import ResponseCreateParamsBase

from atlas_agents.exceptions import ModelInvalidRequestError
from atlas_agents.models import (
    AudioContent,
    ImageContent,
    MessageRole,
    ModelMessage,
    ModelRequest,
    TextContent,
)


class OpenAIRequestMapper:
    """Build one stateless Responses API payload without forwarding metadata."""

    def __init__(self, *, store_responses: bool) -> None:
        """Set the explicit remote response storage policy."""
        self._store_responses = store_responses

    def map(self, request: ModelRequest) -> ResponseCreateParamsBase:
        """Validate and map one complete Atlas request."""
        self._validate_request(request)
        payload: dict[str, object] = {
            "model": request.model,
            "input": self._messages(request.messages),
            "store": self._store_responses,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            payload["max_output_tokens"] = request.max_output_tokens
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "strict": None,
                }
                for tool in request.tools
            ]
            payload["parallel_tool_calls"] = True
        if request.structured_output is not None:
            definition = request.structured_output
            output_format: dict[str, object] = {
                "type": "json_schema",
                "name": definition.name,
                "schema": definition.json_schema,
                "strict": definition.strict,
            }
            if definition.description is not None:
                output_format["description"] = definition.description
            payload["text"] = {"format": output_format}
        return cast("ResponseCreateParamsBase", payload)

    @staticmethod
    def _validate_request(request: ModelRequest) -> None:
        if request.stop_sequences:
            raise ModelInvalidRequestError(
                "A API Responses não oferece stop_sequences neste adapter.",
                provider="openai",
                model=request.model,
            )
        if request.temperature is not None and request.temperature > 2:
            raise ModelInvalidRequestError(
                "A temperatura da OpenAI deve estar entre 0 e 2.",
                provider="openai",
                model=request.model,
            )

    def _messages(self, messages: tuple[ModelMessage, ...]) -> list[object]:
        mapped: list[object] = []
        for message in messages:
            if message.role is MessageRole.TOOL:
                mapped.append(self._tool_output(message))
                continue
            if message.content:
                mapped.append(
                    {
                        "type": "message",
                        "role": message.role.value,
                        "content": self._content(message),
                    }
                )
            mapped.extend(
                {
                    "type": "function_call",
                    "call_id": tool_call.tool_call_id,
                    "name": tool_call.name,
                    "arguments": json.dumps(
                        tool_call.arguments,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                }
                for tool_call in message.tool_calls
            )
        return mapped

    def _content(self, message: ModelMessage) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for content in message.content:
            if isinstance(content, TextContent):
                result.append({"type": "input_text", "text": content.text})
            elif isinstance(content, ImageContent):
                if message.role is not MessageRole.USER:
                    self._invalid_content(
                        "Imagens são aceitas somente em mensagens de usuário."
                    )
                self._validate_image_uri(content.uri)
                image: dict[str, object] = {
                    "type": "input_image",
                    "image_url": content.uri,
                }
                if content.detail is not None:
                    if content.detail not in {"auto", "low", "high", "original"}:
                        self._invalid_content("O detail da imagem não é suportado.")
                    image["detail"] = content.detail
                result.append(image)
            elif isinstance(content, AudioContent):
                self._invalid_content(
                    "Entrada de áudio não é suportada neste provider."
                )
        return result

    def _tool_output(self, message: ModelMessage) -> dict[str, object]:
        if any(not isinstance(item, TextContent) for item in message.content):
            self._invalid_content("Resultados de ferramenta devem ser textuais.")
        output = "".join(
            item.text for item in message.content if isinstance(item, TextContent)
        )
        return {
            "type": "function_call_output",
            "call_id": message.tool_call_id,
            "output": output,
        }

    @staticmethod
    def _validate_image_uri(uri: str) -> None:
        parsed = urlparse(uri)
        if parsed.scheme == "https" and parsed.netloc:
            return
        if uri.startswith("data:image/") and ";base64," in uri:
            return
        OpenAIRequestMapper._invalid_content(
            "A imagem deve usar uma URL HTTPS ou uma data URL de imagem."
        )

    @staticmethod
    def _invalid_content(message: str) -> None:
        raise ModelInvalidRequestError(message, provider="openai")
