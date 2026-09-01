"""Tests for immutable agent definitions."""

import pytest
from pydantic import ValidationError

from atlas_agents import AgentDefinition


def test_agent_definition_accepts_valid_data() -> None:
    definition = AgentDefinition(
        agent_id="support-agent",
        name="Support Agent",
        description="Answers general questions.",
        instructions="Respond clearly.",
        metadata={"version": 1},
    )

    assert definition.agent_id == "support-agent"
    assert definition.metadata == {"version": 1}


@pytest.mark.parametrize(
    ("agent_id", "name", "instructions"),
    [
        (" ", "Agent", "Respond."),
        ("agent", " ", "Respond."),
        ("agent", "Agent", " "),
    ],
)
def test_agent_definition_rejects_blank_required_text(
    agent_id: str,
    name: str,
    instructions: str,
) -> None:
    with pytest.raises(ValidationError):
        AgentDefinition(agent_id=agent_id, name=name, instructions=instructions)


def test_agent_definition_is_immutable() -> None:
    definition = AgentDefinition(
        agent_id="agent",
        name="Agent",
        instructions="Respond.",
    )

    with pytest.raises(ValidationError):
        definition.name = "Changed"


def test_agent_definition_metadata_is_not_shared() -> None:
    first = AgentDefinition(agent_id="first", name="First", instructions="Run.")
    second = AgentDefinition(agent_id="second", name="Second", instructions="Run.")

    first.metadata["source"] = "test"

    assert second.metadata == {}


def test_agent_definition_rejects_non_serializable_metadata() -> None:
    with pytest.raises(ValidationError):
        AgentDefinition(
            agent_id="agent",
            name="Agent",
            instructions="Run.",
            metadata={"invalid": object()},
        )
