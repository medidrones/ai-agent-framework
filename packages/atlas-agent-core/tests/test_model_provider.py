"""Substitutability tests for the abstract model provider contract."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from atlas_agents import (
    FinishReason,
    MessageRole,
    ModelCapability,
    ModelDescriptor,
    ModelExecutionContext,
    ModelMessage,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelUsage,
    TextContent,
)


class FakeModelProvider(ModelProvider):
    @property
    def provider_name(self) -> str:
        return "fake"

    async def list_models(self) -> tuple[ModelDescriptor, ...]:
        return (
            ModelDescriptor(
                provider=self.provider_name,
                model="fake-model",
                capabilities=frozenset(
                    {
                        ModelCapability.TEXT_GENERATION,
                        ModelCapability.STREAMING,
                    }
                ),
            ),
        )

    async def generate(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> ModelResponse:
        return ModelResponse(
            response_id=context.request_id,
            model=request.model,
            content=(TextContent(text="Resposta fake"),),
            finish_reason=FinishReason.STOP,
            usage=ModelUsage(input_tokens=1, output_tokens=2, total_tokens=3),
        )

    async def stream(
        self,
        request: ModelRequest,
        context: ModelExecutionContext,
    ) -> AsyncIterator[ModelStreamEvent]:
        yield ModelStreamEvent(
            type=ModelStreamEventType.TEXT_DELTA,
            sequence=1,
            response_id=context.request_id,
            data={"text": request.model},
            timestamp=datetime.now(UTC),
        )
        yield ModelStreamEvent(
            type=ModelStreamEventType.RESPONSE_COMPLETED,
            sequence=2,
            response_id=context.request_id,
            data={"finish_reason": FinishReason.STOP.value},
            timestamp=datetime.now(UTC),
        )


def _request() -> ModelRequest:
    return ModelRequest(
        model="fake-model",
        messages=(
            ModelMessage(
                role=MessageRole.USER,
                content=(TextContent(text="Olá"),),
            ),
        ),
    )


def _context() -> ModelExecutionContext:
    return ModelExecutionContext(
        execution_id="execution-1",
        agent_id="agent-1",
        request_id="request-1",
    )


async def execute_provider(provider: ModelProvider) -> ModelResponse:
    return await provider.generate(_request(), _context())


async def test_fake_provider_is_substitutable_through_abstract_contract() -> None:
    provider: ModelProvider = FakeModelProvider()

    response = await execute_provider(provider)

    assert provider.provider_name == "fake"
    assert response.content == (TextContent(text="Resposta fake"),)


async def test_provider_lists_models_and_streams_structured_events() -> None:
    provider: ModelProvider = FakeModelProvider()

    models = await provider.list_models()
    events = [event async for event in provider.stream(_request(), _context())]

    assert models[0].provider == provider.provider_name
    assert [event.sequence for event in events] == [1, 2]
    assert events[-1].type is ModelStreamEventType.RESPONSE_COMPLETED


def test_model_execution_context_is_immutable_and_isolates_metadata() -> None:
    metadata: dict[str, object] = {"trace": "value"}
    context = ModelExecutionContext(
        execution_id="execution-1",
        agent_id="agent-1",
        request_id="request-1",
        metadata=metadata,
    )
    metadata["trace"] = "changed"

    assert context.metadata == {"trace": "value"}
