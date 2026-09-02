"""Tests for isolated deterministic tool registries."""

import pytest

from atlas_agents import DuplicateToolError, ToolNotRegisteredError, ToolRegistry
from tests.tools.fakes import FakeTool, tool_definition


def test_registry_starts_empty_and_preserves_registration_order() -> None:
    registry = ToolRegistry()
    first = FakeTool(tool_definition(name="first"))
    second = FakeTool(tool_definition(name="Second"))

    assert registry.tools() == ()
    registry.register(first)
    registry.register(second)

    assert registry.tools() == (first, second)
    assert registry.get("first") is first
    assert registry.try_get("Second") is second
    assert registry.try_get("second") is None
    assert registry.try_get(" first ") is None


def test_registry_rejects_duplicates_without_overwriting() -> None:
    registry = ToolRegistry()
    original = FakeTool(tool_definition())
    duplicate = FakeTool(tool_definition())
    registry.register(original)

    with pytest.raises(DuplicateToolError) as captured:
        registry.register(duplicate)

    assert captured.value.tool_name == "get_customer"
    assert registry.get("get_customer") is original


def test_registry_unknown_and_unregister_semantics() -> None:
    registry = ToolRegistry()
    tool = FakeTool(tool_definition())
    registry.register(tool)

    assert registry.unregister("get_customer") is tool
    assert registry.try_get("get_customer") is None
    with pytest.raises(ToolNotRegisteredError):
        registry.get("get_customer")
    with pytest.raises(ToolNotRegisteredError):
        registry.unregister("get_customer")
    with pytest.raises(ValueError, match="não pode estar vazio"):
        registry.get(" ")


def test_model_definitions_do_not_expose_tool_implementations() -> None:
    registry = ToolRegistry()
    first = FakeTool(tool_definition(name="first"))
    second = FakeTool(tool_definition(name="second"))
    registry.register(first)
    registry.register(second)

    definitions = registry.model_definitions()

    assert tuple(item.name for item in definitions) == ("first", "second")
    assert all(not hasattr(item, "execute") for item in definitions)
    assert all(
        "required_permissions" not in type(item).model_fields for item in definitions
    )
