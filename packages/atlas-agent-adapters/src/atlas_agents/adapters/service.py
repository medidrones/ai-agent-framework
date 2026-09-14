"""Transport-neutral application facade over the Atlas runtime."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from typing import Protocol, cast
from uuid import uuid4

from pydantic import JsonValue, TypeAdapter, ValidationError

from atlas_agents.adapters.errors import (
    AdapterSerializationError,
    AdapterUnavailableError,
    AgentAccessDeniedError,
    IdempotencyConflictError,
    IdentityMappingError,
)
from atlas_agents.adapters.idempotency import (
    IdempotencyState,
    IdempotencyStore,
)
from atlas_agents.adapters.models import (
    AdapterErrorResponse,
    AdapterExecutionStatus,
    ApprovalRequestDTO,
    ApprovalSubjectDTO,
    CitationDTO,
    ExecuteAgentRequest,
    ExecuteAgentResponse,
    ExecutionStreamItem,
    ExecutionSuspensionDTO,
    ReadinessResponse,
    ResumeExecutionRequest,
    TransportPrincipal,
    UsageDTO,
)
from atlas_agents.adapters.policies import (
    AgentAccessPolicy,
    AgentOperation,
    EffectiveExecutionPolicy,
    ExecutionIdentityMapper,
    ExecutionPolicyResolver,
)
from atlas_agents.agents import (
    AgentAttachment,
    AgentContext,
    AgentDefinition,
    AgentInput,
    ExecutionIdentity,
)
from atlas_agents.approvals import (
    ApprovalDecision,
    ApprovalDecisionType,
    ExecutionSuspension,
    ResumeToken,
)
from atlas_agents.events import AgentEventType
from atlas_agents.models import ModelSelectionRequest
from atlas_agents.runtime import (
    ExecutionBudget,
    ExecutionLimits,
    RuntimeEventItem,
    RuntimeOutcome,
    RuntimeResultItem,
    RuntimeStreamItem,
    RuntimeSuspensionItem,
)

_JSON: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


class AgentRuntimePort(Protocol):
    """Describe only runtime operations required by the application facade."""

    async def run(
        self,
        *,
        agent: AgentDefinition,
        input_data: AgentInput,
        context: AgentContext,
        model_selection: ModelSelectionRequest | None = None,
        limits: ExecutionLimits | None = None,
        budget: ExecutionBudget | None = None,
    ) -> RuntimeOutcome:
        """Execute a non-streaming agent invocation."""
        ...

    def stream(
        self,
        *,
        agent: AgentDefinition,
        input_data: AgentInput,
        context: AgentContext,
        model_selection: ModelSelectionRequest | None = None,
        limits: ExecutionLimits | None = None,
        budget: ExecutionBudget | None = None,
    ) -> AsyncIterator[RuntimeStreamItem]:
        """Stream an agent invocation."""
        ...

    async def resume(
        self, *, resume_token: ResumeToken, decision: ApprovalDecision
    ) -> RuntimeOutcome:
        """Resume a non-streaming checkpoint."""
        ...

    def resume_stream(
        self, *, resume_token: ResumeToken, decision: ApprovalDecision
    ) -> AsyncIterator[RuntimeStreamItem]:
        """Resume a streaming checkpoint."""
        ...


class AgentRegistryPort(Protocol):
    """Resolve configured agents without requiring a concrete registry class."""

    def get(self, agent_id: str) -> AgentDefinition:
        """Return the exact agent registered for an external identifier."""
        ...

    def agents(self) -> tuple[AgentDefinition, ...]:
        """Return registered agents in deterministic order."""
        ...


class AgentExecutionService:
    """Centralize external execution, authorization, policy, and DTO mapping."""

    def __init__(
        self,
        *,
        runtime: AgentRuntimePort,
        agent_registry: AgentRegistryPort,
        identity_mapper: ExecutionIdentityMapper,
        access_policy: AgentAccessPolicy,
        policy_resolver: ExecutionPolicyResolver,
        idempotency_store: IdempotencyStore | None = None,
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Store explicit dependencies without a service locator."""
        self._runtime = runtime
        self._agents = agent_registry
        self._identity_mapper = identity_mapper
        self._access_policy = access_policy
        self._policy_resolver = policy_resolver
        self._idempotency = idempotency_store
        self._execution_id_factory = execution_id_factory or (lambda: str(uuid4()))

    async def execute(self, request: ExecuteAgentRequest) -> ExecuteAgentResponse:
        """Authorize, constrain, execute, and map one external request."""

        async def invoke() -> ExecuteAgentResponse:
            agent, identity, policy = await self._prepare_execute(request)
            context = AgentContext(
                execution_id=self._execution_id_factory(),
                session_id=request.context.session_id,
                user_id=identity.subject,
                tenant_id=request.principal.tenant,
                identity=identity,
                metadata=dict(request.context.metadata),
            )
            outcome = await self._runtime.run(
                agent=agent,
                input_data=self._input(request),
                context=context,
                limits=policy.limits,
                budget=policy.budget,
            )
            return self._map_outcome(request.request_id, outcome)

        return await self._idempotent(request, invoke)

    async def stream(
        self, request: ExecuteAgentRequest
    ) -> AsyncIterator[ExecutionStreamItem]:
        """Stream selected runtime events and one final result or suspension."""
        agent, identity, policy = await self._prepare_execute(request)
        execution_id = self._execution_id_factory()
        context = AgentContext(
            execution_id=execution_id,
            session_id=request.context.session_id,
            user_id=identity.subject,
            tenant_id=request.principal.tenant,
            identity=identity,
            metadata=dict(request.context.metadata),
        )
        iterator = self._runtime.stream(
            agent=agent,
            input_data=self._input(request),
            context=context,
            limits=policy.limits,
            budget=policy.budget,
        )
        mapped = self._map_stream(request.request_id, iterator)
        try:
            async for item in mapped:
                yield item
        finally:
            await cast("AsyncGenerator[ExecutionStreamItem, None]", mapped).aclose()

    async def resume(self, request: ResumeExecutionRequest) -> ExecuteAgentResponse:
        """Authorize and resume one checkpoint using a body-carried token."""

        async def invoke() -> ExecuteAgentResponse:
            identity = await self._authorize_resume(request)
            outcome = await self._runtime.resume(
                resume_token=ResumeToken(value=request.resume_token),
                decision=self._decision(request, identity),
            )
            return self._map_outcome(request.request_id, outcome)

        return await self._idempotent(request, invoke)

    async def resume_stream(
        self, request: ResumeExecutionRequest
    ) -> AsyncIterator[ExecutionStreamItem]:
        """Authorize and stream one resumed checkpoint."""
        identity = await self._authorize_resume(request)
        iterator = self._runtime.resume_stream(
            resume_token=ResumeToken(value=request.resume_token),
            decision=self._decision(request, identity),
        )
        mapped = self._map_stream(request.request_id, iterator)
        try:
            async for item in mapped:
                yield item
        finally:
            await cast("AsyncGenerator[ExecutionStreamItem, None]", mapped).aclose()

    async def readiness(self) -> ReadinessResponse:
        """Check local composition without contacting any model provider."""
        agents_ready = bool(self._agents.agents())
        return ReadinessResponse(
            ready=agents_ready,
            checks={"agent_registry": agents_ready, "runtime": True},
        )

    async def _prepare_execute(
        self, request: ExecuteAgentRequest
    ) -> tuple[AgentDefinition, ExecutionIdentity, EffectiveExecutionPolicy]:
        agent = self._agents.get(request.agent_id)
        identity = self._map_identity(request.principal)
        if not await self._access_policy.authorize(
            agent_id=agent.agent_id,
            identity=identity,
            operation=AgentOperation.EXECUTE,
        ):
            raise AgentAccessDeniedError("A execução do agente não foi autorizada.")
        policy = self._policy_resolver.resolve(
            agent=agent,
            identity=identity,
            requested_limits=request.requested_limits,
            requested_budget=request.requested_budget,
        )
        return agent, identity, policy

    async def _authorize_resume(
        self, request: ResumeExecutionRequest
    ) -> ExecutionIdentity:
        agent = self._agents.get(request.agent_id)
        identity = self._map_identity(request.principal)
        if not await self._access_policy.authorize(
            agent_id=agent.agent_id,
            identity=identity,
            operation=AgentOperation.RESUME,
        ):
            raise AgentAccessDeniedError("A retomada do agente não foi autorizada.")
        return identity

    def _map_identity(self, principal: TransportPrincipal) -> ExecutionIdentity:
        try:
            return self._identity_mapper.map(principal)
        except IdentityMappingError:
            raise
        except Exception:
            raise IdentityMappingError(
                "Não foi possível mapear a identidade autenticada."
            ) from None

    @staticmethod
    def _input(request: ExecuteAgentRequest) -> AgentInput:
        return AgentInput(
            message=request.input.message,
            attachments=tuple(
                AgentAttachment(
                    attachment_id=item.attachment_id,
                    name=item.name,
                    media_type=item.media_type,
                    uri=item.uri,
                    metadata=dict(item.metadata),
                )
                for item in request.input.attachments
            ),
            metadata=dict(request.input.metadata),
        )

    @staticmethod
    def _decision(
        request: ResumeExecutionRequest, identity: ExecutionIdentity
    ) -> ApprovalDecision:
        return ApprovalDecision(
            approval_request_id=request.approval_request_id,
            decision=ApprovalDecisionType(request.decision),
            decided_at=request.decided_at,
            decided_by=identity,
            reason=request.reason,
            metadata=dict(request.metadata),
        )

    async def _idempotent(
        self,
        request: ExecuteAgentRequest | ResumeExecutionRequest,
        invoke: Callable[[], Awaitable[ExecuteAgentResponse]],
    ) -> ExecuteAgentResponse:
        key = request.idempotency_key
        store = self._idempotency
        if key is None or store is None:
            return await invoke()
        fingerprint = self._fingerprint(request)
        record, created = await store.reserve(key, fingerprint)
        if record.fingerprint != fingerprint:
            raise IdempotencyConflictError(
                "A chave de idempotência já foi usada com outra requisição."
            )
        if record.state is IdempotencyState.COMPLETED and record.response is not None:
            return record.response
        if not created:
            raise AdapterUnavailableError("A requisição idempotente está em andamento.")
        try:
            response = await invoke()
        except BaseException:
            await store.fail(key, fingerprint)
            raise
        await store.complete(key, fingerprint, response)
        return response

    @staticmethod
    def _fingerprint(
        request: ExecuteAgentRequest | ResumeExecutionRequest,
    ) -> str:
        payload = request.model_dump(
            mode="json", exclude={"principal", "idempotency_key"}
        )
        payload["_principal_scope"] = {
            "subject": request.principal.subject,
            "tenant": request.principal.tenant,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def _map_stream(
        self,
        request_id: str,
        iterator: AsyncIterator[RuntimeStreamItem],
    ) -> AsyncIterator[ExecutionStreamItem]:
        last_sequence = -1
        try:
            async for item in iterator:
                if isinstance(item, RuntimeEventItem):
                    event = item.event
                    last_sequence = event.sequence
                    yield ExecutionStreamItem(
                        type=event.event_type.value,
                        sequence=event.sequence,
                        execution_id=event.execution_id,
                        data=self._safe_event_data(event.event_type, event.data),
                    )
                elif isinstance(item, RuntimeResultItem):
                    response = self._map_outcome(request_id, item.result)
                    yield ExecutionStreamItem(
                        type="result",
                        sequence=last_sequence + 1,
                        execution_id=response.execution_id,
                        data={"result": response.model_dump(mode="json")},
                    )
                elif isinstance(item, RuntimeSuspensionItem):
                    response = self._map_outcome(request_id, item.suspension)
                    yield ExecutionStreamItem(
                        type="suspension",
                        sequence=last_sequence + 1,
                        execution_id=response.execution_id,
                        data={"result": response.model_dump(mode="json")},
                    )
        finally:
            generator = cast("AsyncGenerator[RuntimeStreamItem, None]", iterator)
            await generator.aclose()

    @staticmethod
    def _safe_event_data(
        event_type: AgentEventType, data: dict[str, object]
    ) -> dict[str, JsonValue]:
        allowed: dict[AgentEventType, frozenset[str]] = {
            AgentEventType.MODEL_TEXT_DELTA: frozenset({"text"}),
            AgentEventType.EXECUTION_STATUS_CHANGED: frozenset({"status"}),
            AgentEventType.MODEL_USAGE_UPDATED: frozenset(
                {"input_tokens", "output_tokens", "total_tokens"}
            ),
        }
        keys = allowed.get(event_type, frozenset())
        try:
            return {
                key: _JSON.validate_python(data[key]) for key in keys if key in data
            }
        except ValidationError:
            raise AdapterSerializationError(
                "Um evento não pôde ser serializado com segurança."
            ) from None

    @staticmethod
    def _map_outcome(request_id: str, outcome: RuntimeOutcome) -> ExecuteAgentResponse:
        if isinstance(outcome, ExecutionSuspension):
            suspension = AgentExecutionService._map_suspension(outcome)
            return ExecuteAgentResponse(
                request_id=request_id,
                execution_id=outcome.execution_id,
                status=AdapterExecutionStatus.WAITING_FOR_APPROVAL,
                suspension=suspension,
            )
        result = outcome
        try:
            output = _JSON.validate_python(result.output)
        except ValidationError:
            raise AdapterSerializationError(
                "O resultado da execução não pôde ser serializado."
            ) from None
        error = None
        if result.error is not None:
            error = AdapterErrorResponse(
                code=result.error.code,
                message=result.error.message,
                retryable=result.error.retryable,
                details=cast("dict[str, JsonValue]", result.error.details),
            )
        usage = UsageDTO(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cached_input_tokens=result.usage.cached_input_tokens,
            reasoning_tokens=result.usage.reasoning_tokens,
            estimated_cost=result.usage.estimated_cost,
        )
        citations = tuple(
            CitationDTO(
                citation_key=item.citation_key,
                source_id=item.source_id,
                document_id=item.document_id,
                passage_id=item.passage_id,
                title=item.title,
                uri=item.uri,
                page=None if item.location is None else item.location.page,
                section=None if item.location is None else item.location.section,
            )
            for item in result.citations
        )
        return ExecuteAgentResponse(
            request_id=request_id,
            execution_id=result.execution_id,
            status=AdapterExecutionStatus(result.status.value),
            output=output,
            error=error,
            usage=usage,
            citations=citations,
        )

    @staticmethod
    def _map_suspension(value: ExecutionSuspension) -> ExecutionSuspensionDTO:
        approval = value.approval_request
        return ExecutionSuspensionDTO(
            execution_id=value.execution_id,
            approval_request=ApprovalRequestDTO(
                approval_request_id=approval.approval_request_id,
                execution_id=approval.execution_id,
                agent_id=approval.agent_id,
                kind=approval.kind.value,
                summary=approval.summary,
                reason=approval.reason,
                requested_at=approval.requested_at,
                expires_at=approval.expires_at,
                subject=ApprovalSubjectDTO(
                    tool_call_id=approval.subject.tool_call_id,
                    tool_name=approval.subject.tool_name,
                    argument_keys=approval.subject.argument_keys,
                ),
            ),
            resume_token=value.resume_token.value,
            checkpoint_version=value.checkpoint_version,
            created_at=value.created_at,
        )
