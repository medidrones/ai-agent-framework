"""gRPC adapter registration API."""

try:
    import google.protobuf as _protobuf
    import grpc as _grpc
except ModuleNotFoundError as error:
    if error.name not in {"grpc", "google", "google.protobuf"}:
        raise
    from atlas_agents.adapters.optional import MissingAdapterDependencyError

    raise MissingAdapterDependencyError(
        "O adapter gRPC exige o extra 'grpc'. Instale com: "
        "pip install atlas-agent-adapters[grpc]"
    ) from None

del _grpc, _protobuf

from atlas_agents.adapters.grpc.server import (  # noqa: E402
    AnonymousGrpcPrincipalFactory,
    GrpcAdapterConfig,
    GrpcPrincipalFactory,
    add_agent_execution_servicer,
)

__all__ = [
    "AnonymousGrpcPrincipalFactory",
    "GrpcAdapterConfig",
    "GrpcPrincipalFactory",
    "add_agent_execution_servicer",
]
