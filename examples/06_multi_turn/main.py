"""Show that AgentRuntime owns the model/tool/model loop."""

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
    status = LocalTool(
        ToolDefinition(
            name="get_order_status",
            description="Consulta um pedido na fixture local.",
            parameters={
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
        ),
        lambda arguments: {"order_id": arguments["order_id"], "status": "shipped"},
    )
    provider = ScriptedModelProvider(
        (
            tool_response("get_order_status", {"order_id": "1234"}),
            text_response("O pedido 1234 foi enviado."),
        )
    )
    runtime = build_runtime(provider, tools=(status,))
    input_data, context = input_and_context("Qual é o status do pedido 1234?")
    result = await runtime.run(
        agent=agent(tools=("get_order_status",)),
        input_data=input_data,
        context=context,
    )
    print(f"Turnos do modelo: {len(provider.requests)}")  # noqa: T201
    print(f"Execuções da ferramenta: {status.calls}")  # noqa: T201
    print(result.output)  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
