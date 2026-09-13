from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

from atlas_agents.adapters import (
    AgentExecutionService,
    AgentRegistry,
    AllowAllAgentAccessPolicy,
    BoundedExecutionPolicyResolver,
    InMemoryIdempotencyStore,
    SubjectExecutionIdentityMapper,
)
from atlas_agents.agents import (
    AgentContext,
    AgentDefinition,
    AgentErrorInfo,
    AgentInput,
    AgentResult,
    ExecutionStatus,
    Usage,
)
from atlas_agents.approvals import (
    ApprovalDecision,
    ApprovalKind,
    ApprovalRequest,
    ExecutionSuspension,
    ResumeToken,
    ToolApprovalSubject,
)
from atlas_agents.events import AgentEvent, AgentEventType
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


def result(
    status: ExecutionStatus = ExecutionStatus.COMPLETED,
    *,
    execution_id: str = "execution-1",
) -> AgentResult[object]:
    error = None
    if status is ExecutionStatus.FAILED:
        error = AgentErrorInfo(code="model_failed", message="A execução falhou.")
    return AgentResult(
        execution_id=execution_id,
        status=status,
        output={"answer": "ok"},
        usage=Usage(input_tokens=2, output_tokens=3),
        error=error,
    )


def suspension() -> ExecutionSuspension:
    now = datetime.now(UTC)
    return ExecutionSuspension(
        execution_id="execution-1",
        approval_request=ApprovalRequest(
            approval_request_id="approval-1",
            execution_id="execution-1",
            agent_id="agent-1",
            kind=ApprovalKind.TOOL_EXECUTION,
            summary="Aprovar ferramenta",
            reason="A ferramenta exige aprovação.",
            requested_at=now,
            subject=ToolApprovalSubject(
                tool_call_id="call-1", tool_name="write", argument_keys=("value",)
            ),
        ),
        resume_token=ResumeToken(value="SECRET-RESUME-TOKEN"),
        checkpoint_version=1,
        created_at=now,
    )


class FakeRuntime:
    def __init__(self, outcome: RuntimeOutcome | None = None) -> None:
        self.outcome = outcome or result()
        self.run_calls = 0
        self.resume_calls = 0
        self.last_context: AgentContext | None = None
        self.last_limits: ExecutionLimits | None = None
        self.last_budget: ExecutionBudget | None = None
        self.last_decision: ApprovalDecision | None = None
        self.stream_closed = False

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
        del agent, input_data, model_selection
        self.run_calls += 1
        self.last_context = context
        self.last_limits = limits
        self.last_budget = budget
        return self.outcome

    async def stream(
        self,
        *,
        agent: AgentDefinition,
        input_data: AgentInput,
        context: AgentContext,
        model_selection: ModelSelectionRequest | None = None,
        limits: ExecutionLimits | None = None,
        budget: ExecutionBudget | None = None,
    ) -> AsyncIterator[RuntimeStreamItem]:
        del agent, input_data, model_selection, limits, budget
        self.run_calls += 1
        try:
            yield RuntimeEventItem(
                event=AgentEvent(
                    event_id="event-1",
                    execution_id=context.execution_id,
                    sequence=0,
                    event_type=AgentEventType.MODEL_TEXT_DELTA,
                    timestamp=datetime.now(UTC),
                    data={"text": "Olá", "provider": "não-expor"},
                )
            )
            if isinstance(self.outcome, AgentResult):
                mapped = self.outcome.model_copy(
                    update={"execution_id": context.execution_id}
                )
                yield RuntimeResultItem(result=mapped)
            else:
                yield RuntimeSuspensionItem(suspension=self.outcome)
        finally:
            self.stream_closed = True

    async def resume(
        self, *, resume_token: ResumeToken, decision: ApprovalDecision
    ) -> RuntimeOutcome:
        del resume_token
        self.resume_calls += 1
        self.last_decision = decision
        return self.outcome

    async def resume_stream(
        self, *, resume_token: ResumeToken, decision: ApprovalDecision
    ) -> AsyncIterator[RuntimeStreamItem]:
        del resume_token
        self.resume_calls += 1
        self.last_decision = decision
        try:
            if isinstance(self.outcome, AgentResult):
                yield RuntimeResultItem(result=self.outcome)
        finally:
            self.stream_closed = True


def make_service(
    runtime: FakeRuntime,
    *,
    access_policy: object | None = None,
    idempotency: bool = True,
) -> AgentExecutionService:
    registry = AgentRegistry()
    registry.register(
        AgentDefinition(
            agent_id="agent-1",
            name="Agente",
            instructions="Responda.",
        )
    )
    return AgentExecutionService(
        runtime=runtime,
        agent_registry=registry,
        identity_mapper=SubjectExecutionIdentityMapper(),
        access_policy=access_policy or AllowAllAgentAccessPolicy(),  # type: ignore[arg-type]
        policy_resolver=BoundedExecutionPolicyResolver(
            maximum_limits=ExecutionLimits(max_turns=5, timeout_seconds=30),
            maximum_budget=ExecutionBudget(
                max_estimated_cost=Decimal("1"), currency="USD"
            ),
        ),
        idempotency_store=InMemoryIdempotencyStore() if idempotency else None,
        execution_id_factory=lambda: "execution-1",
    )
