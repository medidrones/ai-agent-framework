"""Execute a deterministic local tool through the Atlas runtime."""

import asyncio
import sys
from pathlib import Path

from atlas_agents import ToolDefinition

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import (
    LocalTool,
    ScriptedModelProvider,
    agent,
    build_runtime,
    input_and_context,
    text_response,
    tool_response,
)


async def _run() -> None:
    shipping = LocalTool(
        ToolDefinition(
            name="calculate_shipping",
            description="Calcula um frete local determinístico.",
            parameters={
                "type": "object",
                "properties": {"postal_code": {"type": "string"}},
                "required": ["postal_code"],
                "additionalProperties": False,
            },
        ),
        lambda arguments: {"postal_code": arguments["postal_code"], "price": 18.5},
    )
    provider = ScriptedModelProvider(
        (
            tool_response("calculate_shipping", {"postal_code": "01001-000"}),
            text_response("O frete custa R$ 18,50."),
        )
    )
    runtime = build_runtime(provider, tools=(shipping,))
    input_data, context = input_and_context("Calcule o frete para 01001-000.")
    result = await runtime.run(
        agent=agent(tools=("calculate_shipping",)),
        input_data=input_data,
        context=context,
    )
    print(f"Chamadas da ferramenta: {shipping.calls}")  # noqa: T201
    print(result.output)  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
