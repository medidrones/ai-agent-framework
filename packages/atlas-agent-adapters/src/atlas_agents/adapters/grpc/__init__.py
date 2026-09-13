"""gRPC adapter registration API."""

from atlas_agents.adapters.grpc.server import (
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
