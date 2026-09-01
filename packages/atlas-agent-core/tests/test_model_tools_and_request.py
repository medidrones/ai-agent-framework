"""Tests for model tool, structured output, and request contracts."""

import pytest
from pydantic import ValidationError

from atlas_agents import (
    ImageContent,
    MessageRole,
    ModelMessage,
    ModelRequest,
    ModelToolDefinition,
    StructuredOutputDefinition,
    TextContent,
    ToolCall,
)


def _message() -> ModelMessage:
    return ModelMessage(
        role=MessageRole.USER,
        content=(TextContent(text="Olá"),),
    )


def test_tool_call_uses_structured_arguments_and_isolates_data() -> None:
    arguments: dict[str, object] = {"customer_id": "123"}
    metadata: dict[str, object] = {"provider_hint": "opaque"}
    call = ToolCall(
        tool_call_id="call-1",
        name="find_customer",
        arguments=arguments,
        metadata=metadata,
    )
    arguments["customer_id"] = "changed"
    metadata["provider_hint"] = "changed"

    assert call.arguments == {"customer_id": "123"}
    assert call.metadata == {"provider_hint": "opaque"}
    assert call.model_dump(mode="json")["arguments"] == {"customer_id": "123"}


@pytest.mark.parametrize("field", ["tool_call_id", "name"])
def test_tool_call_rejects_empty_identifiers(field: str) -> None:
    data: dict[str, object] = {
        "tool_call_id": "call-1",
        "name": "tool",
        "arguments": {},
    }
    data[field] = ""

    with pytest.raises(ValidationError):
        ToolCall.model_validate(data)


def test_model_tool_and_structured_output_isolate_json_schemas() -> None:
    parameters: dict[str, object] = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
    }
    output_schema: dict[str, object] = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
    }
    tool = ModelToolDefinition(
        name="weather",
        description="Consulta o clima.",
        parameters=parameters,
    )
    output = StructuredOutputDefinition(
        name="answer",
        description="Resposta estruturada.",
        json_schema=output_schema,
    )
    parameters["type"] = "array"
    output_schema["type"] = "array"

    assert tool.parameters["type"] == "object"
    assert output.json_schema["type"] == "object"
    assert output.strict
    assert output.model_dump(mode="json")["strict"] is True


def test_simple_and_multimodal_model_requests_are_immutable() -> None:
    simple = ModelRequest(model="model", messages=(_message(),))
    multimodal = ModelRequest(
        model="model",
        messages=(
            ModelMessage(
                role=MessageRole.USER,
                content=(
                    TextContent(text="Observe"),
                    ImageContent(uri="asset:image"),
                ),
            ),
        ),
        temperature=0.7,
        max_output_tokens=500,
        stop_sequences=("FIM",),
    )

    assert simple.tools == ()
    assert len(multimodal.messages[0].content) == 2
    with pytest.raises(ValidationError):
        multimodal.model = "other"


def test_model_request_supports_tools_and_structured_output() -> None:
    tool = ModelToolDefinition(
        name="weather",
        description="Consulta o clima.",
        parameters={"type": "object"},
    )
    output = StructuredOutputDefinition(
        name="answer",
        json_schema={"type": "object"},
    )
    request = ModelRequest(
        model="model",
        messages=(_message(),),
        tools=(tool,),
        structured_output=output,
    )

    assert request.tools == (tool,)
    assert request.structured_output is output


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_output_tokens", 0),
        ("max_output_tokens", -1),
        ("temperature", -0.1),
        ("temperature", float("inf")),
        ("temperature", float("nan")),
    ],
)
def test_model_request_rejects_invalid_generation_values(
    field: str,
    value: int | float,
) -> None:
    data: dict[str, object] = {"model": "model", "messages": (_message(),)}
    data[field] = value

    with pytest.raises(ValidationError):
        ModelRequest.model_validate(data)


def test_model_request_rejects_empty_messages_and_stop_sequences() -> None:
    with pytest.raises(ValidationError):
        ModelRequest(model="model", messages=())
    with pytest.raises(ValidationError):
        ModelRequest(model="model", messages=(_message(),), stop_sequences=("",))
