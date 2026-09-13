"""Explicit gRPC servicer registration without listener ownership."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Protocol, cast

import grpc
from pydantic import BaseModel, ConfigDict, Field

from atlas_agents.adapters.errors import (
    AdapterError,
    AdapterUnavailableError,
    AgentAccessDeniedError,
    AgentNotRegisteredError,
    IdempotencyConflictError,
    IdentityMappingError,
    InvalidExternalRequestError,
)
from atlas_agents.adapters.grpc.mapping import (
    execute_from_proto,
    response_to_proto,
    resume_from_proto,
    stream_to_proto,
)
from atlas_agents.adapters.grpc.v1 import agent_execution_pb2 as pb
from atlas_agents.adapters.grpc.v1 import agent_execution_pb2_grpc as pb_grpc
from atlas_agents.adapters.models import TransportPrincipal
from atlas_agents.adapters.service import AgentExecutionService


class GrpcAdapterConfig(BaseModel):
    """Configure explicit accepted metadata without environment parsing."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    idempotency_metadata_key: str = Field(default="idempotency-key", min_length=1)


class GrpcPrincipalFactory(Protocol):
    """Resolve principal data authenticated by the gRPC host or interceptor."""

    async def create(
        self, context: grpc.aio.ServicerContext[object, object]
    ) -> TransportPrincipal:
        """Return trusted identity input without reading request messages."""
        ...


class AnonymousGrpcPrincipalFactory:
    """Explicitly choose anonymous access for a trusted internal server."""

    async def create(
        self, context: grpc.aio.ServicerContext[object, object]
    ) -> TransportPrincipal:
        """Return a fixed least-privilege principal."""
        del context
        return TransportPrincipal(subject="anonymous", authentication_method="none")


def _grpc_code(error: AdapterError) -> grpc.StatusCode:
    if isinstance(error, IdentityMappingError):
        return grpc.StatusCode.UNAUTHENTICATED
    if isinstance(error, AgentAccessDeniedError):
        return grpc.StatusCode.PERMISSION_DENIED
    if isinstance(error, AgentNotRegisteredError):
        return grpc.StatusCode.NOT_FOUND
    if isinstance(error, IdempotencyConflictError):
        return grpc.StatusCode.ALREADY_EXISTS
    if isinstance(error, InvalidExternalRequestError):
        return grpc.StatusCode.INVALID_ARGUMENT
    if isinstance(error, AdapterUnavailableError):
        return grpc.StatusCode.UNAVAILABLE
    return grpc.StatusCode.INTERNAL


class AgentExecutionServicer(pb_grpc.AgentExecutionServiceServicer):
    """Translate gRPC v1 messages to one shared execution service."""

    def __init__(
        self,
        *,
        service: AgentExecutionService,
        principal_factory: GrpcPrincipalFactory,
        config: GrpcAdapterConfig,
    ) -> None:
        """Store caller-owned dependencies without binding a port."""
        self._service = service
        self._principal_factory = principal_factory
        self._config = config

    def _idempotency_key(
        self, context: grpc.aio.ServicerContext[object, object]
    ) -> str | None:
        allowed = self._config.idempotency_metadata_key.lower()
        for key, value in context.invocation_metadata() or ():
            if key.lower() == allowed and isinstance(value, str):
                return value
        return None

    async def Execute(
        self,
        request: pb.ExecuteRequest,
        context: grpc.aio.ServicerContext[object, object],
    ) -> pb.ExecuteResponse:
        """Execute one unary request while preserving runtime outcomes."""
        try:
            principal = await self._principal_factory.create(context)
            mapped = execute_from_proto(
                request,
                principal=principal,
                idempotency_key=self._idempotency_key(context),
                transport_timeout=context.time_remaining(),
            )
            return response_to_proto(await self._service.execute(mapped))
        except AdapterError as error:
            await context.abort(_grpc_code(error), str(error))
            raise AssertionError("context.abort deveria encerrar a chamada") from None

    async def Stream(
        self,
        request: pb.ExecuteRequest,
        context: grpc.aio.ServicerContext[object, object],
    ) -> AsyncGenerator[pb.StreamItem, None]:
        """Yield runtime items with native gRPC backpressure."""
        iterator = None
        try:
            principal = await self._principal_factory.create(context)
            mapped = execute_from_proto(
                request,
                principal=principal,
                idempotency_key=self._idempotency_key(context),
                transport_timeout=context.time_remaining(),
            )
            iterator = self._service.stream(mapped)
            async for item in iterator:
                yield stream_to_proto(item)
        except AdapterError as error:
            await context.abort(_grpc_code(error), str(error))
        finally:
            if iterator is not None:
                await cast("AsyncGenerator[object, None]", iterator).aclose()

    async def Resume(
        self,
        request: pb.ResumeRequest,
        context: grpc.aio.ServicerContext[object, object],
    ) -> pb.ExecuteResponse:
        """Resume one checkpoint with a body-carried token."""
        try:
            principal = await self._principal_factory.create(context)
            mapped = resume_from_proto(
                request,
                principal=principal,
                idempotency_key=self._idempotency_key(context),
            )
            return response_to_proto(await self._service.resume(mapped))
        except AdapterError as error:
            await context.abort(_grpc_code(error), str(error))
            raise AssertionError("context.abort deveria encerrar a chamada") from None

    async def ResumeStream(
        self,
        request: pb.ResumeRequest,
        context: grpc.aio.ServicerContext[object, object],
    ) -> AsyncGenerator[pb.StreamItem, None]:
        """Stream a resumed checkpoint without buffering."""
        iterator = None
        try:
            principal = await self._principal_factory.create(context)
            mapped = resume_from_proto(
                request,
                principal=principal,
                idempotency_key=self._idempotency_key(context),
            )
            iterator = self._service.resume_stream(mapped)
            async for item in iterator:
                yield stream_to_proto(item)
        except AdapterError as error:
            await context.abort(_grpc_code(error), str(error))
        finally:
            if iterator is not None:
                await cast("AsyncGenerator[object, None]", iterator).aclose()


def add_agent_execution_servicer(
    *,
    server: grpc.aio.Server,
    service: AgentExecutionService,
    principal_factory: GrpcPrincipalFactory,
    config: GrpcAdapterConfig | None = None,
) -> None:
    """Register the servicer without binding or starting the caller's server."""
    pb_grpc.add_AgentExecutionServiceServicer_to_server(  # type: ignore[no-untyped-call]
        AgentExecutionServicer(
            service=service,
            principal_factory=principal_factory,
            config=config or GrpcAdapterConfig(),
        ),
        server,
    )
