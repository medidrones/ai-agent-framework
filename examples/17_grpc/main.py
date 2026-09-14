"""Exercise unary and streaming calls against the official gRPC adapter."""

import asyncio
import sys
from pathlib import Path

import grpc

from atlas_agents.adapters.grpc import (
    AnonymousGrpcPrincipalFactory,
    add_agent_execution_servicer,
)
from atlas_agents.adapters.grpc.v1 import agent_execution_pb2 as pb
from atlas_agents.adapters.grpc.v1 import agent_execution_pb2_grpc as pb_grpc

sys.path.insert(0, str(Path(__file__).parents[1]))

from _adapter_support import build_execution_service
from _support import (
    ScriptedModelProvider,
    agent,
    build_runtime,
    text_response,
    text_stream,
)


def _server() -> grpc.aio.Server:
    """Compose one caller-owned gRPC server without starting it."""
    provider = ScriptedModelProvider(
        (text_response("Resposta via gRPC."),),
        stream_events=text_stream("Resposta ", "gRPC em streaming."),
    )
    definition = agent()
    service = build_execution_service(build_runtime(provider), definition)
    server = grpc.aio.server()
    add_agent_execution_servicer(
        server=server,
        service=service,
        principal_factory=AnonymousGrpcPrincipalFactory(),
    )
    return server


async def _run() -> None:
    server = _server()
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    try:
        stub = pb_grpc.AgentExecutionServiceStub(channel)  # type: ignore[no-untyped-call]
        request = pb.ExecuteRequest(
            request_id="grpc-request-1",
            agent_id=agent().agent_id,
            input=pb.AgentInput(message="Responda pelo adapter gRPC."),
        )
        response = await stub.Execute(request)
        items = [item async for item in stub.Stream(request)]
    finally:
        await channel.close()
        await server.stop(None)
    print(f"Execução: {response.status}")  # noqa: T201
    print(f"Itens do streaming: {len(items)}")  # noqa: T201


async def _serve() -> None:
    """Run the development server used by the .NET interoperability example."""
    server = _server()
    server.add_insecure_port("127.0.0.1:50051")
    await server.start()
    print("Servidor gRPC disponível em 127.0.0.1:50051")  # noqa: T201
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(_serve() if "--serve" in sys.argv else _run())
