"""Reusable doubles for plugin lifecycle tests."""

from collections.abc import AsyncIterator

from atlas_agents import (
    GuardrailContext,
    GuardrailDecision,
    GuardrailResult,
    GuardrailStage,
    KnowledgeQuery,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalResult,
    KnowledgeSource,
    MemoryQuery,
    MemoryRecord,
    MemoryScope,
    MemorySearchResult,
    MemoryWriteRequest,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ObservabilityAttributes,
    Plugin,
    PluginCapability,
    PluginContext,
    PluginContributionDescriptor,
    PluginContributionValue,
    PluginManifest,
    PluginMetadata,
    Span,
    SpanKind,
    Tool,
    ToolDefinition,
    ToolExecutionContext,
    ToolOutput,
    TraceContext,
)


class FakeProvider(ModelProvider):
    """Minimal provider used only for registry identity."""

    def __init__(self, name: str = "fake") -> None:
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return ()

    async def generate(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> ModelResponse:
        raise NotImplementedError

    def stream(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> AsyncIterator[ModelStreamEvent]:
        del request, context
        return self._empty_stream()

    async def _empty_stream(self) -> AsyncIterator[ModelStreamEvent]:
        if False:
            yield


class FakeTool(Tool):
    """Minimal named tool."""

    def __init__(self, name: str = "weather") -> None:
        self._definition = ToolDefinition(
            name=name,
            description="Ferramenta de teste.",
            parameters={"type": "object", "additionalProperties": False},
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(
        self, arguments: dict[str, object], context: ToolExecutionContext
    ) -> ToolOutput:
        del arguments, context
        return ToolOutput(content={"ok": True})


class FakeGuardrail:
    """Minimal guardrail used only for registry identity."""

    def __init__(self, guardrail_id: str = "safe") -> None:
        self._guardrail_id = guardrail_id

    @property
    def guardrail_id(self) -> str:
        return self._guardrail_id

    @property
    def stage(self) -> GuardrailStage:
        return GuardrailStage.INPUT

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


class FakeEvaluator:
    """Minimal evaluator identity accepted through the structural boundary."""

    def __init__(self, evaluator_id: str = "exact") -> None:
        self._evaluator_id = evaluator_id

    @property
    def evaluator_id(self) -> str:
        return self._evaluator_id


class FakeMemoryStore:
    """No-op memory store for unmanaged contribution tests."""

    async def get(self, memory_id: str, *, scope: MemoryScope) -> MemoryRecord | None:
        del memory_id, scope
        return None

    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        raise NotImplementedError

    async def search(self, query: MemoryQuery) -> tuple[MemorySearchResult, ...]:
        del query
        return ()

    async def delete(self, memory_id: str, *, scope: MemoryScope) -> bool:
        del memory_id, scope
        return False


class FakeRetriever:
    """No-op knowledge retriever for unmanaged contribution tests."""

    async def sources(self) -> tuple[KnowledgeSource, ...]:
        return ()

    async def retrieve(
        self, query: KnowledgeQuery, context: KnowledgeRetrievalContext
    ) -> tuple[KnowledgeRetrievalResult, ...]:
        del query, context
        return ()


class FakeTracer:
    """Minimal tracer adapter identity."""

    def start_span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: TraceContext | None = None,
        attributes: ObservabilityAttributes | None = None,
    ) -> Span:
        raise NotImplementedError


class FakePlugin(Plugin):
    """Configurable plugin with lifecycle call recording."""

    def __init__(
        self,
        *,
        plugin_id: str = "acme.test",
        capabilities: tuple[PluginCapability, ...] = (PluginCapability.TOOL,),
        required_atlas_version: str = ">=0.1,<1",
        descriptors: tuple[PluginContributionDescriptor, ...] = (),
        contributions: tuple[PluginContributionValue, ...] = (),
        describe_error: Exception | None = None,
        activate_error: BaseException | None = None,
        deactivate_error: BaseException | None = None,
    ) -> None:
        self._manifest = PluginManifest(
            metadata=PluginMetadata(
                plugin_id=plugin_id,
                name="Plugin de teste",
                version="1.0.0",
            ),
            capabilities=capabilities,
            required_atlas_version=required_atlas_version,
        )
        self.descriptors = descriptors
        self.contribution_values = contributions
        self.describe_error = describe_error
        self.activate_error = activate_error
        self.deactivate_error = deactivate_error
        self.describe_calls = 0
        self.activate_calls = 0
        self.deactivate_calls = 0
        self.contexts: list[PluginContext] = []

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def describe(
        self, context: PluginContext
    ) -> tuple[PluginContributionDescriptor, ...]:
        self.describe_calls += 1
        self.contexts.append(context)
        if self.describe_error is not None:
            raise self.describe_error
        return self.descriptors

    async def activate(
        self, context: PluginContext
    ) -> tuple[PluginContributionValue, ...]:
        self.activate_calls += 1
        self.contexts.append(context)
        if self.activate_error is not None:
            raise self.activate_error
        return self.contribution_values

    async def deactivate(self, context: PluginContext) -> None:
        self.deactivate_calls += 1
        self.contexts.append(context)
        if self.deactivate_error is not None:
            raise self.deactivate_error


class FakeDistribution:
    """Entry-point distribution metadata double."""

    def __init__(self, name: str, version: str = "1.0.0") -> None:
        self.name = name
        self.version = version


class FakeEntryPoint:
    """Loadable entry-point double with call tracking."""

    def __init__(
        self,
        name: str,
        value: str,
        factory: object,
        *,
        group: str = "atlas_agents.plugins",
        distribution: FakeDistribution | None = None,
        load_error: Exception | None = None,
    ) -> None:
        self.name = name
        self.value = value
        self.group = group
        self.dist = distribution
        self.factory = factory
        self.load_error = load_error
        self.load_calls = 0

    def load(self) -> object:
        self.load_calls += 1
        if self.load_error is not None:
            raise self.load_error
        return self.factory
