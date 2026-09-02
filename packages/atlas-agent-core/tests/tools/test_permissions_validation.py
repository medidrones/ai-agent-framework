"""Tests for tool authorization and JSON Schema argument validation."""

import pytest
from pydantic import ValidationError

from atlas_agents import (
    ExecutionIdentity,
    JsonSchemaToolArgumentValidator,
    ToolArgumentValidationIssue,
    ToolArgumentValidationResult,
    ToolExecutionContext,
    ToolPermissionDecision,
    ToolPermissionEvaluator,
)
from tests.tools.fakes import tool_definition


def _context(*permissions: str, identity: bool = True) -> ToolExecutionContext:
    resolved_identity = (
        ExecutionIdentity(subject="subject", permissions=frozenset(permissions))
        if identity
        else None
    )
    return ToolExecutionContext(
        execution_id="execution",
        agent_id="agent",
        tool_call_id="call",
        identity=resolved_identity,
    )


@pytest.mark.parametrize(
    ("required", "context", "allowed", "missing"),
    [
        (frozenset(), _context(identity=False), True, frozenset()),
        (frozenset(), _context("extra"), True, frozenset()),
        (frozenset({"a"}), _context("a"), True, frozenset()),
        (frozenset({"a"}), _context("a", "b"), True, frozenset()),
        (frozenset({"a", "b"}), _context("a"), False, frozenset({"b"})),
        (frozenset({"a"}), _context(identity=False), False, frozenset({"a"})),
        (
            frozenset({"a", "b"}),
            _context(identity=False),
            False,
            frozenset({"a", "b"}),
        ),
    ],
)
def test_permission_matrix(
    required: frozenset[str],
    context: ToolExecutionContext,
    allowed: bool,
    missing: frozenset[str],
) -> None:
    decision = ToolPermissionEvaluator().evaluate(
        definition=tool_definition(permissions=required),
        context=context,
    )
    assert decision == ToolPermissionDecision(
        allowed=allowed,
        missing_permissions=missing,
    )


def test_permission_decision_rejects_inconsistent_state() -> None:
    with pytest.raises(ValidationError):
        ToolPermissionDecision(allowed=True, missing_permissions=frozenset({"a"}))
    with pytest.raises(ValidationError):
        ToolPermissionDecision(allowed=False)


def test_json_schema_validator_accepts_valid_nested_arguments() -> None:
    validator = JsonSchemaToolArgumentValidator()
    schema: dict[str, object] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "customer": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
            }
        },
        "required": ["customer"],
        "additionalProperties": False,
    }
    result = validator.validate(
        schema=schema,
        arguments={"customer": {"id": "123"}},
    )
    assert result == ToolArgumentValidationResult(valid=True)


@pytest.mark.parametrize(
    ("arguments", "expected_code", "expected_path"),
    [
        ({}, "required", "/"),
        ({"customer_id": 123}, "type", "/customer_id"),
        (
            {"customer_id": "123", "unknown": True},
            "additionalProperties",
            "/",
        ),
    ],
)
def test_json_schema_validator_normalizes_invalid_arguments(
    arguments: dict[str, object],
    expected_code: str,
    expected_path: str,
) -> None:
    result = JsonSchemaToolArgumentValidator().validate(
        schema=tool_definition().parameters,
        arguments=arguments,
    )
    assert not result.valid
    assert result.issues[0].code == expected_code
    assert result.issues[0].path == expected_path
    assert result.issues[0].message.endswith(".")


def test_json_schema_validator_reports_invalid_registered_schema() -> None:
    result = JsonSchemaToolArgumentValidator().validate(
        schema={"type": "not-a-json-type"},
        arguments={},
    )
    assert result == ToolArgumentValidationResult(
        valid=False,
        issues=(ToolArgumentValidationIssue.invalid_schema(),),
    )


def test_validation_result_rejects_inconsistent_state() -> None:
    issue = ToolArgumentValidationIssue(path="/", code="type", message="Inválido.")
    with pytest.raises(ValidationError):
        ToolArgumentValidationResult(valid=True, issues=(issue,))
    with pytest.raises(ValidationError):
        ToolArgumentValidationResult(valid=False)
