from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import cast

import pytest
from mcp_test_support import FunctionTool, InMemoryTransport

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentGuardrailConfig,
    AgentInput,
    AgentResult,
    AgentRuntime,
    ExecutionLimits,
    FinishReason,
    GuardrailContext,
    GuardrailDecision,
    GuardrailEnforcement,
    GuardrailManager,
    GuardrailRegistry,
    GuardrailResult,
    GuardrailStage,
    GuardrailViolation,
    ModelCapability,
    ModelDescriptor,
    ModelExecutionContext,
    ModelProvider,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelUsage,
    TextContent,
    Tool,
    ToolCall,
    ToolError,
    ToolExecutionContext,
    ToolExecutionRequest,
    ToolExecutionStatus,
    ToolExecutor,
    ToolOutput,
    ToolRegistry,
)
from atlas_agents.mcp import (
    AtlasMCPServer,
    MCPClient,
    MCPConfigurationError,
    MCPConnectionError,
    MCPRemoteTool,
    MCPServerConfig,
    MCPTextContent,
    MCPToolDescriptor,
    MCPToolImporter,
    MCPToolNamingPolicy,
    MCPToolResult,
)


class SequenceProvider(ModelProvider):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "fake"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider="fake",
                model="model",
                capabilities=frozenset(
                    {ModelCapability.TEXT_GENERATION, ModelCapability.TOOL_CALLING}
                ),
            ),
        )

    async def generate(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> ModelResponse:
        del request, context
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                model="model",
                tool_calls=(
                    ToolCall(
                        tool_call_id="call-1",
                        name="remote__double",
                        arguments={"value": 5},
                    ),
                ),
                finish_reason=FinishReason.TOOL_CALL,
                usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            )
        return ModelResponse(
            model="model",
            content=(TextContent(text="Concluído."),),
            finish_reason=FinishReason.STOP,
            usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
        )

    def stream(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> AsyncIterator[ModelStreamEvent]:
        del request, context
        raise AssertionError("Este teste usa run().")


class DuplicateProvider(SequenceProvider):
    async def generate(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> ModelResponse:
        if self.calls < 2:
            self.calls += 1
            return ModelResponse(
                model="model",
                tool_calls=(
                    ToolCall(
                        tool_call_id="same-call",
                        name="remote__double",
                        arguments={"value": 5},
                    ),
                ),
                finish_reason=FinishReason.TOOL_CALL,
                usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            )
        return await super().generate(request, context)


class SlowProvider(SequenceProvider):
    async def generate(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> ModelResponse:
        del request, context
        self.calls += 1
        return ModelResponse(
            model="model",
            tool_calls=(
                ToolCall(
                    tool_call_id="slow-call",
                    name="remote__slow",
                    arguments={"value": 1},
                ),
            ),
            finish_reason=FinishReason.TOOL_CALL,
            usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
        )


class RejectToolCallGuardrail:
    @property
    def guardrail_id(self) -> str:
        return "reject-remote"

    @property
    def stage(self) -> GuardrailStage:
        return GuardrailStage.TOOL_CALL

    async def evaluate(
        self, value: object, context: GuardrailContext
    ) -> GuardrailResult[object]:
        del value, context
        return GuardrailResult(
            guardrail_id=self.guardrail_id,
            stage=self.stage,
            decision=GuardrailDecision.REJECT,
            enforcement=GuardrailEnforcement.EXECUTION,
            violations=(GuardrailViolation(code="blocked", message="Bloqueado."),),
        )


def remote_server(*names: str) -> tuple[AtlasMCPServer, tuple[FunctionTool, ...]]:
    registry = ToolRegistry()
    tools = tuple(
        FunctionTool(name, lambda arguments: {"value": arguments["value"]})
        for name in names
    )
    for tool in tools:
        registry.register(tool)
    return (
        AtlasMCPServer(
            config=MCPServerConfig(
                name="remote", version="1.0", exposed_tool_names=names
            ),
            tool_registry=registry,
            tool_executor=ToolExecutor(registry=registry),
        ),
        tools,
    )


@pytest.mark.asyncio
async def test_import_is_explicit_allowlisted_and_alias_calls_canonical_name() -> None:
    server, (remote,) = remote_server("double")
    registry = ToolRegistry()
    async with MCPClient(InMemoryTransport(server)) as client:
        importer = MCPToolImporter(
            client=client, registry=registry, server_alias="remote"
        )
        assert registry.tools() == ()
        assert (await client.list_tools())[0].name == "double"
        assert registry.tools() == ()
        assert await importer.import_tools() == ()
        (tool,) = await importer.import_tools(include_names=frozenset({"double"}))
        assert tool.remote_tool_name == "double"
        assert tool.local_tool_name == "remote__double"

        result = await ToolExecutor(registry=registry).execute(
            ToolExecutionRequest(
                tool_call_id="call", tool_name="remote__double", arguments={"value": 3}
            ),
            ToolExecutionContext(
                execution_id="execution",
                agent_id="agent",
                tool_call_id="call",
            ),
        )
        assert result.status is ToolExecutionStatus.SUCCEEDED
    assert remote.calls == 1


@pytest.mark.asyncio
async def test_permission_denial_happens_before_remote_call() -> None:
    server, (remote,) = remote_server("double")
    registry = ToolRegistry()
    async with MCPClient(InMemoryTransport(server)) as client:
        importer = MCPToolImporter(
            client=client, registry=registry, server_alias="remote"
        )
        await importer.import_tools(
            include_names=frozenset({"double"}),
            required_permissions=frozenset({"remote.execute"}),
        )
        result = await ToolExecutor(registry=registry).execute(
            ToolExecutionRequest(
                tool_call_id="call", tool_name="remote__double", arguments={"value": 3}
            ),
            ToolExecutionContext(
                execution_id="execution", agent_id="agent", tool_call_id="call"
            ),
        )
        assert result.status is ToolExecutionStatus.DENIED
    assert remote.calls == 0


@pytest.mark.asyncio
async def test_fake_model_runtime_treats_remote_tool_as_normal_tool() -> None:
    server, (remote,) = remote_server("double")
    tool_registry = ToolRegistry()
    model_registry = ModelProviderRegistry()
    model_registry.register(SequenceProvider())
    async with MCPClient(InMemoryTransport(server)) as client:
        await MCPToolImporter(
            client=client, registry=tool_registry, server_alias="remote"
        ).import_tools(include_names=frozenset({"double"}))
        runtime = AgentRuntime(
            model_registry=model_registry,
            tool_registry=tool_registry,
            tool_executor=ToolExecutor(registry=tool_registry),
        )
        result = await runtime.run(
            agent=AgentDefinition(
                agent_id="agent",
                name="Agente",
                instructions="Use a ferramenta.",
                tool_names=("remote__double",),
            ),
            input_data=AgentInput(message="Calcule."),
            context=AgentContext(execution_id="execution"),
        )
    assert isinstance(result, AgentResult)
    assert result.output == "Concluído."
    assert remote.calls == 1


@pytest.mark.asyncio
async def test_duplicate_tool_call_replay_does_not_repeat_remote_invocation() -> None:
    server, (remote,) = remote_server("double")
    tool_registry = ToolRegistry()
    model_registry = ModelProviderRegistry()
    model_registry.register(DuplicateProvider())
    async with MCPClient(InMemoryTransport(server)) as client:
        await MCPToolImporter(
            client=client, registry=tool_registry, server_alias="remote"
        ).import_tools(include_names=frozenset({"double"}))
        runtime = AgentRuntime(
            model_registry=model_registry,
            tool_registry=tool_registry,
            tool_executor=ToolExecutor(registry=tool_registry),
        )
        result = await runtime.run(
            agent=AgentDefinition(
                agent_id="agent",
                name="Agente",
                instructions="Use a ferramenta.",
                tool_names=("remote__double",),
            ),
            input_data=AgentInput(message="Calcule."),
            context=AgentContext(execution_id="duplicate"),
        )
    assert isinstance(result, AgentResult)
    assert result.status.value == "completed"
    assert remote.calls == 1


@pytest.mark.asyncio
async def test_tool_call_guardrail_rejects_before_remote_network_call() -> None:
    server, (remote,) = remote_server("double")
    tool_registry = ToolRegistry()
    model_registry = ModelProviderRegistry()
    model_registry.register(SequenceProvider())
    guardrail = RejectToolCallGuardrail()
    async with MCPClient(InMemoryTransport(server)) as client:
        await MCPToolImporter(
            client=client, registry=tool_registry, server_alias="remote"
        ).import_tools(include_names=frozenset({"double"}))
        runtime = AgentRuntime(
            model_registry=model_registry,
            tool_registry=tool_registry,
            tool_executor=ToolExecutor(registry=tool_registry),
            guardrail_manager=GuardrailManager(GuardrailRegistry((guardrail,))),
        )
        result = await runtime.run(
            agent=AgentDefinition(
                agent_id="agent",
                name="Agente",
                instructions="Use a ferramenta.",
                tool_names=("remote__double",),
                guardrails=AgentGuardrailConfig(
                    tool_call_guardrails=("reject-remote",)
                ),
            ),
            input_data=AgentInput(message="Calcule."),
            context=AgentContext(execution_id="guardrail"),
        )
    assert isinstance(result, AgentResult)
    assert result.status.value == "rejected"
    assert remote.calls == 0


@pytest.mark.asyncio
async def test_usage_limit_is_enforced_before_remote_call() -> None:
    server, (remote,) = remote_server("double")
    tool_registry = ToolRegistry()
    model_registry = ModelProviderRegistry()
    model_registry.register(SequenceProvider())
    async with MCPClient(InMemoryTransport(server)) as client:
        await MCPToolImporter(
            client=client, registry=tool_registry, server_alias="remote"
        ).import_tools(include_names=frozenset({"double"}))
        result = await AgentRuntime(
            model_registry=model_registry,
            tool_registry=tool_registry,
            tool_executor=ToolExecutor(registry=tool_registry),
        ).run(
            agent=AgentDefinition(
                agent_id="agent",
                name="Agente",
                instructions="Use a ferramenta.",
                tool_names=("remote__double",),
            ),
            input_data=AgentInput(message="Calcule."),
            context=AgentContext(execution_id="limit"),
            limits=ExecutionLimits(max_total_tokens=1),
        )
    assert isinstance(result, AgentResult)
    assert result.status.value == "limit_exceeded"
    assert remote.calls == 0


class SlowTool(FunctionTool):
    def __init__(self) -> None:
        super().__init__("slow", lambda arguments: arguments)
        self.started = asyncio.Event()
        self.cancelled = False

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        del arguments, context
        self.calls += 1
        self.started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return ToolOutput(content={})


@pytest.mark.asyncio
async def test_external_cancellation_reaches_remote_call_without_retry() -> None:
    registry = ToolRegistry()
    slow = SlowTool()
    registry.register(slow)
    server = AtlasMCPServer(
        config=MCPServerConfig(
            name="slow", version="1.0", exposed_tool_names=("slow",)
        ),
        tool_registry=registry,
        tool_executor=ToolExecutor(registry=registry),
    )
    async with MCPClient(InMemoryTransport(server)) as client:
        task = asyncio.create_task(client.call_tool("slow", {"value": 1}))
        await slow.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert slow.calls == 1
    assert slow.cancelled is True


@pytest.mark.asyncio
async def test_runtime_timeout_cancels_remote_call_without_retry() -> None:
    remote_registry = ToolRegistry()
    slow = SlowTool()
    remote_registry.register(slow)
    server = AtlasMCPServer(
        config=MCPServerConfig(
            name="slow", version="1.0", exposed_tool_names=("slow",)
        ),
        tool_registry=remote_registry,
        tool_executor=ToolExecutor(registry=remote_registry),
    )
    local_registry = ToolRegistry()
    models = ModelProviderRegistry()
    models.register(SlowProvider())
    async with MCPClient(InMemoryTransport(server)) as client:
        await MCPToolImporter(
            client=client, registry=local_registry, server_alias="remote"
        ).import_tools(include_names=frozenset({"slow"}))
        result = await AgentRuntime(
            model_registry=models,
            tool_registry=local_registry,
            tool_executor=ToolExecutor(registry=local_registry),
        ).run(
            agent=AgentDefinition(
                agent_id="agent",
                name="Agente",
                instructions="Use a ferramenta.",
                tool_names=("remote__slow",),
            ),
            input_data=AgentInput(message="Aguarde."),
            context=AgentContext(execution_id="timeout"),
            limits=ExecutionLimits(timeout_seconds=0.25),
        )
    assert isinstance(result, AgentResult)
    assert result.status.value == "timed_out"
    assert slow.calls == 1
    assert slow.cancelled is True


def test_naming_is_deterministic_and_separates_equal_remote_names() -> None:
    policy = MCPToolNamingPolicy()
    assert policy.name("github", "search") == "github__search"
    assert policy.name("filesystem", "search") == "filesystem__search"
    with pytest.raises(MCPConfigurationError):
        policy.name("...", "search")


class ControlledErrorClient:
    async def call_tool(self, name: str, arguments: dict[str, object]) -> MCPToolResult:
        del name, arguments
        return MCPToolResult(content=(MCPTextContent(text="falha"),), is_error=True)


class TransportErrorClient(ControlledErrorClient):
    async def call_tool(self, name: str, arguments: dict[str, object]) -> MCPToolResult:
        del name, arguments
        raise MCPConnectionError("indisponível")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client", "expected_code"),
    [
        (ControlledErrorClient(), "mcp_remote_tool_error"),
        (TransportErrorClient(), "mcp_transport_error"),
    ],
)
async def test_remote_tool_normalizes_controlled_and_transport_errors(
    client: ControlledErrorClient, expected_code: str
) -> None:
    tool = MCPRemoteTool(
        client=cast("MCPClient", client),
        server_id="remote",
        descriptor=MCPToolDescriptor(
            name="failure",
            input_schema={"type": "object"},
        ),
        local_tool_name="remote__failure",
    )
    with pytest.raises(ToolError) as caught:
        await tool.execute(
            {},
            ToolExecutionContext(
                execution_id="execution", agent_id="agent", tool_call_id="call"
            ),
        )
    assert caught.value.code == expected_code


@pytest.mark.asyncio
async def test_parallel_calls_do_not_share_names_or_arguments() -> None:
    server, tools = remote_server("one", "two")
    async with MCPClient(InMemoryTransport(server)) as client:
        one, two = await asyncio.gather(
            client.call_tool("one", {"value": 1}),
            client.call_tool("two", {"value": 2}),
        )
    assert one.structured_content == {"value": 1}
    assert two.structured_content == {"value": 2}
    assert [tool.calls for tool in tools] == [1, 1]


@pytest.mark.asyncio
async def test_collision_fails_before_registry_mutation() -> None:
    server, _ = remote_server("one", "two")
    registry = ToolRegistry()
    registry.register(FunctionTool("remote__two", lambda arguments: arguments))
    async with MCPClient(InMemoryTransport(server)) as client:
        importer = MCPToolImporter(
            client=client, registry=registry, server_alias="remote"
        )
        with pytest.raises(MCPConfigurationError, match="colisão"):
            await importer.import_tools(import_all=True)
    assert [item.definition.name for item in registry.tools()] == ["remote__two"]


@pytest.mark.asyncio
async def test_import_rejects_ambiguous_selection_options() -> None:
    server, _ = remote_server("one")
    async with MCPClient(InMemoryTransport(server)) as client:
        importer = MCPToolImporter(
            client=client, registry=ToolRegistry(), server_alias="remote"
        )
        with pytest.raises(MCPConfigurationError, match="nunca ambos"):
            await importer.import_tools(
                include_names=frozenset({"one"}), import_all=True
            )


class FailingRegistry(ToolRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    def register(self, tool: Tool) -> None:
        self.attempts += 1
        if self.attempts == 2:
            raise RuntimeError("falha injetada")
        super().register(tool)


@pytest.mark.asyncio
async def test_unexpected_partial_registration_is_rolled_back() -> None:
    server, _ = remote_server("one", "two")
    registry = FailingRegistry()
    async with MCPClient(InMemoryTransport(server)) as client:
        importer = MCPToolImporter(
            client=client, registry=registry, server_alias="remote"
        )
        with pytest.raises(MCPConfigurationError, match="revertida") as caught:
            await importer.import_tools(import_all=True)
    assert caught.value.__cause__ is None
    assert registry.tools() == ()
