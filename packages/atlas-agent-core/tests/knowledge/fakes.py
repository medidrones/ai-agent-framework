"""Reusable external knowledge retriever test doubles."""

import asyncio
from collections.abc import Callable

from atlas_agents import (
    KnowledgeDocument,
    KnowledgePassage,
    KnowledgeQuery,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalResult,
    KnowledgeSource,
)


class FakeKnowledgeRetriever:
    def __init__(
        self,
        *,
        results_factory: Callable[[KnowledgeQuery], object] | None = None,
        sources_result: object | None = None,
        error: Exception | None = None,
        wait_event: asyncio.Event | None = None,
    ) -> None:
        self.results_factory = results_factory
        self.sources_result = sources_result
        self.error = error
        self.wait_event = wait_event
        self.queries: list[KnowledgeQuery] = []
        self.contexts: list[KnowledgeRetrievalContext] = []
        self.started = asyncio.Event()

    async def sources(self) -> tuple[KnowledgeSource, ...]:
        if self.error is not None:
            raise self.error
        if self.sources_result is not None:
            return self.sources_result  # type: ignore[return-value]
        return (KnowledgeSource(source_id="policies", name="Políticas"),)

    async def retrieve(
        self,
        query: KnowledgeQuery,
        context: KnowledgeRetrievalContext,
    ) -> tuple[KnowledgeRetrievalResult, ...]:
        self.queries.append(query)
        self.contexts.append(context)
        self.started.set()
        if self.wait_event is not None:
            await self.wait_event.wait()
        if self.error is not None:
            raise self.error
        if self.results_factory is not None:
            return self.results_factory(query)  # type: ignore[return-value]
        return ()


def retrieval_result(
    *,
    source_id: str = "policies",
    document_id: str = "document-1",
    passage_id: str = "passage-1",
    content: str = "Cancelamentos são permitidos em até sete dias.",
) -> KnowledgeRetrievalResult:
    return KnowledgeRetrievalResult(
        passage=KnowledgePassage(
            passage_id=passage_id,
            document=KnowledgeDocument(
                document_id=document_id,
                source_id=source_id,
                title="Política de cancelamento",
                uri="urn:policy:cancellation",
            ),
            content=content,
        )
    )
