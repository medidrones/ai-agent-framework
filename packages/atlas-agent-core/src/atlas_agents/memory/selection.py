"""Deterministic memory selection policy contracts."""

from typing import Protocol

from atlas_agents.memory.errors import MemoryPolicyViolationError
from atlas_agents.memory.models import MemorySearchResult
from atlas_agents.memory.renderer import _render_memory_text


class MemorySelectionPolicy(Protocol):
    """Select ordered results within record and rendered-character limits."""

    def select(
        self,
        *,
        results: tuple[MemorySearchResult, ...],
        max_records: int,
        max_characters: int,
    ) -> tuple[MemorySearchResult, ...]:
        """Return an ordered subset of the supplied results."""
        ...


class DeterministicMemorySelectionPolicy:
    """Keep store order, skipping records that cannot fit without truncation."""

    def select(
        self,
        *,
        results: tuple[MemorySearchResult, ...],
        max_records: int,
        max_characters: int,
    ) -> tuple[MemorySearchResult, ...]:
        """Select records without reranking, truncating, or summarizing them."""
        if (
            isinstance(max_records, bool)
            or not isinstance(max_records, int)
            or max_records <= 0
            or isinstance(max_characters, bool)
            or not isinstance(max_characters, int)
            or max_characters <= 0
        ):
            raise MemoryPolicyViolationError(
                "Os limites da seleção de memória devem ser inteiros positivos."
            )
        selected: list[MemorySearchResult] = []
        for result in results:
            if len(selected) >= max_records:
                break
            candidate = (*selected, result)
            if len(_render_memory_text(candidate)) <= max_characters:
                selected.append(result)
        return tuple(selected)
