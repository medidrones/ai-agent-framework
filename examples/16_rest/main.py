"""Exercise the official REST adapter through an in-process ASGI client."""

import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from atlas_agents.adapters.rest import AnonymousRESTPrincipalFactory, create_app

sys.path.insert(0, str(Path(__file__).parents[1]))

from _adapter_support import build_execution_service
from _support import (
    ScriptedModelProvider,
    agent,
    build_runtime,
    text_response,
    text_stream,
)


def create_example_app() -> FastAPI:
    """Compose the caller-owned example application."""
    provider = ScriptedModelProvider(
        (text_response("Resposta via REST."),),
        stream_events=text_stream("Resposta ", "em streaming."),
    )
    definition = agent()
    service = build_execution_service(build_runtime(provider), definition)
    return create_app(
        service=service,
        principal_factory=AnonymousRESTPrincipalFactory(),
    )


async def _run() -> None:
    app = create_example_app()
    definition = agent()
    body = {
        "request_id": "rest-request-1",
        "agent_id": definition.agent_id,
        "input": {"message": "Responda pelo adapter REST."},
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://atlas.local",
    ) as client:
        response = await client.post("/v1/executions", json=body)
        response.raise_for_status()
        streamed = await client.post("/v1/executions/stream", json=body)
        streamed.raise_for_status()
    print(f"Execução: {response.json()['status']}")  # noqa: T201
    print(f"Streaming SSE recebido: {'data:' in streamed.text}")  # noqa: T201


if __name__ == "__main__":
    if "--serve" in sys.argv:
        import uvicorn

        uvicorn.run(create_example_app(), host="127.0.0.1", port=8000)
    else:
        asyncio.run(_run())
