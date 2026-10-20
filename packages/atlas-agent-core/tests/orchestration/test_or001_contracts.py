from datetime import UTC, datetime, timedelta
from inspect import iscoroutinefunction

import pytest
from pydantic import ValidationError

import atlas_agents
from atlas_agents import AgentAttachment, AgentRuntime
from atlas_agents.exceptions import AtlasAgentError
from atlas_agents.orchestration import (
    MAX_IDENTIFIER_LENGTH,
    MAX_JSON_DEPTH,
    MAX_JSON_ITEMS,
    MAX_JSON_STRING_LENGTH,
    WorkflowContext,
    WorkflowContractError,
    WorkflowDefinition,
    WorkflowDefinitionError,
    WorkflowEdge,
    WorkflowError,
    WorkflowErrorInfo,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowInput,
    WorkflowNode,
    WorkflowNodeKind,
    WorkflowNodeResult,
    WorkflowOrchestrator,
    WorkflowPolicyDecision,
    WorkflowResult,
    WorkflowResultKind,
    WorkflowRetryDecision,
    WorkflowStatus,
    WorkflowValidationError,
    is_workflow_terminal,
)
from atlas_agents.orchestration.validation import freeze_json_mapping

NOW = datetime(2026, 10, 19, tzinfo=UTC)


def _node(node_id: str = "agent.prepare") -> WorkflowNode:
    return WorkflowNode(
        node_id=node_id,
        kind=WorkflowNodeKind.AGENT,
        agent_ref="agent.writer",
        configuration={"temperature": 0, "nested": {"values": [1, 2]}},
    )


def _definition(**changes: object) -> WorkflowDefinition:
    data: dict[str, object] = {
        "workflow_id": "content.pipeline",
        "version": "1.0.0",
        "name": "Pipeline editorial",
        "nodes": (_node(),),
        "metadata": {"owner": "platform", "labels": ["public"]},
    }
    data.update(changes)
    return WorkflowDefinition.model_validate(data)


def _context(**changes: object) -> WorkflowContext:
    data: dict[str, object] = {
        "workflow_execution_id": "wfexec-001",
        "workflow_id": "content.pipeline",
        "workflow_version": "1.0.0",
        "correlation_id": "corr-001",
        "tenant_id": "tenant-a",
        "created_at": NOW,
        "deadline_at": NOW + timedelta(minutes=5),
        "metadata": {"channel": "api"},
    }
    data.update(changes)
    return WorkflowContext.model_validate(data)


def test_or001_t01_creates_valid_workflow() -> None:
    assert _definition().workflow_id == "content.pipeline"


@pytest.mark.parametrize(
    ("field", "value"),
    [("workflow_id", " "), ("version", ""), ("name", "  ")],
)
def test_or001_t02_t04_rejects_required_empty_values(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        _definition(**{field: value})


def test_or001_t05_rejects_duplicate_nodes() -> None:
    with pytest.raises(ValidationError, match="únicos"):
        _definition(nodes=(_node(), _node()))


@pytest.mark.parametrize(
    ("edge", "message"),
    [
        (
            WorkflowEdge(source_node_id="missing", target_node_id="agent.prepare"),
            "origem",
        ),
        (
            WorkflowEdge(source_node_id="agent.prepare", target_node_id="missing"),
            "destino",
        ),
    ],
)
def test_or001_t06_t07_rejects_dangling_edges(edge: WorkflowEdge, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _definition(edges=(edge,))


def test_or001_t08_rejects_unknown_node_kind() -> None:
    with pytest.raises(ValidationError):
        WorkflowNode.model_validate({"node_id": "node", "kind": "script"})


def test_or001_t09_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        WorkflowNode.model_validate(
            {"node_id": "node", "kind": "agent", "scheduler": "hidden"}
        )


def test_or001_t10_rejects_non_json_payload() -> None:
    with pytest.raises(ValidationError, match="JSON"):
        WorkflowInput(correlation_id="corr", payload=object())


def test_or001_t11_rejects_model_mutation() -> None:
    with pytest.raises(ValidationError):
        _definition().name = "Outro"


def test_or001_t12_protects_nested_mutation() -> None:
    definition = _definition()
    with pytest.raises(TypeError):
        definition.metadata["owner"] = "attacker"  # type: ignore[index]
    with pytest.raises(TypeError):
        definition.nodes[0].configuration["nested"]["x"] = 1  # type: ignore[index]


def test_or001_t13_serializes_json() -> None:
    assert '"workflow_id":"content.pipeline"' in _definition().model_dump_json()


def test_or001_t14_deserializes_json() -> None:
    value = WorkflowDefinition.model_validate_json(_definition().model_dump_json())
    assert value.version == "1.0.0"


def test_or001_t15_round_trip_is_equivalent() -> None:
    value = _definition()
    assert WorkflowDefinition.model_validate_json(value.model_dump_json()) == value


def test_or001_t16_workflow_status_is_complete() -> None:
    assert {status.value for status in WorkflowStatus} == {
        "created",
        "ready",
        "running",
        "waiting",
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
    }
    assert is_workflow_terminal(WorkflowStatus.SUCCEEDED)
    assert not is_workflow_terminal(WorkflowStatus.WAITING)


def test_or001_t17_workflow_event_types_are_stable() -> None:
    assert len(WorkflowEventType) == 11
    assert WorkflowEventType.NODE_FAILED.value == "node_failed"


def test_or001_t18_builds_terminal_workflow_result() -> None:
    result = WorkflowResult(
        workflow_execution_id="wfexec-001",
        workflow_id="content.pipeline",
        workflow_version="1.0.0",
        correlation_id="corr-001",
        status=WorkflowStatus.SUCCEEDED,
        result_kind=WorkflowResultKind.TERMINAL,
        output={"published": True},
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
    )
    assert result.output == {"published": True}


def test_or001_t19_builds_workflow_context() -> None:
    assert _context().workflow_execution_id == "wfexec-001"


def test_or001_t20_preserves_correlation_id_across_contracts() -> None:
    input_data = WorkflowInput(correlation_id="corr-001", payload={})
    event = WorkflowEvent(
        event_id="event-001",
        workflow_execution_id="wfexec-001",
        event_type=WorkflowEventType.WORKFLOW_CREATED,
        timestamp=NOW,
        correlation_id=input_data.correlation_id,
    )
    assert event.correlation_id == _context().correlation_id


def test_or001_t21_tenant_is_context_not_authorization() -> None:
    context = _context()
    assert context.tenant_id == "tenant-a"
    assert "authorized" not in type(context).model_fields


@pytest.mark.parametrize(
    "factory",
    [
        lambda: _context(created_at=datetime(2026, 1, 1)),
        lambda: WorkflowEvent.model_validate(
            {
                "event_id": "event",
                "workflow_execution_id": "execution",
                "event_type": "workflow_created",
                "timestamp": datetime(2026, 1, 1),
                "correlation_id": "correlation",
            }
        ),
    ],
)
def test_or001_t22_rejects_naive_timestamps(factory: object) -> None:
    with pytest.raises(ValidationError, match="fuso"):
        factory()  # type: ignore[operator]


def test_or001_t23_exception_hierarchy_is_integrated() -> None:
    assert issubclass(WorkflowError, AtlasAgentError)
    assert issubclass(WorkflowDefinitionError, WorkflowError)
    assert issubclass(WorkflowValidationError, WorkflowDefinitionError)
    assert issubclass(WorkflowContractError, WorkflowError)


def test_or001_t24_orchestrator_protocol_is_async() -> None:
    assert iscoroutinefunction(WorkflowOrchestrator.execute)


def test_or001_t25_public_exports_are_available() -> None:
    required = {
        "WorkflowDefinition",
        "WorkflowNode",
        "WorkflowEdge",
        "WorkflowInput",
        "WorkflowContext",
        "WorkflowResult",
        "WorkflowEvent",
        "WorkflowOrchestrator",
    }
    assert required <= set(atlas_agents.__all__)


def test_or001_result_preserves_distinct_execution_identities() -> None:
    node_result = WorkflowNodeResult(
        node_id="agent.prepare",
        node_execution_id="nodeexec-001",
        agent_execution_id="agentexec-001",
        attempt=1,
        status=WorkflowStatus.SUCCEEDED,
        output={"ok": True},
    )
    assert (
        len(
            {
                node_result.node_id,
                node_result.node_execution_id,
                node_result.agent_execution_id,
            }
        )
        == 3
    )


def test_or001_rejects_executable_condition_reference() -> None:
    with pytest.raises(ValidationError, match="simbólica"):
        WorkflowEdge(
            source_node_id="a",
            target_node_id="b",
            condition_ref="__import__('os').system('x')",
        )


def test_or001_rejects_excessive_strings() -> None:
    with pytest.raises(ValidationError, match="string JSON"):
        WorkflowInput(
            correlation_id="corr",
            payload={"text": "x" * (MAX_JSON_STRING_LENGTH + 1)},
        )


def test_or001_rejects_recursive_structures() -> None:
    recursive: dict[str, object] = {}
    recursive["self"] = recursive
    with pytest.raises(ValidationError, match="recursivas"):
        WorkflowInput(correlation_id="corr", payload=recursive)


def test_or001_rejects_excessive_depth() -> None:
    value: object = "leaf"
    for _ in range(MAX_JSON_DEPTH + 1):
        value = [value]
    with pytest.raises(ValidationError, match="profundidade"):
        WorkflowInput(correlation_id="corr", payload=value)


def test_or001_error_info_does_not_embed_exception_or_payload() -> None:
    with pytest.raises(ValidationError):
        WorkflowErrorInfo(
            code="internal",
            message="Falha segura",
            details={"exception": RuntimeError("secret-value")},
        )


def test_or001_rejects_malformed_json() -> None:
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate_json("{invalid")


def test_or001_preserves_agent_runtime_contract() -> None:
    assert AgentRuntime.__module__ == "atlas_agents.runtime.runtime"


def test_or001_preserves_agent_attachment_metadata_contract() -> None:
    attachment = AgentAttachment(
        attachment_id="attachment",
        name="documento",
        media_type="text/plain",
        uri="urn:atlas:document",
        metadata={"origin": "compatibility-test"},
    )
    assert attachment.metadata == {"origin": "compatibility-test"}


@pytest.mark.parametrize(
    "data",
    [
        {
            "workflow_id": "w",
            "version": "not a version",
            "name": "W",
            "nodes": (_node(),),
        },
        {"workflow_id": "w", "version": "1.0", "name": "W", "nodes": ()},
    ],
)
def test_or001_rejects_invalid_definition_version_or_empty_nodes(
    data: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate(data)


def test_or001_serializes_all_immutable_boundaries() -> None:
    input_data = WorkflowInput(
        correlation_id="corr",
        payload=[{"value": 1}],
        metadata={"source": "test"},
    )
    event = WorkflowEvent(
        event_id="event",
        workflow_execution_id="execution",
        event_type=WorkflowEventType.NODE_STARTED,
        timestamp=NOW,
        node_id="node",
        correlation_id="corr",
        payload={"attempt": 1},
    )
    error = WorkflowErrorInfo(
        code="node_failed",
        message="Falha controlada",
        details={"category": "transient"},
    )
    assert input_data.model_dump_json() == (
        '{"correlation_id":"corr","payload":[{"value":1}],"metadata":{"source":"test"}}'
    )
    assert '"node_id":"node"' in event.model_dump_json()
    assert '"category":"transient"' in error.model_dump_json()


def test_or001_accepts_optional_context_and_node_result_fields() -> None:
    context = _context(tenant_id=None, deadline_at=None)
    result = WorkflowNodeResult(
        node_id="node",
        node_execution_id="attempt",
        attempt=1,
        status=WorkflowStatus.RUNNING,
    )
    assert context.tenant_id is None
    assert context.deadline_at is None
    assert result.agent_execution_id is None
    assert result.model_dump_json().endswith('"error":null}')


def test_or001_rejects_deadline_before_creation() -> None:
    with pytest.raises(ValidationError, match="deadline"):
        _context(deadline_at=NOW - timedelta(seconds=1))


@pytest.mark.parametrize(
    "data",
    [
        {
            "status": "running",
            "result_kind": "terminal",
            "completed_at": NOW,
        },
        {"status": "failed", "result_kind": "snapshot"},
        {"status": "succeeded", "result_kind": "terminal"},
        {
            "status": "running",
            "result_kind": "snapshot",
            "completed_at": NOW,
        },
        {
            "status": "cancelled",
            "result_kind": "terminal",
            "completed_at": NOW - timedelta(seconds=1),
        },
        {
            "status": "failed",
            "result_kind": "terminal",
            "completed_at": NOW,
        },
        {
            "status": "succeeded",
            "result_kind": "terminal",
            "completed_at": NOW,
            "error": {"code": "unexpected", "message": "Erro"},
        },
    ],
)
def test_or001_rejects_inconsistent_results(data: dict[str, object]) -> None:
    base: dict[str, object] = {
        "workflow_execution_id": "execution",
        "workflow_id": "workflow",
        "workflow_version": "1.0",
        "correlation_id": "correlation",
        "started_at": NOW,
    }
    base.update(data)
    with pytest.raises(ValidationError):
        WorkflowResult.model_validate(base)


def test_or001_accepts_failed_terminal_result_and_running_snapshot() -> None:
    failed = WorkflowResult(
        workflow_execution_id="execution",
        workflow_id="workflow",
        workflow_version="1.0",
        correlation_id="correlation",
        status=WorkflowStatus.FAILED,
        result_kind=WorkflowResultKind.TERMINAL,
        error=WorkflowErrorInfo(code="failed", message="Falha"),
        started_at=NOW,
        completed_at=NOW,
    )
    snapshot = WorkflowResult(
        workflow_execution_id="execution",
        workflow_id="workflow",
        workflow_version="1.0",
        correlation_id="correlation",
        status=WorkflowStatus.RUNNING,
        result_kind=WorkflowResultKind.SNAPSHOT,
        started_at=NOW,
    )
    assert failed.error is not None
    assert snapshot.completed_at is None


@pytest.mark.parametrize(
    "model",
    [
        lambda: WorkflowPolicyDecision(allowed=False, reason=" "),
        lambda: WorkflowRetryDecision(retry=True, reason=" "),
        lambda: WorkflowRetryDecision(retry=True, delay_seconds=-1, reason="retry"),
    ],
)
def test_or001_rejects_invalid_policy_decisions(model: object) -> None:
    with pytest.raises(ValidationError):
        model()  # type: ignore[operator]


@pytest.mark.parametrize(
    "identifier",
    ["contains space", "x" * (MAX_IDENTIFIER_LENGTH + 1), "-starts-invalid"],
)
def test_or001_rejects_ambiguous_identifiers(identifier: str) -> None:
    with pytest.raises(ValidationError):
        WorkflowInput(correlation_id=identifier, payload={})


@pytest.mark.parametrize(
    "payload",
    [
        {1: "non-string-key"},
        {"x" * (MAX_IDENTIFIER_LENGTH + 1): True},
        {"value": float("inf")},
        set(),
    ],
)
def test_or001_rejects_other_non_json_values(payload: object) -> None:
    with pytest.raises(ValidationError):
        WorkflowInput(correlation_id="corr", payload=payload)


def test_or001_rejects_too_many_json_items() -> None:
    with pytest.raises(ValidationError, match="quantidade"):
        WorkflowInput(
            correlation_id="corr",
            payload=list(range(MAX_JSON_ITEMS + 1)),
        )


def test_or001_default_mappings_are_immutable() -> None:
    node = WorkflowNode(node_id="node", kind=WorkflowNodeKind.AGENT)
    event = WorkflowEvent(
        event_id="event",
        workflow_execution_id="execution",
        event_type=WorkflowEventType.WORKFLOW_CREATED,
        timestamp=NOW,
        correlation_id="corr",
    )
    with pytest.raises(TypeError):
        node.configuration["x"] = 1  # type: ignore[index]
    with pytest.raises(TypeError):
        event.payload["x"] = 1  # type: ignore[index]


def test_or001_covers_valid_edge_float_and_remaining_serializers() -> None:
    first = _node("first")
    second = _node("second")
    definition = _definition(
        nodes=(first, second),
        edges=(
            WorkflowEdge(
                source_node_id="first",
                target_node_id="second",
                condition_ref="approval.granted",
            ),
        ),
    )
    context = _context(metadata={"ratio": 0.5})
    result = WorkflowResult(
        workflow_execution_id="execution",
        workflow_id="workflow",
        workflow_version="1.0",
        correlation_id="correlation",
        status=WorkflowStatus.RUNNING,
        result_kind=WorkflowResultKind.SNAPSHOT,
        output={"ratio": 0.5},
        started_at=NOW,
        metadata={"phase": "active"},
    )
    assert definition.edges[0].condition_ref == "approval.granted"
    assert '"ratio":0.5' in context.model_dump_json()
    assert '"phase":"active"' in result.model_dump_json()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: WorkflowErrorInfo(code="error", message=" "),
        lambda: WorkflowErrorInfo(code="error", message="x" * 4097),
        lambda: WorkflowEvent.model_validate(
            {
                "event_id": "event",
                "workflow_execution_id": "execution",
                "event_type": "workflow_created",
                "timestamp": NOW,
                "correlation_id": "corr",
                "payload": [],
            }
        ),
    ],
)
def test_or001_rejects_invalid_error_messages_and_non_object_payloads(
    factory: object,
) -> None:
    with pytest.raises(ValidationError):
        factory()  # type: ignore[operator]


def test_or001_json_mapping_helper_rejects_non_object_root() -> None:
    with pytest.raises(ValueError, match="objeto JSON"):
        freeze_json_mapping(["array"])
