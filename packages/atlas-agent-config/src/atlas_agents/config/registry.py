"""Explicit instance-local registry for typed configuration factories."""

from __future__ import annotations

from typing import TypeVar

from atlas_agents.config.errors import (
    ComponentFactoryNotFoundError,
    DuplicateFactoryError,
)
from atlas_agents.config.factories import (
    AdapterFactory,
    GuardrailFactory,
    KnowledgeFactory,
    MCPFactory,
    MemoryFactory,
    ModelProviderFactory,
    ObservabilityFactory,
    ToolFactory,
)

F = TypeVar("F")


def _type_name(factory: object) -> str:
    value = getattr(factory, "type_name", None)
    if not isinstance(value, str) or not value.strip():
        raise DuplicateFactoryError("A factory deve declarar um type_name válido.")
    return value.strip()


class ConfigurationFactoryRegistry:
    """Keep typed factory namespaces explicit and isolated per instance."""

    def __init__(self) -> None:
        """Initialize empty factory categories with no global defaults."""
        self._providers: dict[str, ModelProviderFactory] = {}
        self._tools: dict[str, ToolFactory] = {}
        self._memory: dict[str, MemoryFactory] = {}
        self._knowledge: dict[str, KnowledgeFactory] = {}
        self._guardrails: dict[str, GuardrailFactory] = {}
        self._observability: dict[str, ObservabilityFactory] = {}
        self._mcp: dict[str, MCPFactory] = {}
        self._adapters: dict[str, AdapterFactory] = {}

    @staticmethod
    def _register(registry: dict[str, F], factory: F, category: str) -> None:
        type_name = _type_name(factory)
        if type_name in registry:
            raise DuplicateFactoryError(
                f"A factory '{type_name}' já está registrada para {category}.",
                path=type_name,
            )
        registry[type_name] = factory

    @staticmethod
    def _get(registry: dict[str, F], type_name: str, category: str) -> F:
        try:
            return registry[type_name]
        except KeyError as error:
            raise ComponentFactoryNotFoundError(
                f"Não há factory '{type_name}' registrada para {category}.",
                path=type_name,
            ) from error

    def register_provider_factory(self, factory: ModelProviderFactory) -> None:
        """Register one provider factory without overwrite."""
        self._register(self._providers, factory, "providers")

    def get_provider_factory(self, type_name: str) -> ModelProviderFactory:
        """Return one provider factory by exact type."""
        return self._get(self._providers, type_name, "providers")

    def register_tool_factory(self, factory: ToolFactory) -> None:
        """Register one tool factory without overwrite."""
        self._register(self._tools, factory, "ferramentas")

    def get_tool_factory(self, type_name: str) -> ToolFactory:
        """Return one tool factory by exact type."""
        return self._get(self._tools, type_name, "ferramentas")

    def register_memory_factory(self, factory: MemoryFactory) -> None:
        """Register one memory factory without overwrite."""
        self._register(self._memory, factory, "memória")

    def get_memory_factory(self, type_name: str) -> MemoryFactory:
        """Return one memory factory by exact type."""
        return self._get(self._memory, type_name, "memória")

    def register_knowledge_factory(self, factory: KnowledgeFactory) -> None:
        """Register one knowledge factory without overwrite."""
        self._register(self._knowledge, factory, "conhecimento")

    def get_knowledge_factory(self, type_name: str) -> KnowledgeFactory:
        """Return one knowledge factory by exact type."""
        return self._get(self._knowledge, type_name, "conhecimento")

    def register_guardrail_factory(self, factory: GuardrailFactory) -> None:
        """Register one guardrail factory without overwrite."""
        self._register(self._guardrails, factory, "guardrails")

    def get_guardrail_factory(self, type_name: str) -> GuardrailFactory:
        """Return one guardrail factory by exact type."""
        return self._get(self._guardrails, type_name, "guardrails")

    def register_observability_factory(self, factory: ObservabilityFactory) -> None:
        """Register one observability factory without overwrite."""
        self._register(self._observability, factory, "observabilidade")

    def get_observability_factory(self, type_name: str) -> ObservabilityFactory:
        """Return one observability factory by exact type."""
        return self._get(self._observability, type_name, "observabilidade")

    def register_mcp_factory(self, factory: MCPFactory) -> None:
        """Register one MCP factory without overwrite."""
        self._register(self._mcp, factory, "MCP")

    def get_mcp_factory(self, type_name: str) -> MCPFactory:
        """Return one MCP factory by exact type."""
        return self._get(self._mcp, type_name, "MCP")

    def register_adapter_factory(self, factory: AdapterFactory) -> None:
        """Register one adapter factory without overwrite."""
        self._register(self._adapters, factory, "adapters")

    def get_adapter_factory(self, type_name: str) -> AdapterFactory:
        """Return one adapter factory by exact type."""
        return self._get(self._adapters, type_name, "adapters")
