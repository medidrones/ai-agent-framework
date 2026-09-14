"""Inject an explicitly configured official OpenAI provider."""

import asyncio
import os

from openai import AsyncOpenAI

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentRuntime,
    ExecutionSuspension,
    ModelProviderRegistry,
    ModelSelectionRequest,
)
from atlas_agents.providers.openai import OpenAIModelProvider, OpenAIProviderConfig


async def _run() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Defina OPENAI_API_KEY para executar este exemplo online.")  # noqa: T201
        return
    client = AsyncOpenAI(api_key=api_key)
    provider = OpenAIModelProvider(
        client=client,
        config=OpenAIProviderConfig(),
    )
    registry = ModelProviderRegistry()
    registry.register(provider)
    runtime = AgentRuntime(model_registry=registry)
    result = await runtime.run(
        agent=AgentDefinition(
            agent_id="openai-example",
            name="Exemplo OpenAI",
            instructions="Responda em uma frase curta.",
        ),
        input_data=AgentInput(message="O que é inversão de dependência?"),
        context=AgentContext(execution_id="openai-example-1"),
        model_selection=ModelSelectionRequest(model="gpt-5.6-luna"),
    )
    if isinstance(result, ExecutionSuspension):
        raise RuntimeError("Este agente não deveria exigir aprovação humana.")
    print(result.output)  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
