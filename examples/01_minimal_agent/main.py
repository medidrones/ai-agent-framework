"""Run the smallest fully offline Atlas agent."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import (
    ScriptedModelProvider,
    agent,
    build_runtime,
    input_and_context,
    text_response,
)


async def _run() -> None:
    provider = ScriptedModelProvider((text_response("Atlas agent is running."),))
    runtime = build_runtime(provider)
    input_data, context = input_and_context("Inicie o agente.")
    result = await runtime.run(agent=agent(), input_data=input_data, context=context)
    print(result.output)  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
