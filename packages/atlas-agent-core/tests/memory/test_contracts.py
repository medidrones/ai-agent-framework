"""Normative tests for immutable memory value objects."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from atlas_agents import (
    AgentMemoryConfig,
    MemoryCandidate,
    MemoryQuery,
    MemoryRecord,
    MemoryScope,
    MemorySearchResult,
    MemoryType,
    MemoryWriteRequest,
)


def test_memory_types_have_stable_values() -> None:
    assert [item.value for item in MemoryType] == [
        "working",
        "conversation",
        "long_term",
    ]


def test_memory_scope_is_explicit_immutable_and_serializable() -> None:
    scope = MemoryScope(tenant_id="tenant", user_id="user", agent_id="agent")

    assert scope.model_dump(mode="json") == {
        "tenant_id": "tenant",
        "user_id": "user",
        "session_id": None,
        "conversation_id": None,
        "agent_id": "agent",
        "execution_id": None,
    }
    with pytest.raises(ValidationError):
        scope.user_id = "other"


@pytest.mark.parametrize("values", [{}, {"user_id": " "}, {"tenant_id": "*"}])
def test_memory_scope_rejects_global_empty_or_wildcard_values(
    values: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        MemoryScope(**values)


def test_memory_record_validates_content_timestamps_and_expiry() -> None:
    now = datetime.now(UTC)
    scope = MemoryScope(execution_id="execution")
    record = MemoryRecord(
        memory_id="memory",
        memory_type=MemoryType.WORKING,
        scope=scope,
        content="Plano atual.",
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=1),
        metadata={"source": "policy"},
    )

    assert MemoryRecord.model_validate_json(record.model_dump_json()) == record
    for changes in (
        {"memory_id": " "},
        {"content": " "},
        {"updated_at": now - timedelta(seconds=1)},
        {"expires_at": now},
        {"created_at": now.replace(tzinfo=None)},
    ):
        with pytest.raises(ValidationError):
            MemoryRecord.model_validate({**record.model_dump(), **changes})


def test_write_request_and_candidate_require_future_expiry_and_text() -> None:
    scope = MemoryScope(user_id="user")
    future = datetime.now(UTC) + timedelta(hours=1)
    request = MemoryWriteRequest(
        memory_type=MemoryType.LONG_TERM,
        scope=scope,
        content="Prefere respostas curtas.",
        expires_at=future,
    )
    candidate = MemoryCandidate(
        memory_type=MemoryType.LONG_TERM,
        content=request.content,
        expires_at=future,
    )

    assert request.content == candidate.content
    for model in (MemoryWriteRequest, MemoryCandidate):
        values: dict[str, object] = {
            "memory_type": MemoryType.LONG_TERM,
            "content": " ",
            "expires_at": datetime.now(UTC) - timedelta(seconds=1),
        }
        if model is MemoryWriteRequest:
            values["scope"] = scope
        with pytest.raises(ValidationError):
            model.model_validate(values)


def test_query_and_search_score_validate_boundaries() -> None:
    scope = MemoryScope(session_id="session")
    query = MemoryQuery(scope=scope, memory_type=MemoryType.CONVERSATION)
    now = datetime.now(UTC)
    record = MemoryRecord(
        memory_id="memory",
        memory_type=MemoryType.CONVERSATION,
        scope=scope,
        content="Resumo.",
        created_at=now,
        updated_at=now,
    )

    assert query.limit == 20
    assert MemorySearchResult(record=record, score=0.5).score == 0.5
    for score in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            MemorySearchResult(record=record, score=score)
    for values in ({"limit": 0}, {"limit": True}, {"text": " "}):
        with pytest.raises(ValidationError):
            MemoryQuery(
                scope=scope,
                memory_type=MemoryType.CONVERSATION,
                **values,
            )


def test_agent_memory_config_is_disabled_by_default_and_validates_limits() -> None:
    config = AgentMemoryConfig()

    assert not config.enabled
    assert config.max_records_per_type == 20
    assert config.max_characters == 8_000
    assert AgentMemoryConfig(read_types=frozenset({MemoryType.WORKING})).enabled
    for values in (
        {"max_records_per_type": 0},
        {"max_characters": True},
    ):
        with pytest.raises(ValidationError):
            AgentMemoryConfig(**values)
