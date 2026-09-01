"""Tests for execution context and resolved identity models."""

import pytest
from pydantic import ValidationError

from atlas_agents import AgentContext, ExecutionIdentity


def test_agent_context_supports_execution_without_user_or_tenant() -> None:
    context = AgentContext(execution_id="batch-42")

    assert context.user_id is None
    assert context.tenant_id is None
    assert context.identity is None


@pytest.mark.parametrize("execution_id", ["", "   "])
def test_agent_context_rejects_blank_execution_id(execution_id: str) -> None:
    with pytest.raises(ValidationError):
        AgentContext(execution_id=execution_id)


def test_agent_context_rejects_blank_optional_id() -> None:
    with pytest.raises(ValidationError):
        AgentContext(execution_id="execution", session_id=" ")


def test_agent_context_metadata_is_not_shared() -> None:
    first = AgentContext(execution_id="first")
    second = AgentContext(execution_id="second")

    first.metadata["batch"] = True

    assert second.metadata == {}


def test_execution_identity_defaults_to_empty_sets() -> None:
    identity = ExecutionIdentity(subject="service-account")

    assert identity.roles == frozenset()
    assert identity.permissions == frozenset()


def test_execution_identity_accepts_roles_permissions_and_attributes() -> None:
    identity = ExecutionIdentity(
        subject="user-1",
        roles=frozenset({"operator"}),
        permissions=frozenset({"agents:run"}),
        attributes={"region": "br"},
    )

    assert identity.roles == frozenset({"operator"})
    assert identity.permissions == frozenset({"agents:run"})
    assert identity.attributes == {"region": "br"}


def test_execution_identity_attributes_are_not_shared() -> None:
    first = ExecutionIdentity(subject="first")
    second = ExecutionIdentity(subject="second")

    first.attributes["kind"] = "test"

    assert second.attributes == {}


def test_execution_identity_rejects_blank_subject() -> None:
    with pytest.raises(ValidationError):
        ExecutionIdentity(subject=" ")


def test_agent_context_is_immutable() -> None:
    context = AgentContext(execution_id="execution")

    with pytest.raises(ValidationError):
        context.user_id = "changed"


def test_execution_identity_is_immutable() -> None:
    identity = ExecutionIdentity(subject="subject")

    with pytest.raises(ValidationError):
        identity.subject = "changed"
