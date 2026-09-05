"""Stateless coordination around an injected memory store."""

from collections.abc import Callable
from datetime import UTC, datetime

from atlas_agents.memory.errors import (
    AgentMemoryError,
    MemoryPolicyViolationError,
    MemoryStoreOperationError,
    MemoryStoreProtocolError,
)
from atlas_agents.memory.models import (
    MemoryQuery,
    MemoryRecord,
    MemorySearchResult,
    MemoryWriteRequest,
)
from atlas_agents.memory.selection import (
    DeterministicMemorySelectionPolicy,
    MemorySelectionPolicy,
)
from atlas_agents.memory.store import MemoryStore


class MemoryManager:
    """Validate store boundaries and coordinate deterministic memory selection."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        selection_policy: MemorySelectionPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize with explicit replaceable dependencies and no execution state."""
        self._store = store
        self._selection_policy = (
            selection_policy
            if selection_policy is not None
            else DeterministicMemorySelectionPolicy()
        )
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)

    async def retrieve(
        self,
        *,
        query: MemoryQuery,
    ) -> tuple[MemorySearchResult, ...]:
        """Search and defensively validate scope, type, IDs, and expiration."""
        try:
            results = await self._store.search(query)
        except AgentMemoryError:
            raise
        except Exception as error:
            raise MemoryStoreOperationError(
                "A busca no armazenamento de memória falhou."
            ) from error
        if not isinstance(results, tuple):
            raise MemoryStoreProtocolError(
                "O armazenamento deve retornar uma tupla de resultados."
            )
        seen_ids: set[str] = set()
        valid: list[MemorySearchResult] = []
        now = self._clock()
        for result in results:
            if not isinstance(result, MemorySearchResult):
                raise MemoryStoreProtocolError(
                    "O armazenamento retornou um resultado de memória inválido."
                )
            record = result.record
            if record.memory_id in seen_ids:
                raise MemoryStoreProtocolError(
                    "O armazenamento retornou IDs de memória duplicados."
                )
            seen_ids.add(record.memory_id)
            if record.scope != query.scope:
                raise MemoryStoreProtocolError(
                    "O armazenamento retornou memória de outro escopo.",
                    code="memory_scope_violation",
                )
            if record.memory_type is not query.memory_type:
                raise MemoryStoreProtocolError(
                    "O armazenamento retornou memória de outro tipo.",
                    code="memory_type_violation",
                )
            if record.expires_at is not None and record.expires_at <= now:
                continue
            valid.append(result)
        return tuple(valid[: query.limit])

    def select(
        self,
        *,
        results: tuple[MemorySearchResult, ...],
        max_records: int,
        max_characters: int,
    ) -> tuple[MemorySearchResult, ...]:
        """Apply the configured deterministic selection policy."""
        try:
            selected = self._selection_policy.select(
                results=results,
                max_records=max_records,
                max_characters=max_characters,
            )
        except AgentMemoryError:
            raise
        except Exception as error:
            raise MemoryPolicyViolationError(
                "A política de seleção de memória falhou."
            ) from error
        if not isinstance(selected, tuple) or any(
            not isinstance(result, MemorySearchResult) for result in selected
        ):
            raise MemoryPolicyViolationError(
                "A política deve retornar uma tupla de resultados de memória."
            )
        available = {id(result) for result in results}
        if any(id(result) not in available for result in selected):
            raise MemoryPolicyViolationError(
                "A política não pode criar resultados de memória."
            )
        return selected

    async def remember(self, request: MemoryWriteRequest) -> MemoryRecord:
        """Write one memory and validate the definitive store response."""
        try:
            record = await self._store.write(request)
        except AgentMemoryError:
            raise
        except Exception as error:
            raise MemoryStoreOperationError(
                "A escrita no armazenamento de memória falhou."
            ) from error
        if not isinstance(record, MemoryRecord):
            raise MemoryStoreProtocolError(
                "O armazenamento retornou uma memória inválida após a escrita."
            )
        if record.scope != request.scope:
            raise MemoryStoreProtocolError(
                "A memória gravada pertence a outro escopo.",
                code="memory_scope_violation",
            )
        if record.memory_type is not request.memory_type:
            raise MemoryStoreProtocolError(
                "A memória gravada pertence a outro tipo.",
                code="memory_type_violation",
            )
        if record.content != request.content or record.expires_at != request.expires_at:
            raise MemoryStoreProtocolError("A memória gravada diverge da solicitação.")
        return record
