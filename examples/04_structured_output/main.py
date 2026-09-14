"""Describe and consume provider-neutral structured output."""

import asyncio
import json
import sys
from pathlib import Path

from atlas_agents import StructuredOutputDefinition

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import (
    ScriptedModelProvider,
    agent,
    build_runtime,
    input_and_context,
    text_response,
)


async def _run() -> None:
    output_contract = StructuredOutputDefinition(
        name="ticket_classification",
        json_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "priority": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["category", "priority", "summary"],
            "additionalProperties": False,
        },
    )
    payload = {
        "category": "technical",
        "priority": "high",
        "summary": "Serviço indisponível.",
    }
    provider = ScriptedModelProvider((text_response(json.dumps(payload)),))
    runtime = build_runtime(provider)
    input_data, context = input_and_context("Classifique o chamado.")
    definition = agent().model_copy(update={"structured_output": output_contract})
    result = await runtime.run(
        agent=definition,
        input_data=input_data,
        context=context,
    )
    if provider.requests[0].structured_output != output_contract:
        raise RuntimeError("O contrato estruturado não chegou ao provider.")
    print(f"Contrato: {output_contract.name}")  # noqa: T201
    print(json.dumps(json.loads(str(result.output)), ensure_ascii=False))  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
