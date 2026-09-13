from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from atlas_agents.approvals import ToolApprovalMode
from atlas_agents.config import (
    AdapterBuildContext,
    AdapterComponentConfig,
    ComponentConfig,
    ConfigurationBuildContext,
    ConfigurationFactoryRegistry,
    ConfigValidationIssue,
    ConfigValue,
    ExternalAdapter,
    FactoryProduct,
    KnowledgeComponentConfig,
    MCPBuildContext,
    MCPComponentConfig,
    MCPIntegration,
    SecretReference,
)
from atlas_agents.guardrails import (
    GuardrailContext,
    GuardrailDecision,
    GuardrailResult,
    GuardrailStage,
)
from atlas_agents.knowledge import (
    KnowledgeManager,
    KnowledgeQuery,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalResult,
    KnowledgeSource,
)
from atlas_agents.memory import (
    MemoryManager,
    MemoryQuery,
    MemoryRecord,
    MemoryScope,
    MemorySearchResult,
    MemoryWriteRequest,
)
from atlas_agents.models import (
    FinishReason,
    ModelCapability,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelUsage,
    TextContent,
    ToolCall,
)
from atlas_agents.observability import ObservabilityManager
from atlas_agents.plugins import (
    ModelProviderContribution,
    Plugin,
    PluginCapability,
    PluginContext,
    PluginContributionDescriptor,
    PluginContributionValue,
    PluginManifest,
    PluginMetadata,
)
from atlas_agents.tools import Tool, ToolDefinition, ToolExecutionContext, ToolOutput


class FakeResource:
    def __init__(self, name: str, closed_order: list[str] | None = None) -> None:
        self.name = name
        self.close_calls = 0
        self.closed_order = closed_order

    async def aclose(self) -> None:
        self.close_calls += 1
        if self.closed_order is not None:
            self.closed_order.append(self.name)


class FailingResource(FakeResource):
    async def aclose(self) -> None:
        await super().aclose()
        raise RuntimeError("falha de fechamento")


class FakeProvider(ModelProvider):
    def __init__(self, provider_name: str) -> None:
        self._provider_name = provider_name
        self.generate_calls = 0

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider=self.provider_name,
                model="fake-model",
                capabilities=frozenset(
                    {
                        ModelCapability.TEXT_GENERATION,
                        ModelCapability.STREAMING,
                        ModelCapability.TOOL_CALLING,
                    }
                ),
            ),
        )

    async def generate(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> ModelResponse:
        del context
        self.generate_calls += 1
        return ModelResponse(
            model=request.model,
            content=(TextContent(text="Resposta declarativa"),),
            finish_reason=FinishReason.STOP,
            usage=ModelUsage(input_tokens=1, output_tokens=2, total_tokens=3),
        )

    async def stream(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> AsyncIterator[ModelStreamEvent]:
        del request
        yield ModelStreamEvent(
            type=ModelStreamEventType.RESPONSE_STARTED,
            sequence=1,
            response_id=context.request_id,
            timestamp=datetime.now(UTC),
        )
        yield ModelStreamEvent(
            type=ModelStreamEventType.TEXT_DELTA,
            sequence=2,
            response_id=context.request_id,
            data={"text": "Resposta declarativa"},
            timestamp=datetime.now(UTC),
        )
        yield ModelStreamEvent(
            type=ModelStreamEventType.RESPONSE_COMPLETED,
            sequence=3,
            response_id=context.request_id,
            data={
                "model": "fake-model",
                "finish_reason": "stop",
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 2,
                    "total_tokens": 3,
                },
            },
            timestamp=datetime.now(UTC),
        )


class FakeTool(Tool):
    def __init__(
        self,
        name: str,
        approval_mode: ToolApprovalMode = ToolApprovalMode.NOT_REQUIRED,
    ) -> None:
        self._definition = ToolDefinition(
            name=name,
            description="Ferramenta fake",
            parameters={"type": "object", "additionalProperties": False},
            approval_mode=approval_mode,
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(
        self, arguments: dict[str, object], context: ToolExecutionContext
    ) -> ToolOutput:
        del arguments, context
        return ToolOutput(content={"ok": True})


def validation_issues(
    config: dict[str, ConfigValue],
) -> tuple[ConfigValidationIssue, ...]:
    if config.get("invalid") is True:
        return (
            ConfigValidationIssue(
                code="invalid_factory_config",
                path="$.config.invalid",
                message="A configuração específica é inválida.",
            ),
        )
    return ()


class FakeProviderFactory:
    type_name = "fake_provider"

    def __init__(
        self,
        *,
        resource: FakeResource | None = None,
        fail: bool = False,
        cancel: bool = False,
        returned_id: str | None = None,
    ) -> None:
        self.calls = 0
        self.resource = resource
        self.fail = fail
        self.cancel = cancel
        self.returned_id = returned_id
        self.resolved_secret_repr: str | None = None

    def validate_config(
        self, config: dict[str, ConfigValue]
    ) -> tuple[ConfigValidationIssue, ...]:
        return validation_issues(config)

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[ModelProvider]:
        self.calls += 1
        secret = config.config.get("api_key")
        if isinstance(secret, SecretReference):
            resolved = await context.secret_resolver.resolve(secret)
            self.resolved_secret_repr = repr(resolved)
        if self.cancel:
            raise asyncio.CancelledError
        if self.fail:
            raise RuntimeError("detalhe secreto da factory")
        resources = () if self.resource is None else (self.resource,)
        return FactoryProduct(
            component=FakeProvider(self.returned_id or component_id),
            owned_resources=resources,
        )


class FakeToolFactory:
    type_name = "fake_tool"

    def __init__(
        self,
        *,
        fail: bool = False,
        cancel: bool = False,
        returned_id: str | None = None,
    ) -> None:
        self.calls = 0
        self.fail = fail
        self.cancel = cancel
        self.returned_id = returned_id

    def validate_config(
        self, config: dict[str, ConfigValue]
    ) -> tuple[ConfigValidationIssue, ...]:
        return validation_issues(config)

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[Tool]:
        del context
        self.calls += 1
        if self.cancel:
            raise asyncio.CancelledError
        if self.fail:
            raise RuntimeError("falha da ferramenta")
        approval_mode = (
            ToolApprovalMode.REQUIRED
            if config.config.get("approval_required") is True
            else ToolApprovalMode.NOT_REQUIRED
        )
        return FactoryProduct(
            component=FakeTool(self.returned_id or component_id, approval_mode)
        )


class FakeApprovalProvider(FakeProvider):
    async def generate(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> ModelResponse:
        del context
        self.generate_calls += 1
        if self.generate_calls == 1:
            return ModelResponse(
                model=request.model,
                tool_calls=(
                    ToolCall(
                        tool_call_id="call-1",
                        name="sensitive",
                        arguments={},
                    ),
                ),
                finish_reason=FinishReason.TOOL_CALL,
                usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            )
        return ModelResponse(
            model=request.model,
            content=(TextContent(text="Operação aprovada"),),
            finish_reason=FinishReason.STOP,
            usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
        )


class FakeApprovalProviderFactory(FakeProviderFactory):
    type_name = "approval_provider"

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[ModelProvider]:
        del config, context
        self.calls += 1
        return FactoryProduct(component=FakeApprovalProvider(component_id))


class FakeMemoryStore:
    async def get(self, memory_id: str, *, scope: MemoryScope) -> MemoryRecord | None:
        del memory_id, scope
        return None

    async def search(self, query: MemoryQuery) -> tuple[MemorySearchResult, ...]:
        del query
        return ()

    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        now = datetime.now(UTC)
        return MemoryRecord(
            memory_id="memory-1",
            memory_type=request.memory_type,
            scope=request.scope,
            content=request.content,
            created_at=now,
            updated_at=now,
            expires_at=request.expires_at,
            metadata=request.metadata,
        )

    async def delete(self, memory_id: str, *, scope: MemoryScope) -> bool:
        del memory_id, scope
        return False


class FakeMemoryFactory:
    type_name = "fake_memory"

    def validate_config(
        self, config: dict[str, ConfigValue]
    ) -> tuple[ConfigValidationIssue, ...]:
        return validation_issues(config)

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[MemoryManager]:
        del component_id, config, context
        return FactoryProduct(component=MemoryManager(store=FakeMemoryStore()))


class FakeRetriever:
    async def sources(self) -> tuple[KnowledgeSource, ...]:
        return (KnowledgeSource(source_id="docs", name="Documentos"),)

    async def retrieve(
        self, query: KnowledgeQuery, context: KnowledgeRetrievalContext
    ) -> tuple[KnowledgeRetrievalResult, ...]:
        del query, context
        return ()


class FakeKnowledgeFactory:
    type_name = "fake_knowledge"

    def validate_config(
        self, config: dict[str, ConfigValue]
    ) -> tuple[ConfigValidationIssue, ...]:
        return validation_issues(config)

    async def create(
        self,
        component_id: str,
        config: KnowledgeComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[KnowledgeManager]:
        del component_id, config, context
        return FactoryProduct(component=KnowledgeManager(retriever=FakeRetriever()))


class FakeGuardrail:
    def __init__(self, guardrail_id: str) -> None:
        self.guardrail_id = guardrail_id
        self.stage = GuardrailStage.INPUT

    async def evaluate(
        self, value: object, context: GuardrailContext
    ) -> GuardrailResult[object]:
        del context
        return GuardrailResult(
            guardrail_id=self.guardrail_id,
            stage=self.stage,
            decision=GuardrailDecision.ALLOW,
            output=value,
        )


class FakeGuardrailFactory:
    type_name = "fake_guardrail"

    def validate_config(
        self, config: dict[str, ConfigValue]
    ) -> tuple[ConfigValidationIssue, ...]:
        return validation_issues(config)

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[FakeGuardrail]:
        del config, context
        return FactoryProduct(component=FakeGuardrail(component_id))


class FakeObservabilityFactory:
    type_name = "fake_observability"

    def validate_config(
        self, config: dict[str, ConfigValue]
    ) -> tuple[ConfigValidationIssue, ...]:
        return validation_issues(config)

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[ObservabilityManager]:
        del component_id, config, context
        return FactoryProduct(component=ObservabilityManager())


@dataclass(frozen=True)
class FakeMCPIntegration:
    component_id: str
    imported: tuple[str, ...]


class FakeMCPFactory:
    type_name = "fake_mcp"

    def __init__(self) -> None:
        self.includes: tuple[str, ...] | None = None

    def validate_config(
        self, config: dict[str, ConfigValue]
    ) -> tuple[ConfigValidationIssue, ...]:
        return validation_issues(config)

    async def create(
        self,
        component_id: str,
        config: MCPComponentConfig,
        context: MCPBuildContext,
    ) -> FactoryProduct[MCPIntegration]:
        del context
        self.includes = config.import_tools.include
        return FactoryProduct(
            component=FakeMCPIntegration(component_id, config.import_tools.include)
        )


@dataclass(frozen=True)
class FakeAdapter:
    component_id: str
    started: bool = False


class FakeAdapterFactory:
    type_name = "fake_adapter"

    def validate_config(
        self, config: dict[str, ConfigValue]
    ) -> tuple[ConfigValidationIssue, ...]:
        return validation_issues(config)

    async def create(
        self,
        component_id: str,
        config: AdapterComponentConfig,
        context: AdapterBuildContext,
    ) -> FactoryProduct[ExternalAdapter]:
        del config
        assert context.execution_service is not None
        return FactoryProduct(component=FakeAdapter(component_id))


class FakePlugin(Plugin):
    def __init__(self, plugin_id: str = "acme.plugin") -> None:
        self._manifest = PluginManifest(
            metadata=PluginMetadata(
                plugin_id=plugin_id,
                name="Plugin fake",
                version="1.0.0",
            ),
            capabilities=(PluginCapability.MODEL_PROVIDER,),
            required_atlas_version=">=0.1,<1",
        )
        self.activate_calls = 0
        self.deactivate_calls = 0
        self.secret_seen: str | None = None

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def describe(
        self, context: PluginContext
    ) -> tuple[PluginContributionDescriptor, ...]:
        del context
        return (
            PluginContributionDescriptor(
                capability=PluginCapability.MODEL_PROVIDER,
                identifier="plugin-provider",
            ),
        )

    async def activate(
        self, context: PluginContext
    ) -> tuple[PluginContributionValue, ...]:
        self.activate_calls += 1
        value = context.configuration.get("api_key")
        self.secret_seen = value if isinstance(value, str) else None
        return (ModelProviderContribution(FakeProvider("plugin-provider")),)

    async def deactivate(self, context: PluginContext) -> None:
        del context
        self.deactivate_calls += 1


def registry_with_all() -> tuple[
    ConfigurationFactoryRegistry,
    FakeProviderFactory,
    FakeToolFactory,
    FakeMCPFactory,
]:
    registry = ConfigurationFactoryRegistry()
    provider = FakeProviderFactory()
    tool = FakeToolFactory()
    mcp = FakeMCPFactory()
    registry.register_provider_factory(provider)
    registry.register_tool_factory(tool)
    registry.register_memory_factory(FakeMemoryFactory())
    registry.register_knowledge_factory(FakeKnowledgeFactory())
    registry.register_guardrail_factory(FakeGuardrailFactory())
    registry.register_observability_factory(FakeObservabilityFactory())
    registry.register_mcp_factory(mcp)
    registry.register_adapter_factory(FakeAdapterFactory())
    return registry, provider, tool, mcp
