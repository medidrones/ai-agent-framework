"""Retrieve a local passage and expose a provider-neutral citation."""

import asyncio
from pathlib import Path

from atlas_agents import (
    KnowledgeDocument,
    KnowledgeManager,
    KnowledgePassage,
    KnowledgeQuery,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalResult,
    KnowledgeSource,
)


class LocalPolicyRetriever:
    """Retrieve one deterministic local Markdown document."""

    async def sources(self) -> tuple[KnowledgeSource, ...]:
        """Return the single explicit local source."""
        return (KnowledgeSource(source_id="company-policy", name="Política local"),)

    async def retrieve(
        self,
        query: KnowledgeQuery,
        context: KnowledgeRetrievalContext,
    ) -> tuple[KnowledgeRetrievalResult, ...]:
        """Return the deterministic local policy passage."""
        del query, context
        path = Path(__file__).with_name("company_policy.md")
        return (
            KnowledgeRetrievalResult(
                passage=KnowledgePassage(
                    passage_id="late-orders",
                    document=KnowledgeDocument(
                        document_id="company-policy",
                        source_id="company-policy",
                        title="Política de atendimento",
                        uri="company_policy.md",
                    ),
                    content=path.read_text(encoding="utf-8").strip(),
                )
            ),
        )


async def _run() -> None:
    manager = KnowledgeManager(retriever=LocalPolicyRetriever())
    context = await manager.retrieve(
        query=KnowledgeQuery(
            text="Quando um pedido atrasado pode receber compensação?",
            source_ids=("company-policy",),
            limit=1,
        ),
        context=KnowledgeRetrievalContext(
            execution_id="knowledge-example",
            agent_id="example-agent",
        ),
        max_results=1,
        max_characters=1_000,
    )
    print("Memória representa histórico; knowledge representa fonte externa.")  # noqa: T201
    citation = context.citations[0]
    print(  # noqa: T201
        f"Resposta: compensação após aprovação humana [{citation.citation_key}]"
    )
    print(f"Fonte: {citation.uri}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
