"""Deterministic host-side implementations shared by official examples."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentRuntime,
    ApprovalContext,
    ApprovalRequired,
    CheckpointStore,
    ExecutionCheckpoint,
    FinishReason,
    GuardrailManager,
    KnowledgeManager,
    MemoryManager,
    MemoryQuery,
    MemoryRecord,
    MemoryScope,
    MemorySearchResult,
    MemoryWriteRequest,
    ModelCapability,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelUsage,
    ObservabilityAttributeValue,
    ObservabilityManager,
    ResumeToken,
    SpanKind,
    SpanStatus,
    TextContent,
    Tool,
    ToolCall,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutionRequest,
    ToolExecutor,
    ToolOutput,
    ToolRegistry,
    TraceContext,
)


def text_response(text: str) -> ModelResponse:
    """Create a deterministic terminal response."""
    return ModelResponse(
        model="example-model",
        content=(TextContent(text=text),),
        finish_reason=FinishReason.STOP,
        usage=ModelUsage(input_tokens=4, output_tokens=4, total_tokens=8),
    )


def tool_response(
    name: str,
    arguments: dict[str, object],
    *,
    tool_call_id: str = "call-1",
) -> ModelResponse:
    """Create a deterministic tool-call response."""
    return ModelResponse(
        model="example-model",
        tool_calls=(
            ToolCall(tool_call_id=tool_call_id, name=name, arguments=arguments),
        ),
        finish_reason=FinishReason.TOOL_CALL,
        usage=ModelUsage(input_tokens=4, output_tokens=2, total_tokens=6),
    )


def text_stream(*parts: str) -> tuple[ModelStreamEvent, ...]:
    """Create a valid deterministic provider stream."""
    events = [
        ModelStreamEvent(
            type=ModelStreamEventType.RESPONSE_STARTED,
            sequence=1,
            response_id="stream-1",
            data={"model": "example-model"},
        )
    ]
    events.extend(
        ModelStreamEvent(
            type=ModelStreamEventType.TEXT_DELTA,
            sequence=index,
            response_id="stream-1",
            data={"text": part},
        )
        for index, part in enumerate(parts, start=2)
    )
    events.extend(
        (
            ModelStreamEvent(
                type=ModelStreamEventType.USAGE_UPDATED,
                sequence=len(events) + 1,
                response_id="stream-1",
                data={
                    "usage": {
                        "input_tokens": 2,
                        "output_tokens": len(parts),
                        "total_tokens": 2 + len(parts),
                    }
                },
            ),
            ModelStreamEvent(
                type=ModelStreamEventType.RESPONSE_COMPLETED,
                sequence=len(events) + 2,
                response_id="stream-1",
                data={"model": "example-model", "finish_reason": "stop"},
            ),
        )
    )
    return tuple(events)


class ScriptedModelProvider(ModelProvider):
    """Return host-supplied responses without network access."""

    def __init__(
        self,
        responses: tuple[ModelResponse, ...],
        *,
        stream_events: tuple[ModelStreamEvent, ...] = (),
        capabilities: frozenset[ModelCapability] | None = None,
    ) -> None:
        self.responses = responses
        self.stream_events = stream_events
        self.requests: list[ModelRequest] = []
        self._capabilities = capabilities or frozenset(
            {
                ModelCapability.TEXT_GENERATION,
                ModelCapability.STREAMING,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.TOOL_CALLING,
            }
        )

    @property
    def provider_name(self) -> str:
        return "example"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider=self.provider_name,
                model="example-model",
                capabilities=self._capabilities,
            ),
        )

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        del context
        self.requests.append(request)
        return self.responses[len(self.requests) - 1]

    def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        del request, context
        return self._stream()

    async def _stream(self) -> AsyncIterator[ModelStreamEvent]:
        for event in self.stream_events:
            yield event


class LocalTool(Tool):
    """Execute one injected deterministic function."""

    def __init__(
        self,
        definition: ToolDefinition,
        function: Callable[[dict[str, object]], object],
    ) -> None:
        self._definition = definition
        self._function = function
        self.calls = 0

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        del context
        self.calls += 1
        return ToolOutput(content=self._function(arguments))


class InMemoryCheckpointStore:
    """Keep resumable checkpoints only for the lifetime of an example."""

    def __init__(self) -> None:
        self._items: dict[str, ExecutionCheckpoint] = {}

    async def save(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
    ) -> None:
        self._items[resume_token.value] = checkpoint

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        return self._items.pop(resume_token.value)


class InMemoryMemoryStore:
    """Store scoped example memories without infrastructure."""

    def __init__(self) -> None:
        self.records: dict[str, MemoryRecord] = {}

    async def get(
        self,
        memory_id: str,
        *,
        scope: MemoryScope,
    ) -> MemoryRecord | None:
        record = self.records.get(memory_id)
        return record if record is not None and record.scope == scope else None

    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        now = datetime.now(UTC)
        record = MemoryRecord(
            memory_id=f"memory-{len(self.records) + 1}",
            memory_type=request.memory_type,
            scope=request.scope,
            content=request.content,
            created_at=now,
            updated_at=now,
            expires_at=request.expires_at,
            metadata=request.metadata,
        )
        self.records[record.memory_id] = record
        return record

    async def search(self, query: MemoryQuery) -> tuple[MemorySearchResult, ...]:
        matches = (
            record
            for record in self.records.values()
            if record.scope == query.scope and record.memory_type is query.memory_type
        )
        return tuple(MemorySearchResult(record=item) for item in matches)[: query.limit]

    async def delete(self, memory_id: str, *, scope: MemoryScope) -> bool:
        if await self.get(memory_id, scope=scope) is None:
            return False
        del self.records[memory_id]
        return True


@dataclass
class RecordingSpan:
    """Record safe span operations for the observability example."""

    name: str
    context: TraceContext | None
    attributes: dict[str, ObservabilityAttributeValue] = field(default_factory=dict)

    def set_attribute(self, name: str, value: ObservabilityAttributeValue) -> None:
        self.attributes[name] = value

    def add_event(
        self,
        name: str,
        attributes: dict[str, ObservabilityAttributeValue] | None = None,
    ) -> None:
        del name, attributes

    def record_exception(self, error: BaseException) -> None:
        del error

    def set_status(self, status: SpanStatus, description: str | None = None) -> None:
        del status, description

    def end(self) -> None:
        return None


class RecordingTracer:
    """Create content-free spans and retain only their names."""

    def __init__(self) -> None:
        self.spans: list[RecordingSpan] = []

    def start_span(
        self,
        name: str,
        *,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: TraceContext | None = None,
        attributes: dict[str, ObservabilityAttributeValue] | None = None,
    ) -> RecordingSpan:
        del kind, parent
        index = len(self.spans) + 1
        span = RecordingSpan(
            name=name,
            context=TraceContext(trace_id=f"trace-{index}", span_id=f"span-{index}"),
            attributes=dict(attributes or {}),
        )
        self.spans.append(span)
        return span


class RecordingMetrics:
    """Record metric names without retaining prompts or arguments."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def increment(
        self,
        name: str,
        value: int | float = 1,
        *,
        attributes: dict[str, ObservabilityAttributeValue] | None = None,
    ) -> None:
        del value, attributes
        self.names.append(name)

    def record(
        self,
        name: str,
        value: int | float,
        *,
        attributes: dict[str, ObservabilityAttributeValue] | None = None,
    ) -> None:
        del value, attributes
        self.names.append(name)


class RequireApproval:
    """Require human approval for every policy-controlled tool call."""

    def evaluate_tool(
        self,
        *,
        tool: ToolDefinition,
        request: ToolExecutionRequest,
        context: ApprovalContext,
    ) -> ApprovalRequired:
        del tool, request, context
        return ApprovalRequired(
            reason="A operação produz um efeito externo simulado.",
            summary="Autorizar a execução da ferramenta?",
        )


def build_runtime(
    provider: ScriptedModelProvider,
    *,
    tools: tuple[Tool, ...] = (),
    checkpoint_store: CheckpointStore | None = None,
    memory_manager: MemoryManager | None = None,
    knowledge_manager: KnowledgeManager | None = None,
    guardrail_manager: GuardrailManager | None = None,
    observability_manager: ObservabilityManager | None = None,
) -> AgentRuntime:
    """Compose a runtime from explicit public Atlas contracts."""
    models = ModelProviderRegistry()
    models.register(provider)
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return AgentRuntime(
        model_registry=models,
        tool_registry=registry,
        tool_executor=ToolExecutor(registry=registry),
        checkpoint_store=checkpoint_store,
        memory_manager=memory_manager,
        knowledge_manager=knowledge_manager,
        guardrail_manager=guardrail_manager,
        observability_manager=observability_manager,
    )


def agent(*, tools: tuple[str, ...] = ()) -> AgentDefinition:
    """Create the common deterministic example agent."""
    return AgentDefinition(
        agent_id="example-agent",
        name="Agente de exemplo",
        instructions="Responda de forma objetiva usando somente os dados fornecidos.",
        tool_names=tools,
    )


def input_and_context(
    message: str,
    *,
    execution_id: str = "example-execution",
) -> tuple[AgentInput, AgentContext]:
    """Create explicit input and execution context values."""
    return AgentInput(message=message), AgentContext(execution_id=execution_id)
