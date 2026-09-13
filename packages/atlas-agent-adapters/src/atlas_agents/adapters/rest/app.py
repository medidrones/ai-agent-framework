"""FastAPI application factory for REST v1 execution APIs."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Protocol, cast

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
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
from atlas_agents.adapters.models import (
    ExecuteAgentRequest,
    ExecuteAgentResponse,
    ExecutionStreamItem,
    ExternalAgentInput,
    ExternalAttachment,
    ExternalExecutionContext,
    RequestedExecutionBudget,
    RequestedExecutionLimits,
    ResumeExecutionRequest,
    TransportPrincipal,
)
from atlas_agents.adapters.rest.v1.models import (
    ExecuteRequestV1,
    ExecuteResponseV1,
    HealthV1,
    ReadinessV1,
    ResumeRequestV1,
    StreamItemV1,
)
from atlas_agents.adapters.service import AgentExecutionService


class RESTAdapterConfig(BaseModel):
    """Configure REST limits without reading process environment."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    max_request_bytes: int = Field(default=1_048_576, gt=0)
    title: str = "Atlas Agent API"


class RESTPrincipalFactory(Protocol):
    """Resolve an already authenticated host request principal."""

    async def create(self, request: Request) -> TransportPrincipal:
        """Return trusted principal data supplied by host authentication."""
        ...


class AnonymousRESTPrincipalFactory:
    """Explicitly choose anonymous access for trusted internal deployments."""

    async def create(self, request: Request) -> TransportPrincipal:
        """Return a fixed least-privilege principal."""
        del request
        return TransportPrincipal(subject="anonymous", authentication_method="none")


def _execute_request(
    value: ExecuteRequestV1,
    principal: TransportPrincipal,
    idempotency_key: str | None,
) -> ExecuteAgentRequest:
    return ExecuteAgentRequest(
        request_id=value.request_id,
        agent_id=value.agent_id,
        input=ExternalAgentInput(
            message=value.input.message,
            attachments=tuple(
                ExternalAttachment(**item.model_dump())
                for item in value.input.attachments
            ),
            metadata=value.input.metadata,
        ),
        principal=principal,
        context=ExternalExecutionContext(**value.context.model_dump()),
        requested_limits=(
            None
            if value.requested_limits is None
            else RequestedExecutionLimits(**value.requested_limits.model_dump())
        ),
        requested_budget=(
            None
            if value.requested_budget is None
            else RequestedExecutionBudget(**value.requested_budget.model_dump())
        ),
        metadata=value.metadata,
        idempotency_key=idempotency_key,
    )


def _resume_request(
    value: ResumeRequestV1,
    principal: TransportPrincipal,
    idempotency_key: str | None,
) -> ResumeExecutionRequest:
    return ResumeExecutionRequest(
        **value.model_dump(), principal=principal, idempotency_key=idempotency_key
    )


def _response(value: ExecuteAgentResponse) -> ExecuteResponseV1:
    return ExecuteResponseV1.model_validate(value.model_dump(mode="json"))


def _status(error: AdapterError) -> int:
    if isinstance(error, IdentityMappingError):
        return 401
    if isinstance(error, AgentAccessDeniedError):
        return 403
    if isinstance(error, AgentNotRegisteredError):
        return 404
    if isinstance(error, IdempotencyConflictError):
        return 409
    if isinstance(error, InvalidExternalRequestError):
        return 400
    if isinstance(error, AdapterUnavailableError):
        return 503
    return 500


async def _sse_events(
    request: Request,
    iterator: AsyncIterator[ExecutionStreamItem],
    first: ExecutionStreamItem,
) -> AsyncIterator[str]:
    """Serialize incrementally and always close the upstream iterator."""
    try:
        payload = json.dumps(first.model_dump(mode="json"), ensure_ascii=False)
        yield f"data: {payload}\n\n"
        async for item in iterator:
            if await request.is_disconnected():
                break
            payload = json.dumps(item.model_dump(mode="json"), ensure_ascii=False)
            yield f"data: {payload}\n\n"
    finally:
        await cast("AsyncGenerator[ExecutionStreamItem, None]", iterator).aclose()


def _error_body(error: AdapterError) -> dict[str, object]:
    return {
        "code": error.code,
        "message": str(error),
        "retryable": error.retryable,
        "details": {},
    }


def create_app(
    *,
    service: AgentExecutionService,
    principal_factory: RESTPrincipalFactory,
    config: RESTAdapterConfig | None = None,
) -> FastAPI:
    """Create a caller-owned FastAPI app without starting a server."""
    settings = config or RESTAdapterConfig()
    app = FastAPI(title=settings.title, version="1.0.0")

    @app.exception_handler(AdapterError)
    async def adapter_error_handler(
        request: Request, error: AdapterError
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=_status(error), content=_error_body(error))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del request, error
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_external_request",
                "message": "A requisição externa é inválida.",
                "retryable": False,
                "details": {},
            },
        )

    async def checked_principal(request: Request) -> TransportPrincipal:
        length = request.headers.get("content-length")
        try:
            parsed_length = int(length) if length is not None else None
        except ValueError as error:
            raise InvalidExternalRequestError(
                "O cabeçalho Content-Length é inválido."
            ) from error
        if parsed_length is not None and parsed_length > settings.max_request_bytes:
            raise InvalidExternalRequestError(
                "A requisição excede o limite configurado."
            )
        return await principal_factory.create(request)

    @app.post("/v1/executions", response_model=ExecuteResponseV1)
    async def execute(
        body: ExecuteRequestV1,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> ExecuteResponseV1:
        principal = await checked_principal(request)
        return _response(
            await service.execute(_execute_request(body, principal, idempotency_key))
        )

    @app.post("/v1/executions/stream", response_model=StreamItemV1)
    async def stream(
        body: ExecuteRequestV1,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> StreamingResponse:
        principal = await checked_principal(request)
        iterator = service.stream(_execute_request(body, principal, idempotency_key))
        first = await anext(iterator)
        return StreamingResponse(
            _sse_events(request, iterator, first), media_type="text/event-stream"
        )

    @app.post("/v1/executions/resume", response_model=ExecuteResponseV1)
    async def resume(
        body: ResumeRequestV1,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> ExecuteResponseV1:
        principal = await checked_principal(request)
        return _response(
            await service.resume(_resume_request(body, principal, idempotency_key))
        )

    @app.post("/v1/executions/resume/stream", response_model=StreamItemV1)
    async def resume_stream(
        body: ResumeRequestV1,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> StreamingResponse:
        principal = await checked_principal(request)
        iterator = service.resume_stream(
            _resume_request(body, principal, idempotency_key)
        )
        first = await anext(iterator)
        return StreamingResponse(
            _sse_events(request, iterator, first), media_type="text/event-stream"
        )

    @app.get("/v1/health", response_model=HealthV1)
    async def health() -> HealthV1:
        return HealthV1(status="ok")

    @app.get("/v1/readiness", response_model=ReadinessV1)
    async def readiness() -> ReadinessV1:
        result = await service.readiness()
        return ReadinessV1(**result.model_dump())

    return app
