"""Typed asynchronous component factory contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from atlas_agents.adapters import AgentExecutionService
from atlas_agents.config.models import (
    AdapterComponentConfig,
    ComponentConfig,
    ConfigValue,
    KnowledgeComponentConfig,
    MCPComponentConfig,
)
from atlas_agents.config.result import ConfigValidationIssue
from atlas_agents.config.secrets import SecretResolver
from atlas_agents.guardrails import Guardrail
from atlas_agents.knowledge import KnowledgeManager
from atlas_agents.memory import MemoryManager
from atlas_agents.models import ModelProvider
from atlas_agents.observability import ObservabilityManager
from atlas_agents.tools import Tool, ToolRegistry


class OwnedResource(Protocol):
    """Describe one factory-owned asynchronous resource."""

    async def aclose(self) -> None:
        """Release the owned resource idempotently."""
        ...


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class FactoryProduct[T]:
    """Return one typed component and explicitly owned resources."""

    component: T
    owned_resources: tuple[OwnedResource, ...] = ()


@dataclass(frozen=True, slots=True)
class ConfigurationBuildContext:
    """Provide factories only version and explicit secret resolution."""

    secret_resolver: SecretResolver
    atlas_version: str


@dataclass(frozen=True, slots=True)
class MCPBuildContext:
    """Provide an MCP factory only its required tool registration boundary."""

    configuration: ConfigurationBuildContext
    tool_registry: ToolRegistry


@dataclass(frozen=True, slots=True)
class AdapterBuildContext:
    """Provide an adapter factory only the shared execution facade."""

    configuration: ConfigurationBuildContext
    execution_service: AgentExecutionService


class MCPIntegration(Protocol):
    """Expose stable MCP integration identity without dynamic lookup."""

    @property
    def component_id(self) -> str:
        """Return the configured MCP component ID."""
        ...


class ExternalAdapter(Protocol):
    """Expose stable adapter identity without prescribing transport lifecycle."""

    @property
    def component_id(self) -> str:
        """Return the configured adapter component ID."""
        ...


class _FactoryBase(Protocol):
    @property
    def type_name(self) -> str:
        """Return the stable declarative type name."""
        ...

    def validate_config(
        self, config: dict[str, ConfigValue]
    ) -> tuple[ConfigValidationIssue, ...]:
        """Validate factory-specific config synchronously without side effects."""
        ...


class ModelProviderFactory(_FactoryBase, Protocol):
    """Construct one provider implementing the core model contract."""

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[ModelProvider]:
        """Build a provider and report resources owned by the composition."""
        ...


class ToolFactory(_FactoryBase, Protocol):
    """Construct one executable core tool."""

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[Tool]:
        """Build a tool and report resources owned by the composition."""
        ...


class MemoryFactory(_FactoryBase, Protocol):
    """Construct the runtime memory manager boundary."""

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[MemoryManager]:
        """Build a memory manager and report owned resources."""
        ...


class KnowledgeFactory(_FactoryBase, Protocol):
    """Construct the runtime knowledge manager boundary."""

    async def create(
        self,
        component_id: str,
        config: KnowledgeComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[KnowledgeManager]:
        """Build a knowledge manager and report owned resources."""
        ...


class GuardrailFactory(_FactoryBase, Protocol):
    """Construct one core guardrail implementation."""

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[Guardrail[object]]:
        """Build a guardrail and report owned resources."""
        ...


class ObservabilityFactory(_FactoryBase, Protocol):
    """Construct one runtime observability manager."""

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[ObservabilityManager]:
        """Build observability and report owned resources."""
        ...


class MCPFactory(_FactoryBase, Protocol):
    """Construct one MCP integration with explicit import allowlist."""

    async def create(
        self, component_id: str, config: MCPComponentConfig, context: MCPBuildContext
    ) -> FactoryProduct[MCPIntegration]:
        """Build MCP integration without implicit tool imports or startup."""
        ...


class AdapterFactory(_FactoryBase, Protocol):
    """Construct one external adapter without starting its server."""

    async def create(
        self,
        component_id: str,
        config: AdapterComponentConfig,
        context: AdapterBuildContext,
    ) -> FactoryProduct[ExternalAdapter]:
        """Build an adapter object and report owned resources."""
        ...
