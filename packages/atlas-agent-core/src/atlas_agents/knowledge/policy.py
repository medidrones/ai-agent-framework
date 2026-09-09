"""Pure deterministic knowledge result selection policies."""

from typing import Protocol

from atlas_agents.knowledge.errors import KnowledgePolicyError
from atlas_agents.knowledge.retrieval import KnowledgeRetrievalResult


class RetrievalPolicy(Protocol):
    """Select an ordered result subset within assembly limits."""

    def select(
        self,
        *,
        results: tuple[KnowledgeRetrievalResult, ...],
        max_results: int,
        max_characters: int,
    ) -> tuple[KnowledgeRetrievalResult, ...]:
        """Return an ordered subset without external I/O."""
        ...


class DeterministicRetrievalPolicy:
    """Preserve retriever order and skip passages that cannot fit whole."""

    def select(
        self,
        *,
        results: tuple[KnowledgeRetrievalResult, ...],
        max_results: int,
        max_characters: int,
    ) -> tuple[KnowledgeRetrievalResult, ...]:
        """Apply count and passage-content character budgets deterministically."""
        if (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or max_results <= 0
            or isinstance(max_characters, bool)
            or not isinstance(max_characters, int)
            or max_characters <= 0
        ):
            raise KnowledgePolicyError(
                "Os limites de conhecimento devem ser inteiros positivos."
            )
        selected: list[KnowledgeRetrievalResult] = []
        characters = 0
        for result in results:
            if len(selected) >= max_results:
                break
            passage_length = len(result.passage.content)
            if characters + passage_length <= max_characters:
                selected.append(result)
                characters += passage_length
        return tuple(selected)
