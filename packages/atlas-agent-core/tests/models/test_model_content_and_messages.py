"""Tests for multimodal content and model messages."""

import pytest
from pydantic import TypeAdapter, ValidationError

from atlas_agents import (
    AudioContent,
    ImageContent,
    MessageContent,
    MessageRole,
    ModelMessage,
    TextContent,
)


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        ({"type": "text", "text": "Olá"}, TextContent),
        ({"type": "image", "uri": "asset:image"}, ImageContent),
        ({"type": "audio", "uri": "asset:audio"}, AudioContent),
    ],
)
def test_message_content_union_reconstructs_discriminated_type(
    payload: dict[str, object],
    expected_type: type[TextContent] | type[ImageContent] | type[AudioContent],
) -> None:
    adapter: TypeAdapter[MessageContent] = TypeAdapter(MessageContent)
    content: MessageContent = adapter.validate_python(payload)

    assert isinstance(content, expected_type)
    assert content.model_dump(mode="json")["type"] == payload["type"]


def test_multimodal_content_keeps_opaque_references_and_isolates_metadata() -> None:
    image_metadata: dict[str, object] = {"page": 1}
    image = ImageContent(
        uri="data:opaque-image",
        media_type="image/png",
        detail="high",
        metadata=image_metadata,
    )
    audio = AudioContent(uri="storage:audio", media_type="audio/wav")
    image_metadata["page"] = 2

    assert image.uri == "data:opaque-image"
    assert image.metadata == {"page": 1}
    assert audio.type == "audio"
    with pytest.raises(ValidationError):
        image.uri = "other"


def test_text_and_audio_content_are_immutable() -> None:
    text = TextContent(text="Conteúdo")
    metadata: dict[str, object] = {"channel": 1}
    audio = AudioContent(uri="asset:audio", metadata=metadata)
    metadata["channel"] = 2

    assert audio.metadata == {"channel": 1}
    with pytest.raises(ValidationError):
        text.text = "Alterado"
    with pytest.raises(ValidationError):
        audio.uri = "other"


@pytest.mark.parametrize(
    "content",
    [
        {"type": "text", "text": "  "},
        {"type": "image", "uri": ""},
        {"type": "audio", "uri": ""},
    ],
)
def test_content_rejects_empty_primary_values(content: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(MessageContent).validate_python(content)


@pytest.mark.parametrize("role", tuple(MessageRole))
def test_model_message_supports_every_public_role(role: MessageRole) -> None:
    tool_call_id = "call-1" if role is MessageRole.TOOL else None
    message = ModelMessage(
        role=role,
        content=(TextContent(text="Conteúdo"),),
        tool_call_id=tool_call_id,
    )

    assert message.role is role


def test_model_message_supports_multiple_multimodal_items() -> None:
    metadata: dict[str, object] = {"source": "test"}
    message = ModelMessage(
        role=MessageRole.USER,
        content=(
            TextContent(text="Descreva"),
            ImageContent(uri="asset:image"),
            AudioContent(uri="asset:audio"),
        ),
        name="requester",
        metadata=metadata,
    )
    metadata["source"] = "altered"

    assert tuple(item.type for item in message.content) == (
        "text",
        "image",
        "audio",
    )
    assert message.metadata == {"source": "test"}
    assert message.model_dump(mode="json")["role"] == "user"
    with pytest.raises(ValidationError):
        message.role = MessageRole.ASSISTANT


def test_tool_message_requires_tool_call_identifier() -> None:
    with pytest.raises(ValidationError, match="tool_call_id"):
        ModelMessage(role=MessageRole.TOOL, content=(TextContent(text="OK"),))
