"""Instance-local registry for guardrail implementations."""

from atlas_agents._models import _non_empty
from atlas_agents.guardrails.base import Guardrail
from atlas_agents.guardrails.errors import (
    DuplicateGuardrailError,
    GuardrailNotRegisteredError,
)


class GuardrailRegistry:
    """Store only explicitly registered guardrails in registration order."""

    def __init__(self, guardrails: tuple[Guardrail[object], ...] = ()) -> None:
        """Register an optional ordered initial collection."""
        self._guardrails: dict[str, Guardrail[object]] = {}
        for guardrail in guardrails:
            self.register(guardrail)

    @property
    def guardrails(self) -> tuple[Guardrail[object], ...]:
        """Return implementations in registration order."""
        return tuple(self._guardrails.values())

    def register(self, guardrail: Guardrail[object]) -> None:
        """Register one unique stable guardrail ID."""
        guardrail_id = _non_empty(guardrail.guardrail_id)
        if guardrail_id in self._guardrails:
            raise DuplicateGuardrailError(
                "O guardrail já está registrado nesta instância."
            )
        self._guardrails[guardrail_id] = guardrail

    def unregister(self, guardrail_id: str) -> Guardrail[object]:
        """Remove and return one known guardrail."""
        guardrail = self.try_get(guardrail_id)
        if guardrail is None:
            raise GuardrailNotRegisteredError(guardrail_id)
        del self._guardrails[guardrail_id]
        return guardrail

    def get(self, guardrail_id: str) -> Guardrail[object]:
        """Return one guardrail or raise a stable registry error."""
        guardrail = self.try_get(guardrail_id)
        if guardrail is None:
            raise GuardrailNotRegisteredError(guardrail_id)
        return guardrail

    def try_get(self, guardrail_id: str) -> Guardrail[object] | None:
        """Return one guardrail when registered."""
        return self._guardrails.get(guardrail_id)
