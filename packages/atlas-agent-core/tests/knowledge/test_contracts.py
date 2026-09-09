"""Validation tests for provider-neutral knowledge value objects."""

import math

import pytest
from pydantic import ValidationError

from atlas_agents import (
    AgentKnowledgeConfig,
    Citation,
    ExecutionIdentity,
    KnowledgeDocument,
    KnowledgeLocation,
    KnowledgePassage,
    KnowledgeQuery,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalResult,
    KnowledgeSource,
)


def test_document_passage_source_and_context_are_immutable_and_serializable() -> None:
    metadata: dict[str, object] = {"classification": "public"}
    document = KnowledgeDocument(
        document_id="document-1",
        source_id="policies",
        title="Política",
        uri="urn:policy:1",
        metadata=metadata,
    )
    metadata["classification"] = "changed"
    passage = KnowledgePassage(
        passage_id="passage-1",
        document=document,
        content="Conteúdo externo.",
        location=KnowledgeLocation(page=2, section="Cancelamento"),
    )
    source = KnowledgeSource(source_id="policies", name="Políticas")
    context = KnowledgeRetrievalContext(
        execution_id="execution-1",
        agent_id="assistant",
        identity=ExecutionIdentity(subject="user-1"),
    )

    assert document.metadata == {"classification": "public"}
    assert passage.model_dump(mode="json")["location"]["page"] == 2
    assert source.model_dump(mode="json")["source_id"] == "policies"
    assert context.identity is not None
    assert context.identity.subject == "user-1"
    with pytest.raises(ValidationError):
        document.document_id = "changed"


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (KnowledgeDocument, {"document_id": " ", "source_id": "source"}),
        (KnowledgeDocument, {"document_id": "doc", "source_id": " "}),
        (
            KnowledgePassage,
            {
                "passage_id": "passage",
                "document": KnowledgeDocument(document_id="doc", source_id="source"),
                "content": " ",
            },
        ),
        (KnowledgeSource, {"source_id": "source", "name": " "}),
    ],
)
def test_required_document_passage_and_source_text_is_validated(
    model: type[object], kwargs: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        model(**kwargs)


@pytest.mark.parametrize(
    "location",
    [
        {"page": 0},
        {"start_offset": -1},
        {"end_offset": 2},
        {"start_offset": 5, "end_offset": 4},
        {"page": True},
    ],
)
def test_location_rejects_invalid_pages_and_offsets(
    location: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        KnowledgeLocation(**location)  # type: ignore[arg-type]


def test_empty_location_and_ordered_offsets_are_supported() -> None:
    assert KnowledgeLocation() == KnowledgeLocation()
    assert KnowledgeLocation(start_offset=0, end_offset=10).end_offset == 10


def test_query_preserves_sources_and_rejects_unsafe_values() -> None:
    query = KnowledgeQuery(
        text="Qual é a política?",
        source_ids=("policies", "manuals"),
        filters={"language": "pt-BR"},
        limit=4,
    )
    assert query.source_ids == ("policies", "manuals")
    assert query.filters == {"language": "pt-BR"}

    for kwargs in (
        {"text": " "},
        {"text": "x", "source_ids": ("policies", "policies")},
        {"text": "x", "source_ids": ("",)},
        {"text": "x", "limit": 0},
        {"text": "x", "limit": True},
    ):
        with pytest.raises(ValidationError):
            KnowledgeQuery(**kwargs)


@pytest.mark.parametrize("score", [math.nan, math.inf, -math.inf])
def test_retrieval_result_rejects_non_finite_scores(score: float) -> None:
    passage = KnowledgePassage(
        passage_id="passage",
        document=KnowledgeDocument(document_id="doc", source_id="source"),
        content="Conteúdo.",
    )
    with pytest.raises(ValidationError):
        KnowledgeRetrievalResult(passage=passage, score=score)


def test_retrieval_rank_and_citation_key_are_validated() -> None:
    passage = KnowledgePassage(
        passage_id="passage",
        document=KnowledgeDocument(document_id="doc", source_id="source"),
        content="Conteúdo.",
    )
    assert KnowledgeRetrievalResult(passage=passage, rank=1).rank == 1
    with pytest.raises(ValidationError):
        KnowledgeRetrievalResult(passage=passage, rank=True)
    with pytest.raises(ValidationError):
        Citation(
            citation_key="passage",
            source_id="source",
            document_id="doc",
            passage_id="passage",
        )


def test_agent_knowledge_config_is_explicit_ordered_and_bounded() -> None:
    assert not AgentKnowledgeConfig().enabled
    config = AgentKnowledgeConfig(
        source_ids=("policies", "manuals"),
        max_results=3,
        max_characters=1_000,
    )
    assert config.enabled
    assert config.source_ids == ("policies", "manuals")
    for kwargs in (
        {"source_ids": ("a", "a")},
        {"source_ids": ("",)},
        {"max_results": 0},
        {"max_characters": True},
    ):
        with pytest.raises(ValidationError):
            AgentKnowledgeConfig(**kwargs)
