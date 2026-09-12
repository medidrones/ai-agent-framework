from collections.abc import AsyncIterator

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentRuntime,
    CheckpointStore,
    ExecutionCheckpoint,
    FinishReason,
    ModelCapability,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelUsage,
    ResumeToken,
    TextContent,
    Tool,
    ToolApprovalMode,
    ToolCall,
    ToolDefinition,
    ToolExecutionContext,
    ToolOutput,
    ToolRegistry,
)
from atlas_agents.evaluation import (
    AgentRuntimeEvaluationExecutor,
    EvaluationCase,
    EvaluationInput,
)


class Provider(ModelProvider):
    def __init__(self, response: ModelResponse) -> None:
        self.response = response
        self.generate_calls = 0

    @property
    def provider_name(self) -> str:
        return "fake"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider="fake",
                model="model",
                capabilities=frozenset(
                    {
                        ModelCapability.TEXT_GENERATION,
                        ModelCapability.TOOL_CALLING,
                    }
                ),
            ),
        )

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        del request, context
        self.generate_calls += 1
        return self.response

    def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        del request, context
        return self._empty_stream()

    async def _empty_stream(self) -> AsyncIterator[ModelStreamEvent]:
        if False:
            yield ModelStreamEvent.model_started(
                response_id="unused",
                model="unused",
            )


class SensitiveTool(Tool):
    call_count = 0

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="sensitive",
            description="Executa operação sensível.",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            approval_mode=ToolApprovalMode.REQUIRED,
        )

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        del arguments, context
        self.call_count += 1
        return ToolOutput(content={"ok": True})


def response(finish_reason: FinishReason = FinishReason.STOP) -> ModelResponse:
    return ModelResponse(
        response_id="response",
        model="model",
        content=(TextContent(text="resultado"),),
        finish_reason=finish_reason,
        usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
    )


def runtime(provider: Provider, *, tool: SensitiveTool | None = None) -> AgentRuntime:
    models = ModelProviderRegistry()
    models.register(provider)
    tools = ToolRegistry()
    if tool is not None:
        tools.register(tool)
    return AgentRuntime(
        model_registry=models,
        tool_registry=tools,
        checkpoint_store=MemoryCheckpointStore(),
    )


class MemoryCheckpointStore(CheckpointStore):
    def __init__(self) -> None:
        self.items: dict[str, ExecutionCheckpoint] = {}

    async def save(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
    ) -> None:
        self.items[resume_token.value] = checkpoint

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        return self.items.pop(resume_token.value)


def case() -> EvaluationCase:
    return EvaluationCase(
        case_id="case-id",
        name="Caso",
        input=EvaluationInput(agent_input=AgentInput(message="entrada")),
    )


async def test_runtime_executor_uses_public_run_and_distinct_execution_id() -> None:
    provider = Provider(response())
    executor = AgentRuntimeEvaluationExecutor(
        runtime=runtime(provider),
        agent=AgentDefinition(
            agent_id="agent",
            name="Agente",
            instructions="Responda.",
        ),
        context_factory=lambda _: AgentContext(execution_id="execution-id"),
    )

    observation = await executor.execute(case())

    assert provider.generate_calls == 1
    assert observation.execution_id == "execution-id"
    assert observation.execution_id != "case-id"
    assert observation.output == "resultado"
    assert observation.status.value == "completed"


async def test_runtime_failed_result_is_valid_observation() -> None:
    executor = AgentRuntimeEvaluationExecutor(
        runtime=runtime(Provider(response(FinishReason.ERROR))),
        agent=AgentDefinition(
            agent_id="agent",
            name="Agente",
            instructions="Responda.",
        ),
        context_factory=lambda _: AgentContext(execution_id="execution"),
    )

    observation = await executor.execute(case())

    assert observation.status.value == "failed"
    assert observation.error_code is not None


async def test_runtime_suspension_is_observed_without_auto_approval_or_token() -> None:
    tool_call = ToolCall(
        tool_call_id="call",
        name="sensitive",
        arguments={"value": "segredo"},
    )
    provider = Provider(
        ModelResponse(
            response_id="response",
            model="model",
            tool_calls=(tool_call,),
            finish_reason=FinishReason.TOOL_CALL,
            usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
        )
    )
    tool = SensitiveTool()
    executor = AgentRuntimeEvaluationExecutor(
        runtime=runtime(provider, tool=tool),
        agent=AgentDefinition(
            agent_id="agent",
            name="Agente",
            instructions="Responda.",
            tool_names=("sensitive",),
        ),
        context_factory=lambda _: AgentContext(execution_id="execution"),
    )

    observation = await executor.execute(case())

    assert observation.suspended is True
    assert observation.status.value == "waiting_for_approval"
    assert tool.call_count == 0
    serialized = observation.model_dump_json()
    assert "segredo" not in serialized
    assert "resume" not in serialized
