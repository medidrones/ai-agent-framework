"""Explicit phased construction and lifecycle for declarative composition."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.metadata import version as distribution_version
from types import MappingProxyType
from typing import cast

from pydantic import JsonValue

from atlas_agents.adapters import (
    AgentAccessPolicy,
    AgentExecutionService,
    AgentRegistry,
    ExecutionIdentityMapper,
    ExecutionPolicyResolver,
    IdempotencyStore,
)
from atlas_agents.agents import AgentDefinition
from atlas_agents.approvals import (
    ApprovalDecisionValidator,
    ApprovalPolicy,
)
from atlas_agents.config.errors import (
    ComponentBuildError,
    ComponentFactoryNotFoundError,
    CompositionBuildError,
    CompositionCloseError,
    ConfigError,
    ConfigReferenceError,
    ConfigValidationError,
)
from atlas_agents.config.factories import (
    AdapterBuildContext,
    ConfigurationBuildContext,
    ExternalAdapter,
    FactoryProduct,
    MCPBuildContext,
    MCPIntegration,
    OwnedResource,
)
from atlas_agents.config.models import (
    AgentConfig,
    AtlasConfig,
    ConfigValue,
)
from atlas_agents.config.registry import ConfigurationFactoryRegistry
from atlas_agents.config.result import ConfigValidationIssue
from atlas_agents.config.secrets import (
    RejectingSecretResolver,
    SecretReference,
    SecretResolver,
)
from atlas_agents.config.validation import ConfigurationValidator
from atlas_agents.guardrails import (
    AgentGuardrailConfig as CoreAgentGuardrailConfig,
)
from atlas_agents.guardrails import (
    GuardrailManager,
    GuardrailRegistry,
)
from atlas_agents.knowledge import (
    AgentKnowledgeConfig as CoreAgentKnowledgeConfig,
)
from atlas_agents.knowledge import (
    KnowledgeContextRenderer,
    KnowledgeManager,
    KnowledgeQueryBuilder,
)
from atlas_agents.memory import (
    AgentMemoryConfig as CoreAgentMemoryConfig,
)
from atlas_agents.memory import (
    MemoryContextRenderer,
    MemoryManager,
    MemoryScopePolicy,
    MemoryWritePolicy,
)
from atlas_agents.models import (
    ModelProvider,
    ModelProviderRegistry,
    ModelSelectionRequest,
)
from atlas_agents.observability import ObservabilityManager
from atlas_agents.plugins import Plugin, PluginManager
from atlas_agents.runtime import (
    AgentRuntime,
    CheckpointStore,
    ExecutionBudget,
    ExecutionLimits,
)
from atlas_agents.tools import Tool, ToolExecutor, ToolRegistry


@dataclass(frozen=True, slots=True)
class RuntimeDependencies:
    """Carry optional caller-owned runtime collaborators not defined by config v1."""

    tool_executor_factory: Callable[[ToolRegistry], ToolExecutor] | None = None
    approval_policy: ApprovalPolicy | None = None
    approval_decision_validator: ApprovalDecisionValidator | None = None
    checkpoint_store: CheckpointStore | None = None
    memory_scope_policy: MemoryScopePolicy | None = None
    memory_context_renderer: MemoryContextRenderer | None = None
    memory_write_policy: MemoryWritePolicy | None = None
    knowledge_query_builder: KnowledgeQueryBuilder | None = None
    knowledge_context_renderer: KnowledgeContextRenderer | None = None


@dataclass(frozen=True, slots=True)
class ExternalExecutionDependencies:
    """Carry explicit security policies required by external adapters."""

    identity_mapper: ExecutionIdentityMapper
    access_policy: AgentAccessPolicy
    policy_resolver: ExecutionPolicyResolver
    idempotency_store: IdempotencyStore | None = None


def configuration_fingerprint(config: AtlasConfig) -> str:
    """Hash canonical effective config containing references, never secret values."""
    canonical = json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AtlasComposition:
    """Expose explicit typed outputs and own only factory-created resources."""

    def __init__(
        self,
        *,
        config: AtlasConfig,
        model_provider_registry: ModelProviderRegistry,
        tool_registry: ToolRegistry,
        guardrail_registry: GuardrailRegistry,
        agent_registry: AgentRegistry,
        runtime: AgentRuntime,
        memory_manager: MemoryManager | None,
        knowledge_manager: KnowledgeManager | None,
        observability_manager: ObservabilityManager,
        execution_service: AgentExecutionService | None,
        plugin_manager: PluginManager,
        active_plugins: tuple[str, ...],
        model_selections: Mapping[str, ModelSelectionRequest],
        mcp_integrations: tuple[MCPIntegration, ...],
        adapters: tuple[ExternalAdapter, ...],
        owned_resources: tuple[OwnedResource, ...],
    ) -> None:
        """Store immutable views plus private lifecycle state."""
        self.config = config
        self.configuration_fingerprint = configuration_fingerprint(config)
        self.model_provider_registry = model_provider_registry
        self.tool_registry = tool_registry
        self.guardrail_registry = guardrail_registry
        self.agent_registry = agent_registry
        self.runtime = runtime
        self.memory_manager = memory_manager
        self.knowledge_manager = knowledge_manager
        self.observability_manager = observability_manager
        self.execution_service = execution_service
        self.plugin_manager = plugin_manager
        self.model_selections = MappingProxyType(dict(model_selections))
        self.mcp_integrations = mcp_integrations
        self.adapters = adapters
        self._active_plugins = active_plugins
        self._owned_resources = owned_resources
        self._close_lock = asyncio.Lock()
        self._closed = False

    @property
    def closed(self) -> bool:
        """Return whether lifecycle cleanup has already run."""
        return self._closed

    async def __aenter__(self) -> AtlasComposition:
        """Return this already-built composition."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Close owned resources on context exit."""
        del exc_type, exc_value, traceback
        await self.close()

    async def close(self) -> None:
        """Close owned resources and plugins in reverse construction order once."""
        async with self._close_lock:
            if self._closed:
                return
            self._closed = True
            failures = await _cleanup(
                self._owned_resources,
                self.plugin_manager,
                self._active_plugins,
            )
            if failures:
                raise CompositionCloseError(
                    f"O fechamento terminou com {len(failures)} falha(s)."
                ) from failures[0]


async def _cleanup(
    resources: tuple[OwnedResource, ...],
    plugin_manager: PluginManager,
    active_plugins: tuple[str, ...],
) -> tuple[Exception, ...]:
    failures: list[Exception] = []
    for resource in reversed(resources):
        try:
            await resource.aclose()
        except asyncio.CancelledError:
            failures.append(RuntimeError("O cleanup de um recurso foi cancelado."))
        except Exception as error:
            failures.append(error)
    for plugin_id in reversed(active_plugins):
        try:
            await plugin_manager.deactivate(plugin_id)
        except asyncio.CancelledError:
            failures.append(RuntimeError("A desativação de plugin foi cancelada."))
        except Exception as error:
            failures.append(error)
    return tuple(failures)


class AtlasCompositionBuilder:
    """Build independent compositions through explicit dependency phases."""

    def __init__(
        self,
        *,
        factories: ConfigurationFactoryRegistry,
        secret_resolver: SecretResolver | None = None,
        plugins: tuple[Plugin, ...] = (),
        runtime_dependencies: RuntimeDependencies | None = None,
        external_execution_dependencies: ExternalExecutionDependencies | None = None,
        atlas_version: str | None = None,
    ) -> None:
        """Store reusable collaborators without retaining current-build state."""
        self._factories = factories
        self._secret_resolver = secret_resolver or RejectingSecretResolver()
        self._plugins = plugins
        self._runtime_dependencies = runtime_dependencies or RuntimeDependencies()
        self._external_dependencies = external_execution_dependencies
        self._atlas_version = atlas_version or distribution_version("atlas-agent-core")

    async def build(self, config: AtlasConfig) -> AtlasComposition:
        """Preflight, construct in phases, and cleanup any partial build."""
        self._preflight(config)
        resources: list[OwnedResource] = []
        active_plugins: list[str] = []
        plugin_manager: PluginManager | None = None
        try:
            model_registry = ModelProviderRegistry()
            tool_registry = ToolRegistry()
            guardrail_registry = GuardrailRegistry()
            plugin_manager = self._plugin_manager(
                model_registry, tool_registry, guardrail_registry
            )
            await self._activate_plugins(config, plugin_manager, active_plugins)

            context = ConfigurationBuildContext(
                secret_resolver=self._secret_resolver,
                atlas_version=self._atlas_version,
            )
            await self._build_providers(config, context, model_registry, resources)
            await self._build_tools(config, context, tool_registry, resources)
            memory_manager = await self._build_memory(config, context, resources)
            knowledge_manager = await self._build_knowledge(config, context, resources)
            await self._build_guardrails(config, context, guardrail_registry, resources)
            observability_manager = await self._build_observability(
                config, context, resources
            )

            definitions, selections = self._build_agents(config)
            guardrail_manager = (
                GuardrailManager(guardrail_registry)
                if guardrail_registry.guardrails
                else None
            )
            if guardrail_manager is not None:
                for definition in definitions:
                    if definition.guardrails is not None:
                        guardrail_manager.validate_config(definition.guardrails)

            dependencies = self._runtime_dependencies
            tool_executor = (
                None
                if dependencies.tool_executor_factory is None
                else dependencies.tool_executor_factory(tool_registry)
            )
            runtime = AgentRuntime(
                model_registry=model_registry,
                tool_registry=tool_registry,
                tool_executor=tool_executor,
                limits=self._limits(config),
                budget=self._budget(config),
                approval_policy=dependencies.approval_policy,
                approval_decision_validator=dependencies.approval_decision_validator,
                checkpoint_store=dependencies.checkpoint_store,
                memory_manager=memory_manager,
                memory_scope_policy=dependencies.memory_scope_policy,
                memory_context_renderer=dependencies.memory_context_renderer,
                memory_write_policy=dependencies.memory_write_policy,
                knowledge_manager=knowledge_manager,
                knowledge_query_builder=dependencies.knowledge_query_builder,
                knowledge_context_renderer=dependencies.knowledge_context_renderer,
                guardrail_manager=guardrail_manager,
                observability_manager=observability_manager,
            )
            agent_registry = AgentRegistry()
            for definition in definitions:
                agent_registry.register(definition)
            execution_service = self._execution_service(runtime, agent_registry)
            mcp_integrations = await self._build_mcp(
                config, context, tool_registry, resources
            )
            adapters = await self._build_adapters(
                config, context, execution_service, resources
            )
            return AtlasComposition(
                config=config,
                model_provider_registry=model_registry,
                tool_registry=tool_registry,
                guardrail_registry=guardrail_registry,
                agent_registry=agent_registry,
                runtime=runtime,
                memory_manager=memory_manager,
                knowledge_manager=knowledge_manager,
                observability_manager=observability_manager,
                execution_service=execution_service,
                plugin_manager=plugin_manager,
                active_plugins=tuple(active_plugins),
                model_selections=selections,
                mcp_integrations=mcp_integrations,
                adapters=adapters,
                owned_resources=tuple(resources),
            )
        except asyncio.CancelledError:
            if plugin_manager is not None:
                await _cleanup(tuple(resources), plugin_manager, tuple(active_plugins))
            raise
        except Exception as error:
            cleanup_failures: tuple[Exception, ...] = ()
            if plugin_manager is not None:
                cleanup_failures = await _cleanup(
                    tuple(resources), plugin_manager, tuple(active_plugins)
                )
            suffix = (
                " O cleanup parcial também apresentou falhas."
                if cleanup_failures
                else ""
            )
            path = error.path if isinstance(error, ConfigError) else "$"
            raise CompositionBuildError(
                f"A composição declarativa falhou.{suffix}", path=path
            ) from error

    def _preflight(self, config: AtlasConfig) -> None:
        validation = ConfigurationValidator().validate(config)
        if not validation.valid:
            first = validation.errors[0]
            raise ConfigReferenceError(
                f"A configuração possui {len(validation.errors)} "
                "referência(s) inválida(s): "
                f"{first.message}",
                path=first.path,
            )
        issues: list[ConfigValidationIssue] = []
        categories = (
            ("providers", config.providers, self._factories.get_provider_factory),
            ("tools", config.tools, self._factories.get_tool_factory),
            ("memory", config.memory, self._factories.get_memory_factory),
            ("knowledge", config.knowledge, self._factories.get_knowledge_factory),
            ("guardrails", config.guardrails, self._factories.get_guardrail_factory),
            (
                "observability",
                config.observability,
                self._factories.get_observability_factory,
            ),
            ("mcp", config.mcp, self._factories.get_mcp_factory),
            ("adapters", config.adapters, self._factories.get_adapter_factory),
        )
        for category, components, getter in categories:
            for component_id, component in components.items():
                if not component.enabled:
                    continue
                try:
                    factory = getter(component.type)
                except ComponentFactoryNotFoundError:
                    raise ComponentFactoryNotFoundError(
                        f"Não há factory para '{component.type}' em '{category}'.",
                        path=f"$.{category}.{component_id}.type",
                    ) from None
                try:
                    issues.extend(factory.validate_config(component.config))
                except Exception as error:
                    raise ConfigValidationError(
                        "A validação específica da factory falhou.",
                        path=f"$.{category}.{component_id}.config",
                    ) from error
        if issues:
            first = issues[0]
            raise ConfigValidationError(
                f"A configuração específica possui {len(issues)} erro(s): "
                f"{first.message}",
                path=first.path,
            )
        available_plugins = {
            plugin.manifest.metadata.plugin_id for plugin in self._plugins
        }
        for plugin_id in config.plugin_activation:
            if plugin_id not in available_plugins:
                raise ConfigReferenceError(
                    f"O plugin declarado '{plugin_id}' não foi registrado pelo host.",
                    path=f"$.plugins.{plugin_id}",
                )
        if any(item.enabled for item in config.adapters.values()) and (
            self._external_dependencies is None
        ):
            raise ConfigValidationError(
                "Adapters habilitados exigem políticas externas explícitas.",
                path="$.adapters",
            )

    def _plugin_manager(
        self,
        model_registry: ModelProviderRegistry,
        tool_registry: ToolRegistry,
        guardrail_registry: GuardrailRegistry,
    ) -> PluginManager:
        manager = PluginManager(
            atlas_version=self._atlas_version,
            model_provider_registry=model_registry,
            tool_registry=tool_registry,
            guardrail_registry=guardrail_registry,
        )
        for plugin in self._plugins:
            manager.register_plugin(plugin)
        return manager

    async def _activate_plugins(
        self,
        config: AtlasConfig,
        manager: PluginManager,
        active: list[str],
    ) -> None:
        for plugin_id in config.plugin_activation:
            plugin_config = config.plugins[plugin_id]
            values = await self._resolved_plugin_config(plugin_config.config)
            await manager.activate(plugin_id, configuration=values)
            active.append(plugin_id)

    async def _resolved_plugin_config(
        self, values: Mapping[str, ConfigValue]
    ) -> dict[str, JsonValue]:
        return {
            key: await self._resolved_plugin_value(value)
            for key, value in values.items()
        }

    async def _resolved_plugin_value(self, value: ConfigValue) -> JsonValue:
        if isinstance(value, SecretReference):
            secret = await self._secret_resolver.resolve(value)
            return secret.get_secret_value()
        if isinstance(value, list):
            return [await self._resolved_plugin_value(item) for item in value]
        if isinstance(value, dict):
            return {
                key: await self._resolved_plugin_value(item)
                for key, item in value.items()
            }
        return cast("JsonValue", value)

    @staticmethod
    def _record_product[T](
        product: FactoryProduct[T], resources: list[OwnedResource]
    ) -> T:
        if not isinstance(product, FactoryProduct):
            raise ComponentBuildError("A factory retornou um produto inválido.")
        resources.extend(product.owned_resources)
        return product.component

    async def _build_providers(
        self,
        config: AtlasConfig,
        context: ConfigurationBuildContext,
        registry: ModelProviderRegistry,
        resources: list[OwnedResource],
    ) -> None:
        for component_id, component_config in config.providers.items():
            if not component_config.enabled:
                continue
            factory = self._factories.get_provider_factory(component_config.type)
            product = await factory.create(component_id, component_config, context)
            provider = self._record_product(product, resources)
            if not isinstance(provider, ModelProvider):
                raise ComponentBuildError(
                    "A factory de provider retornou um contrato incompatível.",
                    path=f"$.providers.{component_id}",
                )
            if provider.provider_name != component_id:
                raise ComponentBuildError(
                    "O provider construído não coincide com seu component ID.",
                    path=f"$.providers.{component_id}",
                )
            registry.register(provider)

    async def _build_tools(
        self,
        config: AtlasConfig,
        context: ConfigurationBuildContext,
        registry: ToolRegistry,
        resources: list[OwnedResource],
    ) -> None:
        for component_id, component_config in config.tools.items():
            if not component_config.enabled:
                continue
            factory = self._factories.get_tool_factory(component_config.type)
            product = await factory.create(component_id, component_config, context)
            tool = self._record_product(product, resources)
            if not isinstance(tool, Tool):
                raise ComponentBuildError(
                    "A factory de ferramenta retornou um contrato incompatível.",
                    path=f"$.tools.{component_id}",
                )
            if tool.definition.name != component_id:
                raise ComponentBuildError(
                    "A ferramenta construída não coincide com seu component ID.",
                    path=f"$.tools.{component_id}",
                )
            registry.register(tool)

    async def _build_memory(
        self,
        config: AtlasConfig,
        context: ConfigurationBuildContext,
        resources: list[OwnedResource],
    ) -> MemoryManager | None:
        for component_id, component_config in config.memory.items():
            if component_config.enabled:
                factory = self._factories.get_memory_factory(component_config.type)
                manager = self._record_product(
                    await factory.create(component_id, component_config, context),
                    resources,
                )
                if not isinstance(manager, MemoryManager):
                    raise ComponentBuildError(
                        "A factory de memória retornou um contrato incompatível.",
                        path=f"$.memory.{component_id}",
                    )
                return manager
        return None

    async def _build_knowledge(
        self,
        config: AtlasConfig,
        context: ConfigurationBuildContext,
        resources: list[OwnedResource],
    ) -> KnowledgeManager | None:
        for component_id, component_config in config.knowledge.items():
            if component_config.enabled:
                factory = self._factories.get_knowledge_factory(component_config.type)
                manager = self._record_product(
                    await factory.create(component_id, component_config, context),
                    resources,
                )
                if not isinstance(manager, KnowledgeManager):
                    raise ComponentBuildError(
                        "A factory de conhecimento retornou um contrato incompatível.",
                        path=f"$.knowledge.{component_id}",
                    )
                return manager
        return None

    async def _build_guardrails(
        self,
        config: AtlasConfig,
        context: ConfigurationBuildContext,
        registry: GuardrailRegistry,
        resources: list[OwnedResource],
    ) -> None:
        for component_id, component_config in config.guardrails.items():
            if not component_config.enabled:
                continue
            factory = self._factories.get_guardrail_factory(component_config.type)
            guardrail = self._record_product(
                await factory.create(component_id, component_config, context), resources
            )
            if not _is_guardrail(guardrail) or guardrail.guardrail_id != component_id:
                raise ComponentBuildError(
                    "A factory de guardrail retornou um contrato incompatível.",
                    path=f"$.guardrails.{component_id}",
                )
            registry.register(guardrail)

    async def _build_observability(
        self,
        config: AtlasConfig,
        context: ConfigurationBuildContext,
        resources: list[OwnedResource],
    ) -> ObservabilityManager:
        for component_id, component_config in config.observability.items():
            if component_config.enabled:
                factory = self._factories.get_observability_factory(
                    component_config.type
                )
                manager = self._record_product(
                    await factory.create(component_id, component_config, context),
                    resources,
                )
                if not isinstance(manager, ObservabilityManager):
                    raise ComponentBuildError(
                        "A factory de observabilidade retornou um "
                        "contrato incompatível.",
                        path=f"$.observability.{component_id}",
                    )
                return manager
        return ObservabilityManager()

    async def _build_mcp(
        self,
        config: AtlasConfig,
        context: ConfigurationBuildContext,
        tool_registry: ToolRegistry,
        resources: list[OwnedResource],
    ) -> tuple[MCPIntegration, ...]:
        built: list[MCPIntegration] = []
        build_context = MCPBuildContext(
            configuration=context, tool_registry=tool_registry
        )
        for component_id, component_config in config.mcp.items():
            if not component_config.enabled:
                continue
            factory = self._factories.get_mcp_factory(component_config.type)
            integration = self._record_product(
                await factory.create(component_id, component_config, build_context),
                resources,
            )
            if getattr(integration, "component_id", None) != component_id:
                raise ComponentBuildError(
                    "A integração MCP não coincide com seu component ID.",
                    path=f"$.mcp.{component_id}",
                )
            built.append(integration)
        return tuple(built)

    async def _build_adapters(
        self,
        config: AtlasConfig,
        context: ConfigurationBuildContext,
        execution_service: AgentExecutionService | None,
        resources: list[OwnedResource],
    ) -> tuple[ExternalAdapter, ...]:
        enabled = tuple(
            (component_id, item)
            for component_id, item in config.adapters.items()
            if item.enabled
        )
        if not enabled:
            return ()
        if execution_service is None:
            raise ComponentBuildError(
                "A fachada de execução externa não foi configurada.", path="$.adapters"
            )
        build_context = AdapterBuildContext(
            configuration=context, execution_service=execution_service
        )
        built: list[ExternalAdapter] = []
        for component_id, component_config in enabled:
            factory = self._factories.get_adapter_factory(component_config.type)
            adapter = self._record_product(
                await factory.create(component_id, component_config, build_context),
                resources,
            )
            if getattr(adapter, "component_id", None) != component_id:
                raise ComponentBuildError(
                    "O adapter não coincide com seu component ID.",
                    path=f"$.adapters.{component_id}",
                )
            built.append(adapter)
        return tuple(built)

    def _execution_service(
        self, runtime: AgentRuntime, registry: AgentRegistry
    ) -> AgentExecutionService | None:
        dependencies = self._external_dependencies
        if dependencies is None:
            return None
        return AgentExecutionService(
            runtime=runtime,
            agent_registry=registry,
            identity_mapper=dependencies.identity_mapper,
            access_policy=dependencies.access_policy,
            policy_resolver=dependencies.policy_resolver,
            idempotency_store=dependencies.idempotency_store,
        )

    @staticmethod
    def _build_agents(
        config: AtlasConfig,
    ) -> tuple[tuple[AgentDefinition, ...], dict[str, ModelSelectionRequest]]:
        definitions: list[AgentDefinition] = []
        selections: dict[str, ModelSelectionRequest] = {}
        for agent_id, agent in config.agents.items():
            if not agent.enabled:
                continue
            definitions.append(_agent_definition(agent_id, agent))
            if agent.model is not None:
                selections[agent_id] = ModelSelectionRequest(
                    provider=agent.model.provider,
                    model=agent.model.model,
                    required_capabilities=agent.model.required_capabilities,
                    preferred_capabilities=agent.model.preferred_capabilities,
                    minimum_context_window=agent.model.minimum_context_window,
                    minimum_max_output_tokens=agent.model.minimum_max_output_tokens,
                )
        return tuple(definitions), selections

    @staticmethod
    def _limits(config: AtlasConfig) -> ExecutionLimits:
        return ExecutionLimits(**config.atlas.default_limits.model_dump())

    @staticmethod
    def _budget(config: AtlasConfig) -> ExecutionBudget:
        return ExecutionBudget(**config.atlas.default_budget.model_dump())


def _is_guardrail(value: object) -> bool:
    return (
        isinstance(getattr(value, "guardrail_id", None), str)
        and getattr(value, "stage", None) is not None
        and callable(getattr(value, "evaluate", None))
    )


def _agent_definition(agent_id: str, config: AgentConfig) -> AgentDefinition:
    memory = (
        None
        if config.memory is None
        else CoreAgentMemoryConfig(**config.memory.model_dump())
    )
    knowledge = (
        None
        if config.knowledge is None
        else CoreAgentKnowledgeConfig(
            source_ids=config.knowledge.sources,
            max_results=config.knowledge.max_results,
            max_characters=config.knowledge.max_characters,
        )
    )
    guardrails = (
        None
        if config.guardrails is None
        else CoreAgentGuardrailConfig(
            input_guardrails=config.guardrails.input,
            model_output_guardrails=config.guardrails.model_output,
            tool_call_guardrails=config.guardrails.tool_call,
            tool_result_guardrails=config.guardrails.tool_result,
            final_output_guardrails=config.guardrails.final_output,
        )
    )
    return AgentDefinition(
        agent_id=agent_id,
        name=config.name,
        description=config.description,
        instructions=config.instructions,
        tool_names=config.tools,
        memory=memory,
        knowledge=knowledge,
        guardrails=guardrails,
        metadata=dict(config.metadata),
    )
