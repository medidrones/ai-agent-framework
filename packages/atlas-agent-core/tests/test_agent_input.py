"""Tests for generic agent inputs and attachment references."""

import pytest
from pydantic import ValidationError

from atlas_agents import AgentAttachment, AgentInput


def test_agent_input_accepts_opaque_attachments() -> None:
    attachment = AgentAttachment(
        attachment_id="document-1",
        name="document.txt",
        media_type="text/plain",
        uri="connector://documents/1",
    )

    input_data = AgentInput(message="Summarize this.", attachments=(attachment,))

    assert input_data.attachments == (attachment,)


def test_agent_input_defaults_are_empty_and_isolated() -> None:
    first = AgentInput(message="First")
    second = AgentInput(message="Second")

    first.metadata["request"] = 1

    assert first.attachments == ()
    assert second.attachments == ()
    assert second.metadata == {}


def test_agent_attachment_rejects_blank_identifier() -> None:
    with pytest.raises(ValidationError):
        AgentAttachment(
            attachment_id=" ",
            name="document.txt",
            media_type="text/plain",
            uri="memory://document",
        )


def test_agent_attachment_is_immutable() -> None:
    attachment = AgentAttachment(
        attachment_id="document",
        name="document.txt",
        media_type="text/plain",
        uri="memory://document",
    )

    with pytest.raises(ValidationError):
        attachment.uri = "memory://changed"


def test_agent_input_rejects_non_serializable_metadata() -> None:
    with pytest.raises(ValidationError):
        AgentInput(message="Test", metadata={"invalid": {1, 2}})


def test_agent_input_is_immutable() -> None:
    input_data = AgentInput(message="Test")

    with pytest.raises(ValidationError):
        input_data.message = "Changed"
