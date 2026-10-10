"""Deterministic Atlas dependencies used only by the certification host."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable
from typing import cast

from redis.asyncio import Redis

from atlas_agents import (
    AgentRuntime,
    CheckpointStore,
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
    TextContent,
    Tool,
    ToolApprovalMode,
    ToolCall,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutor,
    ToolOutput,
    ToolRegistry,
)


class CertificationModelProvider(ModelProvider):
    """Return a deterministic tool call or terminal answer without network I/O."""

    def __init__(self, *, request_tool: bool, delay_seconds: float = 0) -> None:
        """Select whether the next model call requests the fake tool."""
        self._request_tool = request_tool
        self._delay_seconds = delay_seconds

    @property
    def provider_name(self) -> str:
        """Return the stable provider identifier."""
        return "ds013-certification"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        """Expose the deterministic certification model."""
        return (
            ModelDescriptor(
                provider=self.provider_name,
                model="deterministic",
                capabilities=frozenset(
                    {ModelCapability.TEXT_GENERATION, ModelCapability.TOOL_CALLING}
                ),
            ),
        )

    async def generate(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> ModelResponse:
        """Produce the single scripted response for the current lifecycle phase."""
        del request, context
        if self._delay_seconds:
            await asyncio.sleep(self._delay_seconds)
        if self._request_tool:
            self._request_tool = False
            return ModelResponse(
                model="deterministic",
                tool_calls=(
                    ToolCall(
                        tool_call_id="call-certification-effect",
                        name="record_certification_effect",
                        arguments={"operation": "ds013"},
                    ),
                ),
                finish_reason=FinishReason.TOOL_CALL,
                usage=ModelUsage(input_tokens=2, output_tokens=1, total_tokens=3),
            )
        return ModelResponse(
            model="deterministic",
            content=(TextContent(text="Recuperação de certificação concluída."),),
            finish_reason=FinishReason.STOP,
            usage=ModelUsage(input_tokens=2, output_tokens=2, total_tokens=4),
        )

    def stream(
        self, request: ModelRequest, context: ModelExecutionContext
    ) -> AsyncIterator[ModelStreamEvent]:
        """Reject streaming because DS-013 exercises the run-mode recovery path."""
        del request, context
        raise NotImplementedError("O host DS-013 não utiliza streaming.")


class IdempotentCertificationTool(Tool):
    """Persist one fake external effect with an idempotency marker in Redis."""

    def __init__(self, client: Redis) -> None:
        """Use the injected Redis client as the fake external system."""
        self._client = client

    @property
    def definition(self) -> ToolDefinition:
        """Require explicit HITL approval before the fake effect."""
        return ToolDefinition(
            name="record_certification_effect",
            description="Registra um efeito externo falso e idempotente.",
            parameters={
                "type": "object",
                "properties": {"operation": {"type": "string"}},
                "required": ["operation"],
                "additionalProperties": False,
            },
            approval_mode=ToolApprovalMode.REQUIRED,
        )

    async def execute(
        self, arguments: dict[str, object], context: ToolExecutionContext
    ) -> ToolOutput:
        """Record the effect once even if an unknown result is reconciled."""
        del arguments
        marker = f"atlas:ds013:effect:{context.execution_id}"
        counter = f"atlas:ds013:effect-count:{context.execution_id}"
        applied = await cast(
            Awaitable[object],
            self._client.eval(
                """
                if redis.call('SETNX', KEYS[1], ARGV[1]) == 1 then
                  redis.call('INCR', KEYS[2])
                  return 1
                end
                return 0
                """,
                2,
                marker,
                counter,
                "applied",
            ),
        )
        crash_marker = f"atlas:ds013:crash-after-effect:{context.execution_id}"
        crash_requested = await self._client.delete(crash_marker)
        if crash_requested:
            os.kill(os.getpid(), 9)  # SIGKILL in the Linux certification image.
        delay_marker = f"atlas:ds013:delay-after-effect:{context.execution_id}"
        delay_value = await self._client.getdel(delay_marker)
        if delay_value is not None:
            await asyncio.sleep(float(delay_value.decode("ascii")))
        return ToolOutput(content={"applied": bool(applied)})


def build_runtime(
    *,
    checkpoint_store: CheckpointStore,
    redis_client: Redis,
    request_tool: bool,
    model_delay_seconds: float = 0,
) -> AgentRuntime:
    """Build the public Atlas runtime with explicit deterministic dependencies."""
    models = ModelProviderRegistry()
    models.register(
        CertificationModelProvider(
            request_tool=request_tool,
            delay_seconds=model_delay_seconds,
        )
    )
    tools = ToolRegistry()
    tools.register(IdempotentCertificationTool(redis_client))
    return AgentRuntime(
        model_registry=models,
        tool_registry=tools,
        tool_executor=ToolExecutor(registry=tools),
        checkpoint_store=checkpoint_store,
    )
