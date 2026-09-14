"""Collect safe local spans and metrics without OpenTelemetry."""

import asyncio
import sys
from pathlib import Path

from atlas_agents import ObservabilityManager, ToolDefinition

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import (
    LocalTool,
    RecordingMetrics,
    RecordingTracer,
    ScriptedModelProvider,
    agent,
    build_runtime,
    input_and_context,
    text_response,
    tool_response,
)


async def _run() -> None:
    tracer = RecordingTracer()
    metrics = RecordingMetrics()
    observability = ObservabilityManager(tracer=tracer, metrics=metrics)
    tool = LocalTool(
        ToolDefinition(
            name="health_check",
            description="Retorna o estado local.",
            parameters={"type": "object", "properties": {}},
        ),
        lambda arguments: {"healthy": not arguments},
    )
    provider = ScriptedModelProvider(
        (tool_response("health_check", {}), text_response("Serviço saudável."))
    )
    runtime = build_runtime(
        provider,
        tools=(tool,),
        observability_manager=observability,
    )
    input_data, context = input_and_context("Verifique o serviço.")
    await runtime.run(
        agent=agent(tools=("health_check",)),
        input_data=input_data,
        context=context,
    )
    for span in tracer.spans:
        print(f"span: {span.name}")  # noqa: T201
    for name in dict.fromkeys(metrics.names):
        print(f"metric: {name}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
