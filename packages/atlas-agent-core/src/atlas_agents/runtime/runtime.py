"""Multi-turn agent runtime orchestrating model and tool invocations."""

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Protocol, cast, runtime_checkable
from uuid import uuid4

from atlas_agents.agents import (
    AgentContext,
    AgentDefinition,
    AgentErrorInfo,
    AgentInput,
    AgentResult,
    ExecutionStatus,
)
from atlas_agents.approvals import (
    ApprovalContext,
    ApprovalDecision,
    ApprovalDecisionType,
    ApprovalDecisionValidator,
    ApprovalNotRequired,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalRequired,
    ApprovalRequirement,
    CheckpointStoreRequiredError,
    DefaultApprovalDecisionValidator,
    ExecutionSuspension,
    InvalidCheckpointError,
    NoApprovalPolicy,
    ResumeToken,
    ToolApprovalMode,
    ToolApprovalSubject,
)
from atlas_agents.events import AgentEvent, AgentEventFactory, AgentEventType
from atlas_agents.exceptions import (
    ModelProviderError,
    ModelProviderRegistryError,
    ModelSelectionError,
)
from atlas_agents.guardrails import (
    GuardrailContext,
    GuardrailDecision,
    GuardrailEnforcement,
    GuardrailError,
    GuardrailEvaluationError,
    GuardrailManager,
    GuardrailNotRegisteredError,
    GuardrailPipelineResult,
    GuardrailProtocolError,
    GuardrailRecord,
    GuardrailStage,
    GuardrailStageMismatchError,
)
from atlas_agents.guardrails.inputs import (
    FinalOutputGuardrailInput,
    InputGuardrailInput,
    ModelOutputGuardrailInput,
    ToolCallGuardrailInput,
    ToolResultGuardrailInput,
)
from atlas_agents.knowledge import (
    DefaultKnowledgeQueryBuilder,
    KnowledgeContextError,
    KnowledgeContextRenderer,
    KnowledgeError,
    KnowledgeManager,
    KnowledgePolicyError,
    KnowledgeProtocolError,
    KnowledgeQuery,
    KnowledgeQueryBuilder,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalError,
    KnowledgeSourceNotFoundError,
)
from atlas_agents.memory import (
    AgentMemoryError,
    DefaultMemoryScopePolicy,
    MemoryCandidate,
    MemoryContextRenderer,
    MemoryManager,
    MemoryPolicyViolationError,
    MemoryQuery,
    MemoryScopePolicy,
    MemoryScopeResolutionError,
    MemorySearchResult,
    MemoryStoreProtocolError,
    MemoryWritePolicy,
    MemoryWriteRequest,
    NoMemoryWritePolicy,
)
from atlas_agents.memory.types import _MEMORY_TYPE_ORDER
from atlas_agents.models import (
    FinishReason,
    MessageRole,
    ModelCapability,
    ModelExecutionContext,
    ModelMessage,
    ModelProvider,
    ModelProviderRegistry,
    ModelResponse,
    ModelSelectionRequest,
    ModelSelectionResult,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelToolDefinition,
    TextContent,
    ToolCall,
)
from atlas_agents.observability import (
    ObservabilityManager,
    SafeSpan,
    SpanKind,
    SpanStatus,
    TraceContext,
)
from atlas_agents.runtime.budget import ExecutionBudget, ExecutionBudgetViolation
from atlas_agents.runtime.checkpoint import (
    CURRENT_CHECKPOINT_VERSION,
    CheckpointStore,
    ExecutionCheckpoint,
    ExecutionMode,
)
from atlas_agents.runtime.deadline import (
    ExecutionDeadline,
    ExecutionDeadlineExpiredError,
)
from atlas_agents.runtime.enforcement import ExecutionLimitChecker
from atlas_agents.runtime.error_mapping import (
    model_provider_error_to_agent_error,
    model_selection_error_to_agent_error,
    registry_error_to_agent_error,
)
from atlas_agents.runtime.errors import (
    InvalidModelStreamProtocolError,
    InvalidModelStreamSequenceError,
    ModelStreamIncompleteError,
    ModelStreamProtocolError,
    ModelStreamReportedError,
    RuntimeInputRejectedError,
)
from atlas_agents.runtime.limits import (
    ExecutionLimits,
    ExecutionLimitViolation,
)
from atlas_agents.runtime.model_request import ModelRequestBuilder
from atlas_agents.runtime.outcome import RuntimeOutcome
from atlas_agents.runtime.restorer import ExecutionStateRestorer
from atlas_agents.runtime.state import ExecutionState
from atlas_agents.runtime.stream_accumulator import ModelStreamAccumulator
from atlas_agents.runtime.stream_items import (
    RuntimeEventItem,
    RuntimeResultItem,
    RuntimeStreamItem,
    RuntimeSuspensionItem,
)
from atlas_agents.runtime.tool_calls import ToolCallRecord
from atlas_agents.runtime.tool_results import ToolResultMessageMapper
from atlas_agents.tools import (
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutionError,
    ToolExecutionInvariantError,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolExecutor,
    ToolNotRegisteredError,
    ToolRegistry,
)


@dataclass(frozen=True)
class _PreparedExecution:
    state: ExecutionState
    factory: AgentEventFactory
    provider: ModelProvider
    selection: ModelSelectionResult
    tool_definitions: tuple[ModelToolDefinition, ...]


@dataclass(frozen=True)
class _ExecutionPolicies:
    limits: ExecutionLimits
    budget: ExecutionBudget
    deadline: ExecutionDeadline
    observation: "_InvocationObservation"


@dataclass(frozen=True)
class _InvocationObservation:
    span: SafeSpan
    started_at: float
    mode: ExecutionMode
    resumed: bool


@dataclass(frozen=True)
class _OperationObservation:
    span: SafeSpan
    started_at: float


@runtime_checkable
class _AsyncClosable(Protocol):
    async def aclose(self) -> None:
        """Close an asynchronous provider iterator."""


class AgentRuntime:
    """Own the provider-agnostic multi-turn model and tool execution loop."""

    def __init__(
        self,
        *,
        model_registry: ModelProviderRegistry,
        tool_registry: ToolRegistry | None = None,
        tool_executor: ToolExecutor | None = None,
        request_builder: ModelRequestBuilder | None = None,
        limits: ExecutionLimits | None = None,
        budget: ExecutionBudget | None = None,
        approval_policy: ApprovalPolicy | None = None,
        approval_decision_validator: ApprovalDecisionValidator | None = None,
        checkpoint_store: CheckpointStore | None = None,
        memory_manager: MemoryManager | None = None,
        memory_scope_policy: MemoryScopePolicy | None = None,
        memory_context_renderer: MemoryContextRenderer | None = None,
        memory_write_policy: MemoryWritePolicy | None = None,
        knowledge_manager: KnowledgeManager | None = None,
        knowledge_query_builder: KnowledgeQueryBuilder | None = None,
        knowledge_context_renderer: KnowledgeContextRenderer | None = None,
        guardrail_manager: GuardrailManager | None = None,
        observability_manager: ObservabilityManager | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the runtime with explicit replaceable dependencies."""
        self._model_registry = model_registry
        if tool_executor is not None and tool_registry is None:
            msg = "tool_registry deve ser informado junto com tool_executor"
            raise ValueError(msg)
        self._tool_registry = (
            tool_registry if tool_registry is not None else ToolRegistry()
        )
        self._tool_executor = (
            tool_executor
            if tool_executor is not None
            else ToolExecutor(registry=self._tool_registry)
        )
        self._tool_result_mapper = ToolResultMessageMapper()
        self._request_builder = (
            request_builder if request_builder is not None else ModelRequestBuilder()
        )
        self._default_limits = limits if limits is not None else ExecutionLimits()
        self._default_budget = budget if budget is not None else ExecutionBudget()
        self._limit_checker = ExecutionLimitChecker()
        self._approval_policy = (
            approval_policy if approval_policy is not None else NoApprovalPolicy()
        )
        self._approval_decision_validator = (
            approval_decision_validator
            if approval_decision_validator is not None
            else DefaultApprovalDecisionValidator()
        )
        self._checkpoint_store = checkpoint_store
        self._memory_manager = memory_manager
        self._memory_scope_policy = (
            memory_scope_policy
            if memory_scope_policy is not None
            else DefaultMemoryScopePolicy()
        )
        self._memory_context_renderer = (
            memory_context_renderer
            if memory_context_renderer is not None
            else MemoryContextRenderer()
        )
        self._memory_write_policy = (
            memory_write_policy
            if memory_write_policy is not None
            else NoMemoryWritePolicy()
        )
        self._knowledge_manager = knowledge_manager
        self._knowledge_query_builder = (
            knowledge_query_builder
            if knowledge_query_builder is not None
            else DefaultKnowledgeQueryBuilder()
        )
        self._knowledge_context_renderer = (
            knowledge_context_renderer
            if knowledge_context_renderer is not None
            else KnowledgeContextRenderer()
        )
        self._guardrail_manager = guardrail_manager
        self._observability = (
            observability_manager
            if observability_manager is not None
            else ObservabilityManager()
        )
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._state_restorer = ExecutionStateRestorer()

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
        """Execute model and tool turns and return a terminal result."""
        state = ExecutionState(
            execution_id=context.execution_id,
            agent=agent,
            input_data=input_data,
            context=context,
        )
        observation = self._start_runtime_observation(
            state=state,
            mode=ExecutionMode.RUN,
            resumed=False,
            parent=context.trace_context,
        )
        policies = self._resolve_policies(
            limits=limits,
            budget=budget,
            observation=observation,
        )
        factory = AgentEventFactory(context.execution_id)
        self._start_execution(state, factory)
        try:
            return await policies.deadline.wait_for(
                lambda: self._run_execution(
                    state=state,
                    factory=factory,
                    agent=agent,
                    input_data=input_data,
                    model_selection=model_selection,
                    policies=policies,
                )
            )
        except ExecutionDeadlineExpiredError:
            if not state.is_terminal:
                self._timeout(state, factory, policies.deadline)
            return state.to_result()
        except asyncio.CancelledError:
            if not state.is_terminal:
                if self._model_invocation_open(state):
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "cancelled"},
                    )
                self._cancel(
                    state,
                    factory,
                    reason="A execução foi cancelada pelo consumidor.",
                )
            raise
        finally:
            self._finish_runtime_observation(state, observation)

    async def resume(
        self,
        *,
        resume_token: ResumeToken,
        decision: ApprovalDecision,
    ) -> RuntimeOutcome:
        """Atomically consume a run checkpoint and continue its execution."""
        checkpoint = await self._consume_checkpoint(
            resume_token,
            expected_mode=ExecutionMode.RUN,
        )
        state = self._state_restorer.restore(checkpoint)
        observation = self._start_runtime_observation(
            state=state,
            mode=ExecutionMode.RUN,
            resumed=True,
            parent=checkpoint.trace_context,
        )
        factory = AgentEventFactory(
            state.execution_id,
            initial_sequence=len(state.events),
        )
        policies = self._checkpoint_policies(checkpoint, observation)
        try:
            resumed = await policies.deadline.wait_for(
                lambda: self._resume_decision_and_tools(
                    checkpoint=checkpoint,
                    state=state,
                    factory=factory,
                    decision=decision,
                    policies=policies,
                )
            )
            if isinstance(resumed, _PreparedExecution):
                return await policies.deadline.wait_for(
                    lambda: self._run_model_loop(
                        prepared=resumed,
                        policies=policies,
                        execution_mode=ExecutionMode.RUN,
                    )
                )
            return resumed
        except ExecutionDeadlineExpiredError:
            if not state.is_terminal:
                self._timeout(state, factory, policies.deadline)
            return state.to_result()
        except asyncio.CancelledError:
            if not state.is_terminal:
                if self._model_invocation_open(state):
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "cancelled"},
                    )
                self._cancel(
                    state,
                    factory,
                    reason="A retomada foi cancelada pelo consumidor.",
                )
            raise
        finally:
            self._finish_runtime_observation(state, observation)

    async def resume_stream(
        self,
        *,
        resume_token: ResumeToken,
        decision: ApprovalDecision,
    ) -> AsyncIterator[RuntimeStreamItem]:
        """Resume a streaming checkpoint without switching model transport."""
        checkpoint = await self._consume_checkpoint(
            resume_token,
            expected_mode=ExecutionMode.STREAM,
        )
        state = self._state_restorer.restore(checkpoint)
        observation = self._start_runtime_observation(
            state=state,
            mode=ExecutionMode.STREAM,
            resumed=True,
            parent=checkpoint.trace_context,
        )
        factory = AgentEventFactory(
            state.execution_id,
            initial_sequence=len(state.events),
        )
        policies = self._checkpoint_policies(checkpoint, observation)
        previous_event_count = len(state.events)
        suspended = False
        try:
            resumed = await policies.deadline.wait_for(
                lambda: self._resume_decision_and_tools(
                    checkpoint=checkpoint,
                    state=state,
                    factory=factory,
                    decision=decision,
                    policies=policies,
                )
            )
            for event in state.events[previous_event_count:]:
                yield RuntimeEventItem(event=event)
            if isinstance(resumed, ExecutionSuspension):
                suspended = True
                yield RuntimeSuspensionItem(suspension=resumed)
                return
            if isinstance(resumed, AgentResult):
                yield RuntimeResultItem(result=resumed)
                return
            async for item in self._stream_followup_turns(
                state=state,
                factory=factory,
                prepared=resumed,
                agent=state.agent,
                policies=policies,
            ):
                if isinstance(item, RuntimeSuspensionItem):
                    suspended = True
                yield item
            return
        except ExecutionDeadlineExpiredError:
            if not state.is_terminal:
                if self._model_invocation_open(state):
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "timed_out", "mode": "stream"},
                    )
                self._timeout(state, factory, policies.deadline)
            for event in state.events[previous_event_count:]:
                yield RuntimeEventItem(event=event)
            yield RuntimeResultItem(result=state.to_result())
        except asyncio.CancelledError:
            if not state.is_terminal:
                self._cancel(
                    state,
                    factory,
                    reason="A retomada incremental foi cancelada pelo consumidor.",
                )
            raise
        finally:
            if not state.is_terminal and not suspended:
                self._cancel(
                    state,
                    factory,
                    reason="O consumidor encerrou a retomada antes da conclusão.",
                )
            self._finish_runtime_observation(state, observation)

    async def _consume_checkpoint(
        self,
        resume_token: ResumeToken,
        *,
        expected_mode: ExecutionMode,
    ) -> ExecutionCheckpoint:
        store = self._checkpoint_store
        if store is None:
            raise CheckpointStoreRequiredError(
                "A retomada exige um armazenamento de checkpoint configurado."
            )
        observation = _OperationObservation(
            span=self._observability.start_span(
                "atlas.checkpoint.consume",
                kind=SpanKind.CLIENT,
                attributes={"atlas.operation": "consume"},
            ),
            started_at=self._observability.now(),
        )
        try:
            checkpoint = await store.consume(resume_token)
        except asyncio.CancelledError:
            self._finish_operation_observation(
                observation,
                outcome="cancelled",
                status=SpanStatus.UNSET,
            )
            raise
        except Exception:
            self._finish_operation_observation(
                observation,
                outcome="failed",
                status=SpanStatus.ERROR,
                error_code="checkpoint_consume_failed",
            )
            self._observability.increment(
                "atlas.checkpoint.operations",
                attributes={"operation": "consume", "outcome": "failed"},
            )
            raise
        observation.span.set_attribute(
            "atlas.checkpoint.version", checkpoint.checkpoint_version
        )
        self._finish_operation_observation(
            observation,
            outcome="completed",
            status=SpanStatus.OK,
        )
        self._observability.increment(
            "atlas.checkpoint.operations",
            attributes={"operation": "consume", "outcome": "completed"},
        )
        if checkpoint.execution_mode is not expected_mode:
            raise InvalidCheckpointError(
                "O checkpoint deve ser retomado pela mesma modalidade de execução."
            )
        return checkpoint

    def _checkpoint_policies(
        self,
        checkpoint: ExecutionCheckpoint,
        observation: _InvocationObservation,
    ) -> _ExecutionPolicies:
        return _ExecutionPolicies(
            limits=checkpoint.limits,
            budget=checkpoint.budget,
            deadline=ExecutionDeadline.start(checkpoint.remaining_timeout_seconds),
            observation=observation,
        )

    async def _resume_decision_and_tools(
        self,
        *,
        checkpoint: ExecutionCheckpoint,
        state: ExecutionState,
        factory: AgentEventFactory,
        decision: ApprovalDecision,
        policies: _ExecutionPolicies,
    ) -> _PreparedExecution | RuntimeOutcome:
        request = checkpoint.pending_approval
        self._approval_decision_validator.validate(
            request=request,
            decision=decision,
        )
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_RESUMED,
            {"approval_request_id": request.approval_request_id},
        )
        state.resolve_approval(decision)
        self._observability.increment(
            "atlas.approval.decisions",
            attributes={"decision": decision.decision.value},
        )
        self._observability.record(
            "atlas.approval.wait_duration",
            max(0.0, (decision.decided_at - request.requested_at).total_seconds()),
            attributes={"decision": decision.decision.value},
        )
        expired = request.expires_at is not None and self._clock() >= request.expires_at
        if expired or decision.decision is ApprovalDecisionType.REJECT:
            code = "approval_expired" if expired else "approval_rejected"
            reason = (
                "A solicitação de aprovação expirou."
                if expired
                else decision.reason or "A execução foi rejeitada pelo aprovador."
            )
            self._record(
                state,
                factory,
                AgentEventType.APPROVAL_REJECTED,
                {
                    "approval_request_id": request.approval_request_id,
                    "code": code,
                },
            )
            self._reject(
                state,
                factory,
                code=code,
                reason=reason,
                retain_error=True,
            )
            return state.to_result()

        self._record(
            state,
            factory,
            AgentEventType.APPROVAL_GRANTED,
            {"approval_request_id": request.approval_request_id},
        )
        prepared = self._restore_prepared_execution(state, factory)
        if isinstance(prepared, AgentResult):
            return prepared
        tool_outcome = await self._process_tool_batch(
            state=state,
            factory=factory,
            calls=checkpoint.pending_tool_calls,
            policies=policies,
            execution_mode=checkpoint.execution_mode,
            approved_call_id=request.subject.tool_call_id,
        )
        return prepared if tool_outcome is None else tool_outcome

    def _restore_prepared_execution(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
    ) -> _PreparedExecution | AgentResult[object]:
        selection = state.model_selection
        if selection is None:
            self._fail(state, factory, self._runtime_error())
            return state.to_result()
        if (
            state.agent.memory is not None
            and state.agent.memory.enabled
            and self._memory_manager is None
        ):
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_manager_required",
                    message=(
                        "A retomada exige o MemoryManager configurado na execução."
                    ),
                ),
            )
            return state.to_result()
        if (
            state.agent.knowledge is not None
            and state.agent.knowledge.enabled
            and self._knowledge_manager is None
        ):
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="knowledge_manager_required",
                    message=(
                        "A retomada exige o KnowledgeManager configurado na execução."
                    ),
                ),
            )
            return state.to_result()
        guardrail_config = state.agent.guardrails
        if guardrail_config is not None and guardrail_config.enabled:
            manager = self._guardrail_manager
            if manager is None:
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="guardrail_manager_required",
                        message=(
                            "A retomada exige o GuardrailManager configurado na "
                            "execução."
                        ),
                    ),
                )
                return state.to_result()
            try:
                manager.validate_config(guardrail_config)
            except GuardrailNotRegisteredError:
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="guardrail_not_registered",
                        message="Um guardrail da execução não está mais registrado.",
                    ),
                )
                return state.to_result()
            except GuardrailStageMismatchError:
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="guardrail_stage_mismatch",
                        message="Um guardrail está registrado no estágio incorreto.",
                    ),
                )
                return state.to_result()
        try:
            provider = self._model_registry.get(selection.provider_name)
            tools = tuple(
                self._tool_registry.get(name) for name in state.agent.tool_names
            )
        except ToolNotRegisteredError as error:
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="tool_not_found_after_resume",
                    message="Uma ferramenta da execução não está mais registrada.",
                    details={"tool_name": error.tool_name},
                ),
            )
            return state.to_result()
        except ModelProviderRegistryError as error:
            self._fail(state, factory, registry_error_to_agent_error(error))
            return state.to_result()
        except Exception:
            self._fail(state, factory, self._runtime_error())
            return state.to_result()
        return _PreparedExecution(
            state=state,
            factory=factory,
            provider=provider,
            selection=selection,
            tool_definitions=tuple(
                tool.definition.to_model_definition() for tool in tools
            ),
        )

    @staticmethod
    def _model_invocation_open(state: ExecutionState) -> bool:
        started = sum(
            event.event_type is AgentEventType.MODEL_EXECUTION_STARTED
            for event in state.events
        )
        completed = sum(
            event.event_type is AgentEventType.MODEL_EXECUTION_COMPLETED
            for event in state.events
        )
        return started > completed

    async def _run_execution(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        agent: AgentDefinition,
        input_data: AgentInput,
        model_selection: ModelSelectionRequest | None,
        policies: _ExecutionPolicies,
    ) -> RuntimeOutcome:
        """Run model and tool turns inside one unchanged policy scope."""
        prepared = await self._prepare(
            state=state,
            factory=factory,
            agent=agent,
            input_data=input_data,
            model_selection=model_selection,
            policies=policies,
        )
        if isinstance(prepared, AgentResult):
            return prepared
        return await self._run_model_loop(
            prepared=prepared,
            policies=policies,
            execution_mode=ExecutionMode.RUN,
        )

    async def _run_model_loop(
        self,
        *,
        prepared: _PreparedExecution,
        policies: _ExecutionPolicies,
        execution_mode: ExecutionMode,
    ) -> RuntimeOutcome:
        """Continue complete model turns using one preserved selection."""
        state = prepared.state
        factory = prepared.factory
        while True:
            turn_violation = self._limit_checker.check_turn_allowed(
                limits=policies.limits,
                current_turn_count=state.turn_count,
            )
            if turn_violation is not None:
                return self._exceed_limit(state, factory, turn_violation)
            self._record(
                state,
                factory,
                AgentEventType.MODEL_EXECUTION_STARTED,
                {
                    "provider": prepared.selection.provider_name,
                    "model": prepared.selection.model,
                    "turn": state.turn_count + 1,
                },
            )
            state.increment_turn()
            request = self._request_builder.build_request(
                state,
                prepared.selection,
                tools=prepared.tool_definitions,
            )
            model_context = self._model_context(state, state.agent)
            model_observation = self._start_model_observation(
                state=state,
                selection=prepared.selection,
                policies=policies,
                mode="generate",
                request_id=model_context.request_id,
            )
            response: ModelResponse | None = None
            model_outcome = "completed"
            model_status = SpanStatus.OK
            model_error_code: str | None = None
            try:
                response = await prepared.provider.generate(request, model_context)
            except asyncio.CancelledError:
                model_outcome = (
                    "timed_out" if policies.deadline.expired else "cancelled"
                )
                model_status = (
                    SpanStatus.ERROR if policies.deadline.expired else SpanStatus.UNSET
                )
                raise
            except ModelProviderError as error:
                model_outcome = "failed"
                model_status = SpanStatus.ERROR
                model_error_code = "model_provider_error"
                self._record(
                    state,
                    factory,
                    AgentEventType.MODEL_EXECUTION_COMPLETED,
                    {"outcome": "failed"},
                )
                self._fail(
                    state,
                    factory,
                    model_provider_error_to_agent_error(error),
                )
                return state.to_result()
            except Exception:
                model_outcome = "failed"
                model_status = SpanStatus.ERROR
                model_error_code = "runtime_error"
                self._record(
                    state,
                    factory,
                    AgentEventType.MODEL_EXECUTION_COMPLETED,
                    {"outcome": "failed"},
                )
                self._fail(state, factory, self._runtime_error())
                return state.to_result()
            finally:
                self._finish_model_observation(
                    model_observation,
                    selection=prepared.selection,
                    mode="generate",
                    outcome=model_outcome,
                    status=model_status,
                    response=response,
                    error_code=model_error_code,
                )

            policies.deadline.raise_if_expired()
            self._record(
                state,
                factory,
                AgentEventType.MODEL_EXECUTION_COMPLETED,
                {
                    "outcome": "completed",
                    "finish_reason": response.finish_reason.value,
                },
            )
            state.add_model_usage(response.usage)
            policy_result = self._enforce_usage(state, factory, policies)
            if policy_result is not None:
                return policy_result
            guarded_response = await self._guard_model_response(
                state=state,
                factory=factory,
                response=response,
                policies=policies,
            )
            if isinstance(guarded_response, AgentResult):
                return guarded_response
            response = guarded_response
            if response.finish_reason is FinishReason.TOOL_CALL:
                tool_result = await self._process_tool_calls(
                    state=state,
                    factory=factory,
                    response=response,
                    policies=policies,
                    execution_mode=execution_mode,
                )
                if tool_result is not None:
                    return tool_result
                continue

            state.add_message(
                ModelMessage(role=MessageRole.ASSISTANT, content=response.content)
            )
            self._transition(state, factory, ExecutionStatus.VALIDATING_OUTPUT)
            self._record(state, factory, AgentEventType.OUTPUT_VALIDATION_STARTED)
            return await self._finish_response(state, factory, response, policies)

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
        """Yield incremental execution events followed by one terminal result."""
        state = ExecutionState(
            execution_id=context.execution_id,
            agent=agent,
            input_data=input_data,
            context=context,
        )
        observation = self._start_runtime_observation(
            state=state,
            mode=ExecutionMode.STREAM,
            resumed=False,
            parent=context.trace_context,
        )
        policies = self._resolve_policies(
            limits=limits,
            budget=budget,
            observation=observation,
        )
        factory = AgentEventFactory(context.execution_id)
        self._start_execution(state, factory)
        emitted_events = 0
        provider_iterator: AsyncIterator[ModelStreamEvent] | None = None
        provider_exhausted = False
        active_model_observation: _OperationObservation | None = None
        active_model_selection: ModelSelectionResult | None = None
        suspended = False
        result: RuntimeOutcome
        try:
            prepared = await policies.deadline.wait_for(
                lambda: self._prepare(
                    state=state,
                    factory=factory,
                    agent=agent,
                    input_data=input_data,
                    model_selection=model_selection,
                    policies=policies,
                    additional_required_capabilities=frozenset(
                        {ModelCapability.STREAMING}
                    ),
                )
            )
            if isinstance(prepared, AgentResult):
                for event in prepared.events:
                    yield RuntimeEventItem(event=event)
                yield RuntimeResultItem(result=prepared)
                return

            for event in state.events:
                yield RuntimeEventItem(event=event)
                emitted_events += 1

            turn_violation = self._limit_checker.check_turn_allowed(
                limits=policies.limits,
                current_turn_count=state.turn_count,
            )
            if turn_violation is not None:
                result = self._exceed_limit(state, factory, turn_violation)
            else:
                started_event = self._record(
                    state,
                    factory,
                    AgentEventType.MODEL_EXECUTION_STARTED,
                    {
                        "provider": prepared.selection.provider_name,
                        "model": prepared.selection.model,
                        "mode": "stream",
                    },
                )
                yield RuntimeEventItem(event=started_event)
                emitted_events += 1
                state.increment_turn()
                accumulator = ModelStreamAccumulator()
                model_context = self._model_context(state, agent)
                model_observation = self._start_model_observation(
                    state=state,
                    selection=prepared.selection,
                    policies=policies,
                    mode="stream",
                    request_id=model_context.request_id,
                )
                active_model_observation = model_observation
                active_model_selection = prepared.selection
                stream_event_count = 0
                first_delta_recorded = False
                try:
                    request = self._request_builder.build_request(
                        state,
                        prepared.selection,
                        tools=prepared.tool_definitions,
                    )
                    provider_iterator = prepared.provider.stream(
                        request,
                        model_context,
                    )
                    while True:
                        try:
                            model_event = await policies.deadline.wait_for(
                                lambda: anext(provider_iterator)
                            )
                        except StopAsyncIteration:
                            provider_exhausted = True
                            break
                        policies.deadline.raise_if_expired()
                        stream_event_count += 1
                        if (
                            model_event.type is ModelStreamEventType.TEXT_DELTA
                            and not first_delta_recorded
                        ):
                            first_delta_recorded = True
                            self._observability.record(
                                "atlas.model.stream.time_to_first_delta",
                                self._observability.elapsed_since(
                                    model_observation.started_at
                                ),
                                attributes={
                                    "provider": prepared.selection.provider_name,
                                    "model": prepared.selection.model,
                                    "mode": "stream",
                                    "outcome": "observed",
                                },
                            )
                        accumulator.consume(model_event)
                        runtime_event = self._record_model_stream_event(
                            state,
                            factory,
                            model_event,
                        )
                        yield RuntimeEventItem(event=runtime_event)
                        emitted_events += 1
                    response = accumulator.finalize()
                except ExecutionDeadlineExpiredError:
                    self._finish_model_observation(
                        model_observation,
                        selection=prepared.selection,
                        mode="stream",
                        outcome="timed_out",
                        status=SpanStatus.ERROR,
                        error_code="execution_timed_out",
                    )
                    raise
                except asyncio.CancelledError:
                    self._finish_model_observation(
                        model_observation,
                        selection=prepared.selection,
                        mode="stream",
                        outcome="cancelled",
                        status=SpanStatus.UNSET,
                    )
                    raise
                except ModelProviderError as error:
                    self._finish_model_observation(
                        model_observation,
                        selection=prepared.selection,
                        mode="stream",
                        outcome="failed",
                        status=SpanStatus.ERROR,
                        error_code="model_provider_error",
                    )
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "failed", "mode": "stream"},
                    )
                    self._fail(
                        state,
                        factory,
                        model_provider_error_to_agent_error(error),
                    )
                    result = state.to_result()
                except ModelStreamProtocolError as error:
                    self._finish_model_observation(
                        model_observation,
                        selection=prepared.selection,
                        mode="stream",
                        outcome="failed",
                        status=SpanStatus.ERROR,
                        error_code="model_stream_protocol_error",
                    )
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "failed", "mode": "stream"},
                    )
                    self._fail(state, factory, self._stream_error(error))
                    result = state.to_result()
                except Exception:
                    self._finish_model_observation(
                        model_observation,
                        selection=prepared.selection,
                        mode="stream",
                        outcome="failed",
                        status=SpanStatus.ERROR,
                        error_code="runtime_error",
                    )
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "failed", "mode": "stream"},
                    )
                    self._fail(state, factory, self._runtime_error())
                    result = state.to_result()
                else:
                    model_observation.span.set_attribute(
                        "atlas.model.stream.event_count", stream_event_count
                    )
                    self._observability.record(
                        "atlas.model.stream.event_count",
                        stream_event_count,
                        attributes={
                            "provider": prepared.selection.provider_name,
                            "model": prepared.selection.model,
                            "mode": "stream",
                            "outcome": "completed",
                        },
                    )
                    self._finish_model_observation(
                        model_observation,
                        selection=prepared.selection,
                        mode="stream",
                        outcome="completed",
                        status=SpanStatus.OK,
                        response=response,
                    )
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {
                            "outcome": "completed",
                            "mode": "stream",
                            "finish_reason": response.finish_reason.value,
                        },
                    )
                    state.add_model_usage(response.usage)
                    policy_result = self._enforce_usage(state, factory, policies)
                    if policy_result is not None:
                        result = policy_result
                    else:
                        guarded_response = await self._guard_model_response(
                            state=state,
                            factory=factory,
                            response=response,
                            policies=policies,
                        )
                        if isinstance(guarded_response, AgentResult):
                            result = guarded_response
                        else:
                            response = guarded_response
                    if (
                        policy_result is None
                        and not isinstance(guarded_response, AgentResult)
                        and response.finish_reason is FinishReason.TOOL_CALL
                    ):
                        tool_result = await self._process_tool_calls(
                            state=state,
                            factory=factory,
                            response=response,
                            policies=policies,
                            execution_mode=ExecutionMode.STREAM,
                        )
                        for event in state.events[emitted_events:]:
                            yield RuntimeEventItem(event=event)
                            emitted_events += 1
                        if tool_result is not None:
                            result = tool_result
                            suspended = isinstance(tool_result, ExecutionSuspension)
                        else:
                            async for item in self._stream_followup_turns(
                                state=state,
                                factory=factory,
                                prepared=prepared,
                                agent=agent,
                                policies=policies,
                            ):
                                if isinstance(item, RuntimeSuspensionItem):
                                    suspended = True
                                yield item
                            return
                    elif policy_result is None and not isinstance(
                        guarded_response, AgentResult
                    ):
                        state.add_message(
                            ModelMessage(
                                role=MessageRole.ASSISTANT,
                                content=response.content,
                            )
                        )
                        self._transition(
                            state,
                            factory,
                            ExecutionStatus.VALIDATING_OUTPUT,
                        )
                        self._record(
                            state,
                            factory,
                            AgentEventType.OUTPUT_VALIDATION_STARTED,
                        )
                        result = await self._finish_response(
                            state,
                            factory,
                            response,
                            policies,
                        )
        except ExecutionDeadlineExpiredError:
            if not state.is_terminal and not suspended:
                if self._model_invocation_open(state):
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "timed_out", "mode": "stream"},
                    )
                self._timeout(state, factory, policies.deadline)
            result = state.to_result()
        except asyncio.CancelledError:
            if not state.is_terminal:
                if self._model_invocation_open(state):
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "cancelled", "mode": "stream"},
                    )
                self._cancel(
                    state,
                    factory,
                    reason="O stream foi cancelado pelo consumidor.",
                )
            raise
        finally:
            if (
                provider_iterator is not None
                and not provider_exhausted
                and isinstance(provider_iterator, _AsyncClosable)
            ):
                await provider_iterator.aclose()
            if (
                active_model_observation is not None
                and active_model_selection is not None
                and not active_model_observation.span.ended
            ):
                self._finish_model_observation(
                    active_model_observation,
                    selection=active_model_selection,
                    mode="stream",
                    outcome="cancelled",
                    status=SpanStatus.UNSET,
                )
            if not state.is_terminal and not suspended:
                if self._model_invocation_open(state):
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "cancelled", "mode": "stream"},
                    )
                self._cancel(
                    state,
                    factory,
                    reason="O consumidor encerrou o stream antes da conclusão.",
                )
            self._finish_runtime_observation(state, observation)

        for event in state.events[emitted_events:]:
            yield RuntimeEventItem(event=event)
            emitted_events += 1
        if isinstance(result, ExecutionSuspension):
            yield RuntimeSuspensionItem(suspension=result)
        else:
            yield RuntimeResultItem(result=result)

    async def _stream_followup_turns(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        prepared: _PreparedExecution,
        agent: AgentDefinition,
        policies: _ExecutionPolicies,
    ) -> AsyncIterator[RuntimeStreamItem]:
        """Continue a streaming execution after the first processed tool batch."""
        emitted_events = len(state.events)
        result: RuntimeOutcome | None = None
        while result is None:
            turn_violation = self._limit_checker.check_turn_allowed(
                limits=policies.limits,
                current_turn_count=state.turn_count,
            )
            if turn_violation is not None:
                result = self._exceed_limit(state, factory, turn_violation)
                break

            started_event = self._record(
                state,
                factory,
                AgentEventType.MODEL_EXECUTION_STARTED,
                {
                    "provider": prepared.selection.provider_name,
                    "model": prepared.selection.model,
                    "mode": "stream",
                    "turn": state.turn_count + 1,
                },
            )
            yield RuntimeEventItem(event=started_event)
            emitted_events += 1
            state.increment_turn()
            accumulator = ModelStreamAccumulator()
            provider_iterator: AsyncIterator[ModelStreamEvent] | None = None
            provider_exhausted = False
            model_stream_completed = False
            model_context = self._model_context(state, agent)
            model_observation = self._start_model_observation(
                state=state,
                selection=prepared.selection,
                policies=policies,
                mode="stream",
                request_id=model_context.request_id,
            )
            stream_event_count = 0
            first_delta_recorded = False
            try:
                request = self._request_builder.build_request(
                    state,
                    prepared.selection,
                    tools=prepared.tool_definitions,
                )
                provider_iterator = prepared.provider.stream(
                    request,
                    model_context,
                )
                while True:
                    try:
                        model_event = await policies.deadline.wait_for(
                            partial(anext, provider_iterator)
                        )
                    except StopAsyncIteration:
                        provider_exhausted = True
                        break
                    policies.deadline.raise_if_expired()
                    stream_event_count += 1
                    if (
                        model_event.type is ModelStreamEventType.TEXT_DELTA
                        and not first_delta_recorded
                    ):
                        first_delta_recorded = True
                        self._observability.record(
                            "atlas.model.stream.time_to_first_delta",
                            self._observability.elapsed_since(
                                model_observation.started_at
                            ),
                            attributes={
                                "provider": prepared.selection.provider_name,
                                "model": prepared.selection.model,
                                "mode": "stream",
                                "outcome": "observed",
                            },
                        )
                    accumulator.consume(model_event)
                    runtime_event = self._record_model_stream_event(
                        state,
                        factory,
                        model_event,
                    )
                    yield RuntimeEventItem(event=runtime_event)
                    emitted_events += 1
                response = accumulator.finalize()
                model_stream_completed = True
            except ExecutionDeadlineExpiredError:
                self._finish_model_observation(
                    model_observation,
                    selection=prepared.selection,
                    mode="stream",
                    outcome="timed_out",
                    status=SpanStatus.ERROR,
                    error_code="execution_timed_out",
                )
                raise
            except asyncio.CancelledError:
                self._finish_model_observation(
                    model_observation,
                    selection=prepared.selection,
                    mode="stream",
                    outcome="cancelled",
                    status=SpanStatus.UNSET,
                )
                raise
            except ModelProviderError as error:
                self._finish_model_observation(
                    model_observation,
                    selection=prepared.selection,
                    mode="stream",
                    outcome="failed",
                    status=SpanStatus.ERROR,
                    error_code="model_provider_error",
                )
                self._record(
                    state,
                    factory,
                    AgentEventType.MODEL_EXECUTION_COMPLETED,
                    {"outcome": "failed", "mode": "stream"},
                )
                self._fail(
                    state,
                    factory,
                    model_provider_error_to_agent_error(error),
                )
                result = state.to_result()
                break
            except ModelStreamProtocolError as error:
                self._finish_model_observation(
                    model_observation,
                    selection=prepared.selection,
                    mode="stream",
                    outcome="failed",
                    status=SpanStatus.ERROR,
                    error_code="model_stream_protocol_error",
                )
                self._record(
                    state,
                    factory,
                    AgentEventType.MODEL_EXECUTION_COMPLETED,
                    {"outcome": "failed", "mode": "stream"},
                )
                self._fail(state, factory, self._stream_error(error))
                result = state.to_result()
                break
            except Exception:
                self._finish_model_observation(
                    model_observation,
                    selection=prepared.selection,
                    mode="stream",
                    outcome="failed",
                    status=SpanStatus.ERROR,
                    error_code="runtime_error",
                )
                self._record(
                    state,
                    factory,
                    AgentEventType.MODEL_EXECUTION_COMPLETED,
                    {"outcome": "failed", "mode": "stream"},
                )
                self._fail(state, factory, self._runtime_error())
                result = state.to_result()
                break
            finally:
                if (
                    provider_iterator is not None
                    and not provider_exhausted
                    and isinstance(provider_iterator, _AsyncClosable)
                ):
                    await provider_iterator.aclose()
                if not model_stream_completed and not model_observation.span.ended:
                    self._finish_model_observation(
                        model_observation,
                        selection=prepared.selection,
                        mode="stream",
                        outcome="cancelled",
                        status=SpanStatus.UNSET,
                    )

            model_observation.span.set_attribute(
                "atlas.model.stream.event_count", stream_event_count
            )
            self._observability.record(
                "atlas.model.stream.event_count",
                stream_event_count,
                attributes={
                    "provider": prepared.selection.provider_name,
                    "model": prepared.selection.model,
                    "mode": "stream",
                    "outcome": "completed",
                },
            )
            self._finish_model_observation(
                model_observation,
                selection=prepared.selection,
                mode="stream",
                outcome="completed",
                status=SpanStatus.OK,
                response=response,
            )
            self._record(
                state,
                factory,
                AgentEventType.MODEL_EXECUTION_COMPLETED,
                {
                    "outcome": "completed",
                    "mode": "stream",
                    "finish_reason": response.finish_reason.value,
                },
            )
            state.add_model_usage(response.usage)
            result = self._enforce_usage(state, factory, policies)
            if result is None:
                guarded_response = await self._guard_model_response(
                    state=state,
                    factory=factory,
                    response=response,
                    policies=policies,
                )
                if isinstance(guarded_response, AgentResult):
                    result = guarded_response
                else:
                    response = guarded_response
            if result is None and response.finish_reason is FinishReason.TOOL_CALL:
                result = await self._process_tool_calls(
                    state=state,
                    factory=factory,
                    response=response,
                    policies=policies,
                    execution_mode=ExecutionMode.STREAM,
                )
            elif result is None:
                state.add_message(
                    ModelMessage(role=MessageRole.ASSISTANT, content=response.content)
                )
                self._transition(state, factory, ExecutionStatus.VALIDATING_OUTPUT)
                self._record(
                    state,
                    factory,
                    AgentEventType.OUTPUT_VALIDATION_STARTED,
                )
                result = await self._finish_response(
                    state,
                    factory,
                    response,
                    policies,
                )

            for event in state.events[emitted_events:]:
                yield RuntimeEventItem(event=event)
                emitted_events += 1

        if result is None:
            raise RuntimeError("O loop incremental terminou sem resultado.")
        for event in state.events[emitted_events:]:
            yield RuntimeEventItem(event=event)
            emitted_events += 1
        if isinstance(result, ExecutionSuspension):
            yield RuntimeSuspensionItem(suspension=result)
        else:
            yield RuntimeResultItem(result=result)

    async def _prepare(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        agent: AgentDefinition,
        input_data: AgentInput,
        model_selection: ModelSelectionRequest | None,
        policies: _ExecutionPolicies,
        additional_required_capabilities: frozenset[ModelCapability] = frozenset(),
    ) -> _PreparedExecution | AgentResult[object]:
        try:
            self._request_builder.validate_input(input_data)
        except RuntimeInputRejectedError as error:
            self._record(
                state,
                factory,
                AgentEventType.INPUT_VALIDATION_COMPLETED,
                {"outcome": "rejected", "code": error.code},
            )
            self._reject(state, factory, code=error.code, reason=str(error))
            return state.to_result()
        guardrail_config = agent.guardrails
        if guardrail_config is not None and guardrail_config.enabled:
            manager = self._guardrail_manager
            if manager is None:
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="guardrail_manager_required",
                        message=(
                            "O agente configurou guardrails, mas o runtime não possui "
                            "um GuardrailManager."
                        ),
                    ),
                )
                return state.to_result()
            try:
                manager.validate_config(guardrail_config)
            except GuardrailNotRegisteredError:
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="guardrail_not_registered",
                        message="Um guardrail configurado não está registrado.",
                    ),
                )
                return state.to_result()
            except GuardrailStageMismatchError:
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="guardrail_stage_mismatch",
                        message="Um guardrail foi configurado no estágio incorreto.",
                    ),
                )
                return state.to_result()
            guarded = await self._evaluate_guardrails(
                state=state,
                factory=factory,
                stage=GuardrailStage.INPUT,
                value=InputGuardrailInput(agent=agent, input_data=input_data),
                policies=policies,
            )
            if isinstance(guarded, AgentResult):
                return guarded
            if guarded.decision is GuardrailDecision.REJECT:
                self._record(
                    state,
                    factory,
                    AgentEventType.INPUT_VALIDATION_COMPLETED,
                    {"outcome": "rejected", "code": "input_guardrail_rejected"},
                )
                self._reject(
                    state,
                    factory,
                    code="input_guardrail_rejected",
                    reason="A entrada foi rejeitada pela política do agente.",
                    retain_error=True,
                )
                return state.to_result()
            if not isinstance(guarded.output, InputGuardrailInput):
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="guardrail_invalid_transformation",
                        message="O guardrail produziu uma entrada incompatível.",
                    ),
                )
                return state.to_result()
            if guarded.output.agent != agent:
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="guardrail_invalid_transformation",
                        message="O guardrail não pode alterar a definição do agente.",
                    ),
                )
                return state.to_result()
            if (
                guarded.output.input_data.attachments != input_data.attachments
                or guarded.output.input_data.metadata != input_data.metadata
            ):
                return self._invalid_guardrail_transformation(state, factory)
            input_data = guarded.output.input_data
            state.set_effective_input(input_data)
        self._record(
            state,
            factory,
            AgentEventType.INPUT_VALIDATION_COMPLETED,
            {"outcome": "accepted"},
        )

        self._transition(state, factory, ExecutionStatus.LOADING_CONTEXT)
        self._record(state, factory, AgentEventType.CONTEXT_LOADING_STARTED)
        memory_config = agent.memory
        if (
            memory_config is not None
            and memory_config.enabled
            and self._memory_manager is None
        ):
            self._fail_preparation(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_manager_required",
                    message=(
                        "O agente habilitou memória, mas o runtime não possui um "
                        "MemoryManager."
                    ),
                ),
            )
            return state.to_result()
        knowledge_config = agent.knowledge
        if (
            knowledge_config is not None
            and knowledge_config.enabled
            and self._knowledge_manager is None
        ):
            self._fail_preparation(
                state,
                factory,
                AgentErrorInfo(
                    code="knowledge_manager_required",
                    message=(
                        "O agente habilitou conhecimento, mas o runtime não possui "
                        "um KnowledgeManager."
                    ),
                ),
            )
            return state.to_result()
        messages = self._request_builder.build_initial_messages(agent, input_data)
        state.add_message(messages[0])
        try:
            memory_message = await self._load_memory_context(
                state=state,
                factory=factory,
                agent=agent,
                input_data=input_data,
                policies=policies,
            )
        except MemoryScopeResolutionError:
            self._fail_preparation(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_scope_unavailable",
                    message=(
                        "Não foi possível determinar um escopo seguro para a memória."
                    ),
                ),
            )
            return state.to_result()
        except MemoryStoreProtocolError as error:
            self._fail_preparation(
                state,
                factory,
                AgentErrorInfo(
                    code=error.code,
                    message="O armazenamento retornou memória incompatível.",
                ),
            )
            return state.to_result()
        except MemoryPolicyViolationError:
            self._fail_preparation(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_policy_violation",
                    message="A política de seleção de memória é inválida.",
                ),
            )
            return state.to_result()
        except AgentMemoryError:
            self._fail_preparation(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_read_failed",
                    message="Não foi possível recuperar a memória configurada.",
                ),
            )
            return state.to_result()
        except Exception:
            self._fail_preparation(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_read_failed",
                    message="Não foi possível recuperar a memória configurada.",
                ),
            )
            return state.to_result()
        if memory_message is not None:
            state.add_message(memory_message)
        self._record(
            state,
            factory,
            AgentEventType.CONTEXT_LOADING_COMPLETED,
            {"outcome": "completed"},
        )
        if knowledge_config is not None and knowledge_config.enabled:
            self._transition(
                state,
                factory,
                ExecutionStatus.RETRIEVING_KNOWLEDGE,
            )
            knowledge_result = await self._load_knowledge_context(
                state=state,
                factory=factory,
                agent=agent,
                input_data=input_data,
                policies=policies,
            )
            if isinstance(knowledge_result, AgentResult):
                return knowledge_result
            if knowledge_result is not None:
                state.add_message(knowledge_result)
        state.add_message(messages[-1])
        try:
            tools = tuple(self._tool_registry.get(name) for name in agent.tool_names)
        except ToolNotRegisteredError as error:
            self._fail_preparation(
                state,
                factory,
                AgentErrorInfo(
                    code="agent_tool_not_registered",
                    message="Uma ferramenta configurada no agente não está registrada.",
                    details={"tool_name": error.tool_name},
                ),
            )
            return state.to_result()
        except Exception:
            self._fail_preparation(state, factory, self._runtime_error())
            return state.to_result()
        tool_definitions = tuple(
            tool.definition.to_model_definition() for tool in tools
        )
        required_capabilities = set(additional_required_capabilities)
        if tool_definitions:
            required_capabilities.add(ModelCapability.TOOL_CALLING)
        selection_request = self._request_builder.derive_selection_request(
            input_data,
            model_selection,
            additional_required_capabilities=frozenset(required_capabilities),
        )
        selection_observation = self._start_operation_observation(
            name="atlas.model.select",
            policies=policies,
            attributes={
                "atlas.model.required_capability_count": len(
                    selection_request.required_capabilities
                )
            },
        )
        selection_succeeded = False
        try:
            selection = await self._model_registry.select(selection_request)
            state.set_model_selection(selection)
            provider = self._model_registry.get(selection.provider_name)
            selection_succeeded = True
            selection_observation.span.set_attribute(
                "atlas.model.provider", selection.provider_name
            )
            selection_observation.span.set_attribute("atlas.model.id", selection.model)
        except ModelProviderError as error:
            self._fail_preparation(
                state,
                factory,
                model_provider_error_to_agent_error(error),
            )
            return state.to_result()
        except ModelSelectionError as error:
            self._fail_preparation(
                state,
                factory,
                model_selection_error_to_agent_error(error),
            )
            return state.to_result()
        except ModelProviderRegistryError as error:
            self._fail_preparation(
                state,
                factory,
                registry_error_to_agent_error(error),
            )
            return state.to_result()
        except Exception:
            self._fail_preparation(state, factory, self._runtime_error())
            return state.to_result()
        finally:
            self._finish_operation_observation(
                selection_observation,
                outcome="completed" if selection_succeeded else "failed",
                status=SpanStatus.OK if selection_succeeded else SpanStatus.ERROR,
                error_code=None if selection_succeeded else "model_selection_failed",
            )

        self._transition(state, factory, ExecutionStatus.RUNNING)
        return _PreparedExecution(
            state=state,
            factory=factory,
            provider=provider,
            selection=selection,
            tool_definitions=tool_definitions,
        )

    async def _load_memory_context(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        agent: AgentDefinition,
        input_data: AgentInput,
        policies: _ExecutionPolicies,
    ) -> ModelMessage | None:
        """Retrieve configured memory once and render one contextual message."""
        config = agent.memory
        manager = self._memory_manager
        if config is None or not config.read_types or manager is None:
            return None
        results: list[MemorySearchResult] = []
        seen_ids: set[str] = set()
        query_text = input_data.message if input_data.message.strip() else None
        for memory_type in _MEMORY_TYPE_ORDER:
            if memory_type not in config.read_types:
                continue
            self._record(
                state,
                factory,
                AgentEventType.MEMORY_RETRIEVAL_STARTED,
                {"memory_type": memory_type.value},
            )
            memory_observation = self._start_operation_observation(
                name="atlas.memory.retrieve",
                policies=policies,
                kind=SpanKind.CLIENT,
                attributes={"atlas.memory.type": memory_type.value},
            )
            retrieved: tuple[MemorySearchResult, ...] = ()
            retrieval_succeeded = False
            try:
                scope = self._memory_scope_policy.scope_for(
                    memory_type=memory_type,
                    agent=agent,
                    context=state.context,
                )
                retrieved = await manager.retrieve(
                    query=MemoryQuery(
                        scope=scope,
                        memory_type=memory_type,
                        text=query_text,
                        limit=config.max_records_per_type,
                    )
                )
                if any(result.record.memory_id in seen_ids for result in retrieved):
                    raise MemoryStoreProtocolError(
                        "O armazenamento repetiu uma memória entre consultas."
                    )
                seen_ids.update(result.record.memory_id for result in retrieved)
                retrieval_succeeded = True
            except Exception:
                self._record(
                    state,
                    factory,
                    AgentEventType.MEMORY_RETRIEVAL_COMPLETED,
                    {"memory_type": memory_type.value, "outcome": "failed"},
                )
                raise
            finally:
                memory_observation.span.set_attribute(
                    "atlas.memory.result_count", len(retrieved)
                )
                self._finish_operation_observation(
                    memory_observation,
                    outcome="completed" if retrieval_succeeded else "failed",
                    status=(SpanStatus.OK if retrieval_succeeded else SpanStatus.ERROR),
                    duration_metric="atlas.memory.retrieval.duration",
                    metric_attributes={
                        "memory_type": memory_type.value,
                        "outcome": ("completed" if retrieval_succeeded else "failed"),
                    },
                    error_code=(
                        None if retrieval_succeeded else "memory_retrieval_failed"
                    ),
                )
            self._record(
                state,
                factory,
                AgentEventType.MEMORY_RETRIEVAL_COMPLETED,
                {
                    "memory_type": memory_type.value,
                    "outcome": "completed",
                    "records_count": len(retrieved),
                },
            )
            results.extend(retrieved)
        if not results:
            return None
        selected = manager.select(
            results=tuple(results),
            max_records=len(results),
            max_characters=config.max_characters,
        )
        return self._memory_context_renderer.render(selected)

    async def _load_knowledge_context(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        agent: AgentDefinition,
        input_data: AgentInput,
        policies: _ExecutionPolicies,
    ) -> ModelMessage | AgentResult[object] | None:
        """Retrieve external knowledge once and preserve its citation mapping."""
        config = agent.knowledge
        manager = self._knowledge_manager
        if config is None or not config.enabled or manager is None:
            raise KnowledgeContextError(
                "A recuperação de conhecimento não foi configurada corretamente."
            )
        self._record(
            state,
            factory,
            AgentEventType.KNOWLEDGE_RETRIEVAL_STARTED,
            {
                "sources_count": len(config.source_ids),
                "query_length": len(input_data.message),
            },
        )
        knowledge_observation = self._start_operation_observation(
            name="atlas.knowledge.retrieve",
            policies=policies,
            kind=SpanKind.CLIENT,
            attributes={"atlas.knowledge.source_count": len(config.source_ids)},
        )
        knowledge_context = None
        retrieval_succeeded = False
        try:
            query = self._knowledge_query_builder.build(
                agent=agent,
                input_data=input_data,
                context=state.context,
            )
            self._validate_knowledge_query(query, config.source_ids, config.max_results)
            knowledge_context = await manager.retrieve(
                query=query,
                context=KnowledgeRetrievalContext(
                    execution_id=state.execution_id,
                    agent_id=agent.agent_id,
                    identity=state.context.identity,
                ),
                max_results=config.max_results,
                max_characters=config.max_characters,
            )
            state.set_knowledge_context(knowledge_context)
            knowledge_message = self._knowledge_context_renderer.render(
                knowledge_context
            )
            retrieval_succeeded = True
        except KnowledgeSourceNotFoundError:
            return self._fail_knowledge_retrieval(
                state,
                factory,
                code="knowledge_source_not_found",
                message="Uma fonte de conhecimento configurada não está disponível.",
            )
        except KnowledgeProtocolError:
            return self._fail_knowledge_retrieval(
                state,
                factory,
                code="knowledge_protocol_violation",
                message="O retriever retornou conhecimento incompatível.",
            )
        except (KnowledgeContextError, KnowledgePolicyError):
            return self._fail_knowledge_retrieval(
                state,
                factory,
                code="knowledge_context_error",
                message="Não foi possível montar o contexto de conhecimento.",
            )
        except (KnowledgeRetrievalError, KnowledgeError):
            return self._fail_knowledge_retrieval(
                state,
                factory,
                code="knowledge_retrieval_failed",
                message="Não foi possível recuperar o conhecimento configurado.",
            )
        except Exception:
            return self._fail_knowledge_retrieval(
                state,
                factory,
                code="knowledge_context_error",
                message="Não foi possível montar o contexto de conhecimento.",
            )
        finally:
            if knowledge_context is not None:
                knowledge_observation.span.set_attribute(
                    "atlas.knowledge.result_count", len(knowledge_context.results)
                )
                knowledge_observation.span.set_attribute(
                    "atlas.knowledge.selected_count", len(knowledge_context.results)
                )
            self._finish_operation_observation(
                knowledge_observation,
                outcome="completed" if retrieval_succeeded else "failed",
                status=SpanStatus.OK if retrieval_succeeded else SpanStatus.ERROR,
                duration_metric="atlas.knowledge.retrieval.duration",
                metric_attributes={
                    "outcome": "completed" if retrieval_succeeded else "failed"
                },
                error_code=(
                    None if retrieval_succeeded else "knowledge_retrieval_failed"
                ),
            )
        self._record(
            state,
            factory,
            AgentEventType.KNOWLEDGE_RETRIEVAL_COMPLETED,
            {
                "outcome": "completed",
                "selected_count": len(knowledge_context.results),
            },
        )
        return knowledge_message

    @staticmethod
    def _validate_knowledge_query(
        query: object,
        allowed_source_ids: tuple[str, ...],
        max_results: int,
    ) -> None:
        if not isinstance(query, KnowledgeQuery):
            raise KnowledgeContextError(
                "O query builder deve retornar uma KnowledgeQuery."
            )
        if not query.source_ids:
            raise KnowledgeContextError(
                "A consulta não pode ampliar o acesso para todas as fontes."
            )
        if not set(query.source_ids).issubset(allowed_source_ids):
            raise KnowledgeContextError(
                "A consulta contém fonte fora da allowlist do agente."
            )
        if query.limit > max_results:
            raise KnowledgeContextError(
                "A consulta excede o limite de resultados do agente."
            )

    def _fail_knowledge_retrieval(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        *,
        code: str,
        message: str,
    ) -> AgentResult[object]:
        self._record(
            state,
            factory,
            AgentEventType.KNOWLEDGE_RETRIEVAL_COMPLETED,
            {"outcome": "failed", "code": code},
        )
        self._fail(state, factory, AgentErrorInfo(code=code, message=message))
        return state.to_result()

    async def _guard_model_response(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        response: ModelResponse,
        policies: _ExecutionPolicies,
    ) -> ModelResponse | AgentResult[object]:
        guarded = await self._evaluate_guardrails(
            state=state,
            factory=factory,
            stage=GuardrailStage.MODEL_OUTPUT,
            value=ModelOutputGuardrailInput(
                response=response,
                turn_number=state.turn_count,
            ),
            policies=policies,
        )
        if isinstance(guarded, AgentResult):
            return guarded
        if guarded.decision is GuardrailDecision.REJECT:
            self._reject(
                state,
                factory,
                code="model_output_guardrail_rejected",
                reason="A saída do modelo foi rejeitada pela política do agente.",
                retain_error=True,
            )
            return state.to_result()
        output = guarded.output
        if not isinstance(output, ModelOutputGuardrailInput):
            return self._invalid_guardrail_transformation(state, factory)
        transformed = output.response
        if (
            transformed.response_id != response.response_id
            or transformed.model != response.model
            or transformed.tool_calls != response.tool_calls
            or transformed.finish_reason is not response.finish_reason
            or transformed.usage != response.usage
            or transformed.metadata != response.metadata
        ):
            return self._invalid_guardrail_transformation(state, factory)
        return transformed

    def _invalid_guardrail_transformation(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
    ) -> AgentResult[object]:
        self._fail(
            state,
            factory,
            AgentErrorInfo(
                code="guardrail_invalid_transformation",
                message="O guardrail produziu uma transformação não permitida.",
            ),
        )
        return state.to_result()

    async def _evaluate_guardrails[T](
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        stage: GuardrailStage,
        value: T,
        policies: _ExecutionPolicies,
    ) -> GuardrailPipelineResult[T] | AgentResult[object]:
        """Evaluate one configured stage and record only content-free facts."""
        config = state.agent.guardrails
        if config is None or not config.ids_for(stage):
            return GuardrailPipelineResult(
                decision=GuardrailDecision.ALLOW,
                output=value,
            )
        manager = self._guardrail_manager
        if manager is None:
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="guardrail_manager_required",
                    message="A avaliação exige um GuardrailManager configurado.",
                ),
            )
            return state.to_result()
        self._record(
            state,
            factory,
            AgentEventType.GUARDRAIL_EVALUATION_STARTED,
            {"stage": stage.value, "guardrails_count": len(config.ids_for(stage))},
        )
        observation = self._start_operation_observation(
            name="atlas.guardrail.evaluate",
            policies=policies,
            attributes={
                "atlas.guardrail.stage": stage.value,
                "atlas.guardrail.count": len(config.ids_for(stage)),
            },
        )
        result: GuardrailPipelineResult[T] | None = None
        try:
            result = await manager.evaluate(
                config=config,
                stage=stage,
                value=value,
                context=self._guardrail_context(state, stage),
            )
        except asyncio.CancelledError:
            raise
        except GuardrailProtocolError:
            self._fail_guardrail_evaluation(
                state,
                factory,
                stage=stage,
                code="guardrail_protocol_violation",
                message="Um guardrail retornou um resultado incompatível.",
            )
            return state.to_result()
        except (GuardrailEvaluationError, GuardrailError):
            self._fail_guardrail_evaluation(
                state,
                factory,
                stage=stage,
                code="guardrail_evaluation_failed",
                message="Não foi possível avaliar a política configurada.",
            )
            return state.to_result()
        except Exception:
            self._fail_guardrail_evaluation(
                state,
                factory,
                stage=stage,
                code="guardrail_evaluation_failed",
                message="Não foi possível avaliar a política configurada.",
            )
            return state.to_result()
        finally:
            decision = "error" if result is None else result.decision.value
            observation.span.set_attribute("atlas.guardrail.decision", decision)
            self._observability.increment(
                "atlas.guardrail.evaluations",
                attributes={"stage": stage.value, "decision": decision},
            )
            self._finish_operation_observation(
                observation,
                outcome="failed" if result is None else "completed",
                status=SpanStatus.ERROR if result is None else SpanStatus.OK,
                duration_metric="atlas.guardrail.duration",
                metric_attributes={"stage": stage.value, "decision": decision},
                error_code=("guardrail_evaluation_failed" if result is None else None),
            )
        for item in result.guardrail_results:
            state.record_guardrail(
                GuardrailRecord(
                    stage=stage,
                    guardrail_id=item.guardrail_id,
                    decision=item.decision,
                    enforcement=item.enforcement,
                    violation_codes=tuple(
                        violation.code for violation in item.violations
                    ),
                    transformation_kinds=tuple(
                        transformation.kind for transformation in item.transformations
                    ),
                    timestamp=state.updated_at,
                )
            )
            event_data: dict[str, object] = {
                "stage": stage.value,
                "guardrail_id": item.guardrail_id,
                "decision": item.decision.value,
                "violation_codes": [violation.code for violation in item.violations],
                "transformation_kinds": [
                    transformation.kind for transformation in item.transformations
                ],
            }
            if item.decision is GuardrailDecision.TRANSFORM:
                self._record(
                    state,
                    factory,
                    AgentEventType.GUARDRAIL_TRANSFORMED,
                    event_data,
                )
            elif item.decision is GuardrailDecision.REJECT:
                self._record(
                    state,
                    factory,
                    AgentEventType.GUARDRAIL_REJECTED,
                    event_data,
                )
        self._record(
            state,
            factory,
            AgentEventType.GUARDRAIL_EVALUATION_COMPLETED,
            {"stage": stage.value, "decision": result.decision.value},
        )
        return result

    def _fail_guardrail_evaluation(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        *,
        stage: GuardrailStage,
        code: str,
        message: str,
    ) -> None:
        self._record(
            state,
            factory,
            AgentEventType.GUARDRAIL_EVALUATION_COMPLETED,
            {"stage": stage.value, "outcome": "failed", "code": code},
        )
        self._fail(state, factory, AgentErrorInfo(code=code, message=message))

    @staticmethod
    def _guardrail_context(
        state: ExecutionState,
        stage: GuardrailStage,
    ) -> GuardrailContext:
        return GuardrailContext(
            execution_id=state.execution_id,
            agent_id=state.agent.agent_id,
            identity=state.context.identity,
            stage=stage,
        )

    @staticmethod
    def _model_context(
        state: ExecutionState,
        agent: AgentDefinition,
    ) -> ModelExecutionContext:
        return ModelExecutionContext(
            execution_id=state.execution_id,
            agent_id=agent.agent_id,
            request_id=str(uuid4()),
        )

    async def _process_tool_calls(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        response: ModelResponse,
        policies: _ExecutionPolicies,
        execution_mode: ExecutionMode,
    ) -> RuntimeOutcome | None:
        """Process one model-ordered tool batch and restore running state."""
        if not state.agent.tool_names:
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="unexpected_tool_call",
                    message=(
                        "O modelo solicitou uma ferramenta não oferecida pelo agente."
                    ),
                ),
            )
            return state.to_result()

        state.add_message(
            ModelMessage(
                role=MessageRole.ASSISTANT,
                content=response.content,
                tool_calls=response.tool_calls,
            )
        )
        for call in response.tool_calls:
            self._record(
                state,
                factory,
                AgentEventType.TOOL_REQUESTED,
                {
                    "tool_call_id": call.tool_call_id,
                    "tool_name": call.name,
                    "argument_keys": sorted(call.arguments),
                },
            )
        self._transition(state, factory, ExecutionStatus.WAITING_FOR_TOOL)
        return await self._process_tool_batch(
            state=state,
            factory=factory,
            calls=response.tool_calls,
            policies=policies,
            execution_mode=execution_mode,
        )

    async def _process_tool_batch(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        calls: tuple[ToolCall, ...],
        policies: _ExecutionPolicies,
        execution_mode: ExecutionMode,
        approved_call_id: str | None = None,
    ) -> RuntimeOutcome | None:
        """Process calls sequentially, suspending before each required approval."""
        for index, call in enumerate(calls):
            original_call = call
            previous = state.get_tool_call_record(call.tool_call_id)
            if previous is not None:
                if (
                    previous.tool_name != call.name
                    or previous.arguments != call.arguments
                ):
                    self._fail(
                        state,
                        factory,
                        AgentErrorInfo(
                            code="tool_call_id_conflict",
                            message=(
                                "O modelo reutilizou um tool_call_id com dados "
                                "diferentes."
                            ),
                            details={"tool_call_id": call.tool_call_id},
                        ),
                    )
                    return state.to_result()
                self._enter_tool_processing(state, factory)
                self._record_tool_completion(
                    state,
                    factory,
                    previous.model_facing_result,
                    deduplicated=True,
                )
                state.add_message(
                    self._tool_result_mapper.map(previous.model_facing_result)
                )
                continue

            registered = self._tool_registry.try_get(call.name)
            if registered is not None and call.name not in state.agent.tool_names:
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="tool_not_available_for_agent",
                        message=(
                            "A ferramenta solicitada não está disponível ao agente."
                        ),
                        details={"tool_name": call.name},
                    ),
                )
                return state.to_result()

            request = ToolExecutionRequest(
                tool_call_id=call.tool_call_id,
                tool_name=call.name,
                arguments=call.arguments,
            )
            context = ToolExecutionContext(
                execution_id=state.execution_id,
                agent_id=state.agent.agent_id,
                tool_call_id=call.tool_call_id,
                identity=state.context.identity,
            )
            try:
                prepared = self._tool_executor.prepare(request, context)
            except ToolExecutionInvariantError:
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="tool_execution_invariant",
                        message=(
                            "O executor de ferramentas violou uma invariante interna."
                        ),
                    ),
                )
                return state.to_result()
            except Exception:
                self._fail(state, factory, self._runtime_error())
                return state.to_result()
            if isinstance(prepared, ToolExecutionResult):
                self._enter_tool_processing(state, factory)
                self._record_processed_tool_call(
                    state,
                    call,
                    call,
                    prepared,
                    prepared,
                )
                self._record_tool_completion(state, factory, prepared)
                state.add_message(self._tool_result_mapper.map(prepared))
                continue
            if registered is None:
                self._fail(state, factory, self._runtime_error())
                return state.to_result()

            already_guarded = approved_call_id == call.tool_call_id
            if not already_guarded:
                guarded_call = await self._evaluate_guardrails(
                    state=state,
                    factory=factory,
                    stage=GuardrailStage.TOOL_CALL,
                    value=ToolCallGuardrailInput(
                        tool_call=call,
                        tool_definition=registered.definition,
                    ),
                    policies=policies,
                )
                if isinstance(guarded_call, AgentResult):
                    return guarded_call
                if guarded_call.decision is GuardrailDecision.REJECT:
                    if guarded_call.enforcement is GuardrailEnforcement.EXECUTION:
                        self._reject(
                            state,
                            factory,
                            code="tool_call_guardrail_rejected",
                            reason=(
                                "A chamada de ferramenta foi rejeitada pela política."
                            ),
                            retain_error=True,
                        )
                        return state.to_result()
                    denied = self._guardrail_tool_denial(
                        call,
                        code="tool_call_guardrail_rejected",
                    )
                    self._enter_tool_processing(state, factory)
                    self._record_processed_tool_call(
                        state,
                        original_call,
                        call,
                        denied,
                        denied,
                    )
                    self._record_tool_completion(state, factory, denied)
                    state.add_message(self._tool_result_mapper.map(denied))
                    continue
                guarded_value = guarded_call.output
                if not isinstance(guarded_value, ToolCallGuardrailInput):
                    return self._invalid_guardrail_transformation(state, factory)
                effective_call = guarded_value.tool_call
                if (
                    effective_call.tool_call_id != call.tool_call_id
                    or effective_call.name != call.name
                    or guarded_value.tool_definition != registered.definition
                ):
                    return self._invalid_guardrail_transformation(state, factory)
                call = effective_call
                request = ToolExecutionRequest(
                    tool_call_id=call.tool_call_id,
                    tool_name=call.name,
                    arguments=call.arguments,
                )
                context = ToolExecutionContext(
                    execution_id=state.execution_id,
                    agent_id=state.agent.agent_id,
                    tool_call_id=call.tool_call_id,
                    identity=state.context.identity,
                )
                prepared = self._tool_executor.prepare(request, context)
                if isinstance(prepared, ToolExecutionResult):
                    return self._invalid_guardrail_transformation(state, factory)

            if already_guarded:
                approved_call_id = None
            else:
                requirement = self._approval_requirement(
                    tool=registered.definition,
                    request=request,
                    state=state,
                    policies=policies,
                )
                if isinstance(requirement, ApprovalRequired):
                    return await self._suspend_for_approval(
                        state=state,
                        factory=factory,
                        call=call,
                        pending_calls=(call, *calls[index + 1 :]),
                        requirement=requirement,
                        policies=policies,
                        execution_mode=execution_mode,
                    )

            self._enter_tool_processing(state, factory)
            violation = self._limit_checker.check_tool_call_allowed(
                limits=policies.limits,
                current_tool_call_count=state.tool_call_count,
            )
            if violation is not None:
                return self._exceed_limit(state, factory, violation)
            state.increment_tool_calls()
            self._record(
                state,
                factory,
                AgentEventType.TOOL_EXECUTION_STARTED,
                {"tool_call_id": call.tool_call_id, "tool_name": call.name},
            )
            tool_observation = self._start_operation_observation(
                name="atlas.tool.execute",
                policies=policies,
                attributes={
                    "atlas.tool.name": call.name,
                    "atlas.tool.call_id": call.tool_call_id,
                    "atlas.tool.idempotency": registered.definition.idempotency.value,
                },
            )
            result: ToolExecutionResult | None = None
            tool_outcome = "failed"
            tool_status = SpanStatus.ERROR
            tool_error_code: str | None = None
            try:
                result = await policies.deadline.wait_for(
                    partial(self._tool_executor.execute_prepared, prepared)
                )
                tool_outcome = result.status.value
                tool_status = (
                    SpanStatus.ERROR
                    if result.status is ToolExecutionStatus.FAILED
                    else SpanStatus.OK
                )
                tool_error_code = None if result.error is None else result.error.code
            except ExecutionDeadlineExpiredError:
                tool_outcome = "timed_out"
                tool_error_code = "execution_timed_out"
                raise
            except asyncio.CancelledError:
                tool_outcome = "cancelled"
                tool_status = SpanStatus.UNSET
                raise
            except ToolExecutionInvariantError:
                tool_error_code = "tool_execution_invariant"
                self._fail(
                    state,
                    factory,
                    AgentErrorInfo(
                        code="tool_execution_invariant",
                        message=(
                            "O executor de ferramentas violou uma invariante interna."
                        ),
                    ),
                )
                return state.to_result()
            except Exception:
                tool_error_code = "runtime_error"
                self._fail(state, factory, self._runtime_error())
                return state.to_result()
            finally:
                tool_observation.span.set_attribute("atlas.tool.status", tool_outcome)
                self._observability.increment(
                    "atlas.tool.executions",
                    attributes={
                        "tool_name": call.name,
                        "status": tool_outcome,
                    },
                )
                self._finish_operation_observation(
                    tool_observation,
                    outcome=tool_outcome,
                    status=tool_status,
                    duration_metric="atlas.tool.duration",
                    metric_attributes={
                        "tool_name": call.name,
                        "status": tool_outcome,
                    },
                    error_code=tool_error_code,
                )
            guarded_result = await self._guard_tool_result(
                state=state,
                factory=factory,
                call=call,
                result=result,
                policies=policies,
            )
            if isinstance(guarded_result, AgentResult):
                return guarded_result
            self._record_processed_tool_call(
                state,
                original_call,
                call,
                result,
                guarded_result,
            )
            self._record_tool_completion(state, factory, guarded_result)
            state.add_message(self._tool_result_mapper.map(guarded_result))

        if state.status is not ExecutionStatus.RUNNING:
            self._transition(state, factory, ExecutionStatus.RUNNING)
        return None

    async def _guard_tool_result(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        call: ToolCall,
        result: ToolExecutionResult,
        policies: _ExecutionPolicies,
    ) -> ToolExecutionResult | AgentResult[object]:
        guarded = await self._evaluate_guardrails(
            state=state,
            factory=factory,
            stage=GuardrailStage.TOOL_RESULT,
            value=ToolResultGuardrailInput(tool_call=call, tool_result=result),
            policies=policies,
        )
        if isinstance(guarded, AgentResult):
            return guarded
        if guarded.decision is GuardrailDecision.REJECT:
            if guarded.enforcement is GuardrailEnforcement.EXECUTION:
                self._reject(
                    state,
                    factory,
                    code="tool_result_guardrail_rejected",
                    reason="O resultado da ferramenta foi rejeitado pela política.",
                    retain_error=True,
                )
                return state.to_result()
            return self._guardrail_tool_denial(
                call,
                code="tool_result_guardrail_rejected",
            )
        output = guarded.output
        if not isinstance(output, ToolResultGuardrailInput):
            return self._invalid_guardrail_transformation(state, factory)
        if output.tool_call != call or (
            output.tool_result.tool_call_id != result.tool_call_id
            or output.tool_result.tool_name != result.tool_name
        ):
            return self._invalid_guardrail_transformation(state, factory)
        return output.tool_result

    def _guardrail_tool_denial(
        self,
        call: ToolCall,
        *,
        code: str,
    ) -> ToolExecutionResult:
        timestamp = self._clock()
        return ToolExecutionResult(
            tool_call_id=call.tool_call_id,
            tool_name=call.name,
            status=ToolExecutionStatus.DENIED,
            error=ToolExecutionError(
                code=code,
                message="A política do agente bloqueou esta operação.",
            ),
            started_at=timestamp,
            completed_at=timestamp,
        )

    def _approval_requirement(
        self,
        *,
        tool: ToolDefinition,
        request: ToolExecutionRequest,
        state: ExecutionState,
        policies: _ExecutionPolicies,
    ) -> ApprovalRequirement:
        observation = self._start_operation_observation(
            name="atlas.approval.evaluate",
            policies=policies,
            attributes={"atlas.tool.name": tool.name},
        )
        try:
            if tool.approval_mode is ToolApprovalMode.NOT_REQUIRED:
                requirement: ApprovalRequirement = ApprovalNotRequired()
            elif tool.approval_mode is ToolApprovalMode.REQUIRED:
                requirement = ApprovalRequired(
                    reason="A ferramenta exige aprovação humana antes da execução.",
                    summary=f"Autorizar a execução da ferramenta '{tool.name}'?",
                )
            else:
                requirement = self._approval_policy.evaluate_tool(
                    tool=tool,
                    request=request,
                    context=ApprovalContext(
                        execution_id=state.execution_id,
                        agent_id=state.agent.agent_id,
                        tool_call_id=request.tool_call_id,
                        identity=state.context.identity,
                    ),
                )
        except Exception:
            self._finish_operation_observation(
                observation,
                outcome="failed",
                status=SpanStatus.ERROR,
                error_code="approval_evaluation_failed",
            )
            raise
        decision = (
            "required" if isinstance(requirement, ApprovalRequired) else "not_required"
        )
        observation.span.set_attribute("atlas.approval.decision", decision)
        self._finish_operation_observation(
            observation,
            outcome="completed",
            status=SpanStatus.OK,
        )
        return requirement

    async def _suspend_for_approval(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        call: ToolCall,
        pending_calls: tuple[ToolCall, ...],
        requirement: ApprovalRequired,
        policies: _ExecutionPolicies,
        execution_mode: ExecutionMode,
    ) -> RuntimeOutcome:
        store = self._checkpoint_store
        if store is None:
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="approval_checkpoint_store_required",
                    message=(
                        "A aprovação exige um armazenamento de checkpoint configurado."
                    ),
                ),
            )
            return state.to_result()
        if state.status is ExecutionStatus.EXECUTING_TOOL:
            self._transition(state, factory, ExecutionStatus.WAITING_FOR_TOOL)
        requested_at = self._clock()
        request = ApprovalRequest(
            approval_request_id=str(uuid4()),
            execution_id=state.execution_id,
            agent_id=state.agent.agent_id,
            summary=requirement.summary,
            reason=requirement.reason,
            requested_at=requested_at,
            expires_at=requirement.expires_at,
            subject=ToolApprovalSubject(
                tool_call_id=call.tool_call_id,
                tool_name=call.name,
                argument_keys=tuple(sorted(call.arguments)),
            ),
            metadata=requirement.metadata,
        )
        state.set_pending_approval(request)
        self._record(
            state,
            factory,
            AgentEventType.APPROVAL_REQUESTED,
            {
                "approval_request_id": request.approval_request_id,
                "tool_call_id": call.tool_call_id,
                "tool_name": call.name,
                "reason": request.reason,
            },
        )
        self._transition(state, factory, ExecutionStatus.WAITING_FOR_APPROVAL)
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_SUSPENDED,
            {"approval_request_id": request.approval_request_id},
        )
        token = ResumeToken.create()
        self._observability.increment(
            "atlas.approval.requests",
            attributes={"decision": "required"},
        )
        checkpoint_observation = self._start_operation_observation(
            name="atlas.checkpoint.save",
            policies=policies,
            kind=SpanKind.CLIENT,
            attributes={
                "atlas.checkpoint.version": CURRENT_CHECKPOINT_VERSION,
                "atlas.execution.mode": execution_mode.value,
                "atlas.operation": "save",
            },
        )
        checkpoint_outcome = "completed"
        checkpoint_status = SpanStatus.OK
        checkpoint_error_code: str | None = None
        try:
            checkpoint = self._state_restorer.build_checkpoint(
                state=state,
                execution_mode=execution_mode,
                pending_tool_calls=pending_calls,
                limits=policies.limits,
                budget=policies.budget,
                deadline=policies.deadline,
                trace_context=policies.observation.span.context,
            )
            await policies.deadline.wait_for(
                lambda: store.save(resume_token=token, checkpoint=checkpoint)
            )
        except ExecutionDeadlineExpiredError:
            checkpoint_outcome = "timed_out"
            checkpoint_status = SpanStatus.ERROR
            checkpoint_error_code = "execution_timed_out"
            raise
        except asyncio.CancelledError:
            checkpoint_outcome = "cancelled"
            checkpoint_status = SpanStatus.UNSET
            raise
        except Exception:
            checkpoint_outcome = "failed"
            checkpoint_status = SpanStatus.ERROR
            checkpoint_error_code = "checkpoint_save_failed"
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="checkpoint_save_failed",
                    message="Não foi possível salvar o checkpoint da execução.",
                ),
            )
            return state.to_result()
        finally:
            self._observability.increment(
                "atlas.checkpoint.operations",
                attributes={
                    "operation": "save",
                    "outcome": checkpoint_outcome,
                },
            )
            self._finish_operation_observation(
                checkpoint_observation,
                outcome=checkpoint_outcome,
                status=checkpoint_status,
                error_code=checkpoint_error_code,
            )
        return ExecutionSuspension(
            execution_id=state.execution_id,
            approval_request=request,
            resume_token=token,
            checkpoint_version=CURRENT_CHECKPOINT_VERSION,
            created_at=requested_at,
        )

    def _enter_tool_processing(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
    ) -> None:
        if state.status in {
            ExecutionStatus.WAITING_FOR_TOOL,
            ExecutionStatus.WAITING_FOR_APPROVAL,
        }:
            self._transition(state, factory, ExecutionStatus.EXECUTING_TOOL)

    @staticmethod
    def _record_processed_tool_call(
        state: ExecutionState,
        original_call: ToolCall,
        effective_call: ToolCall,
        result: ToolExecutionResult,
        effective_result: ToolExecutionResult,
    ) -> None:
        state.record_tool_call(
            ToolCallRecord(
                tool_call_id=original_call.tool_call_id,
                tool_name=original_call.name,
                arguments=original_call.arguments,
                result=result,
                effective_arguments=effective_call.arguments,
                effective_result=effective_result,
            )
        )

    def _record_tool_completion(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        result: ToolExecutionResult,
        *,
        deduplicated: bool = False,
    ) -> None:
        data: dict[str, object] = {
            "tool_call_id": result.tool_call_id,
            "tool_name": result.tool_name,
            "status": result.status.value,
        }
        if result.error is not None:
            data["error_code"] = result.error.code
        if deduplicated:
            data["deduplicated"] = True
        self._record(
            state,
            factory,
            AgentEventType.TOOL_EXECUTION_COMPLETED,
            data,
        )

    def _start_execution(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
    ) -> None:
        self._record(state, factory, AgentEventType.EXECUTION_CREATED)
        validating_transition = state.transition_to(ExecutionStatus.VALIDATING_INPUT)
        self._record(state, factory, AgentEventType.EXECUTION_STARTED)
        state.record_event(factory.from_transition(validating_transition))
        self._record(state, factory, AgentEventType.INPUT_VALIDATION_STARTED)

    async def _finish_response(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        response: ModelResponse,
        policies: _ExecutionPolicies,
    ) -> AgentResult[object]:
        if response.finish_reason in {FinishReason.STOP, FinishReason.LENGTH}:
            output = "".join(
                part.text for part in response.content if isinstance(part, TextContent)
            )
            if not output:
                return self._failed_output(
                    state,
                    factory,
                    code="model_empty_text_response",
                    message="O modelo não retornou conteúdo textual utilizável.",
                )
            guarded_output = await self._evaluate_guardrails(
                state=state,
                factory=factory,
                stage=GuardrailStage.FINAL_OUTPUT,
                value=FinalOutputGuardrailInput(output=output),
                policies=policies,
            )
            if isinstance(guarded_output, AgentResult):
                return guarded_output
            if guarded_output.decision is GuardrailDecision.REJECT:
                self._record(
                    state,
                    factory,
                    AgentEventType.OUTPUT_VALIDATION_COMPLETED,
                    {
                        "outcome": "rejected",
                        "code": "final_output_guardrail_rejected",
                    },
                )
                self._reject(
                    state,
                    factory,
                    code="final_output_guardrail_rejected",
                    reason="A saída final foi rejeitada pela política do agente.",
                    retain_error=True,
                )
                return state.to_result()
            guarded_value = guarded_output.output
            if not isinstance(guarded_value, FinalOutputGuardrailInput):
                return self._invalid_guardrail_transformation(state, factory)
            if guarded_value.citations:
                return self._invalid_guardrail_transformation(state, factory)
            effective_output = guarded_value.output
            self._record(
                state,
                factory,
                AgentEventType.OUTPUT_VALIDATION_COMPLETED,
                {
                    "outcome": "accepted",
                    "partial": response.finish_reason is FinishReason.LENGTH,
                },
            )
            write_failure = await self._write_memories(
                state=state,
                factory=factory,
                output=effective_output,
                policies=policies,
            )
            if write_failure is not None:
                return write_failure
            state.complete(effective_output)
            state.record_event(factory.from_transition(state.transitions[-1]))
            self._record(state, factory, AgentEventType.EXECUTION_COMPLETED)
            return state.to_result()

        if response.finish_reason is FinishReason.CONTENT_FILTER:
            self._record(
                state,
                factory,
                AgentEventType.OUTPUT_VALIDATION_COMPLETED,
                {"outcome": "rejected", "code": "model_content_filtered"},
            )
            self._reject(
                state,
                factory,
                code="model_content_filtered",
                reason="O provider bloqueou o conteúdo da resposta.",
            )
            return state.to_result()

        if response.finish_reason is FinishReason.CANCELLED:
            self._record(
                state,
                factory,
                AgentEventType.OUTPUT_VALIDATION_COMPLETED,
                {"outcome": "cancelled", "code": "model_response_cancelled"},
            )
            self._cancel(
                state,
                factory,
                reason="O provider retornou uma resposta cancelada.",
            )
            return state.to_result()

        error_facts = {
            FinishReason.TOOL_CALL: (
                "unsupported_tool_call",
                "A resposta de ferramenta não pôde ser processada pelo runtime.",
            ),
            FinishReason.ERROR: (
                "model_error_finish_reason",
                "O provider encerrou a resposta com erro.",
            ),
            FinishReason.UNKNOWN: (
                "model_unknown_finish_reason",
                "O provider retornou um motivo de término desconhecido.",
            ),
        }
        code, message = error_facts[response.finish_reason]
        return self._failed_output(state, factory, code=code, message=message)

    async def _write_memories(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        output: object,
        policies: _ExecutionPolicies,
    ) -> AgentResult[object] | None:
        """Select and write configured memories before successful completion."""
        config = state.agent.memory
        if config is None or not config.write_types:
            return None
        manager = self._memory_manager
        if manager is None:
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_manager_required",
                    message="A escrita de memória exige um MemoryManager.",
                ),
            )
            return state.to_result()
        try:
            candidates = self._memory_write_policy.select(
                agent=state.agent,
                snapshot=state.snapshot(),
                output=output,
            )
            if not isinstance(candidates, tuple) or any(
                not isinstance(candidate, MemoryCandidate) for candidate in candidates
            ):
                raise MemoryPolicyViolationError(
                    "A política deve retornar uma tupla de candidatas de memória."
                )
            requests: list[MemoryWriteRequest] = []
            for candidate in candidates:
                if candidate.memory_type not in config.write_types:
                    raise MemoryPolicyViolationError(
                        "A política selecionou um tipo não permitido pelo agente."
                    )
                scope = self._memory_scope_policy.scope_for(
                    memory_type=candidate.memory_type,
                    agent=state.agent,
                    context=state.context,
                )
                requests.append(
                    MemoryWriteRequest(
                        memory_type=candidate.memory_type,
                        scope=scope,
                        content=candidate.content,
                        expires_at=candidate.expires_at,
                        metadata=candidate.metadata,
                    )
                )
        except MemoryScopeResolutionError:
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_scope_unavailable",
                    message=(
                        "Não foi possível determinar um escopo seguro para a memória."
                    ),
                ),
            )
            return state.to_result()
        except Exception:
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_policy_violation",
                    message="A política de escrita de memória é inválida.",
                ),
            )
            return state.to_result()
        if not requests:
            return None

        self._transition(state, factory, ExecutionStatus.UPDATING_MEMORY)
        self._record(
            state,
            factory,
            AgentEventType.MEMORY_UPDATE_STARTED,
            {"records_count": len(requests)},
        )
        written = 0
        try:
            for request in requests:
                memory_observation = self._start_operation_observation(
                    name="atlas.memory.write",
                    policies=policies,
                    kind=SpanKind.CLIENT,
                    attributes={"atlas.memory.type": request.memory_type.value},
                )
                write_outcome = "completed"
                write_status = SpanStatus.OK
                write_error_code: str | None = None
                try:
                    await policies.deadline.wait_for(partial(manager.remember, request))
                except ExecutionDeadlineExpiredError:
                    write_outcome = "timed_out"
                    write_status = SpanStatus.ERROR
                    write_error_code = "execution_timed_out"
                    raise
                except asyncio.CancelledError:
                    write_outcome = "cancelled"
                    write_status = SpanStatus.UNSET
                    raise
                except Exception:
                    write_outcome = "failed"
                    write_status = SpanStatus.ERROR
                    write_error_code = "memory_write_failed"
                    raise
                finally:
                    self._observability.increment(
                        "atlas.memory.writes",
                        attributes={
                            "memory_type": request.memory_type.value,
                            "outcome": write_outcome,
                        },
                    )
                    self._finish_operation_observation(
                        memory_observation,
                        outcome=write_outcome,
                        status=write_status,
                        duration_metric="atlas.memory.write.duration",
                        metric_attributes={
                            "memory_type": request.memory_type.value,
                            "outcome": write_outcome,
                        },
                        error_code=write_error_code,
                    )
                written += 1
        except ExecutionDeadlineExpiredError:
            self._record(
                state,
                factory,
                AgentEventType.MEMORY_UPDATE_COMPLETED,
                {"outcome": "timed_out", "records_written": written},
            )
            raise
        except AgentMemoryError:
            self._record(
                state,
                factory,
                AgentEventType.MEMORY_UPDATE_COMPLETED,
                {"outcome": "failed", "records_written": written},
            )
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_write_failed",
                    message="Não foi possível persistir a memória selecionada.",
                ),
            )
            return state.to_result()
        except Exception:
            self._record(
                state,
                factory,
                AgentEventType.MEMORY_UPDATE_COMPLETED,
                {"outcome": "failed", "records_written": written},
            )
            self._fail(
                state,
                factory,
                AgentErrorInfo(
                    code="memory_write_failed",
                    message="Não foi possível persistir a memória selecionada.",
                ),
            )
            return state.to_result()
        self._record(
            state,
            factory,
            AgentEventType.MEMORY_UPDATE_COMPLETED,
            {
                "outcome": "completed",
                "records_written": written,
                "memory_types": [
                    memory_type.value
                    for memory_type in _MEMORY_TYPE_ORDER
                    if memory_type in {request.memory_type for request in requests}
                ],
            },
        )
        return None

    def _failed_output(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        *,
        code: str,
        message: str,
    ) -> AgentResult[object]:
        self._record(
            state,
            factory,
            AgentEventType.OUTPUT_VALIDATION_COMPLETED,
            {"outcome": "failed", "code": code},
        )
        self._fail(state, factory, AgentErrorInfo(code=code, message=message))
        return state.to_result()

    def _resolve_policies(
        self,
        *,
        limits: ExecutionLimits | None,
        budget: ExecutionBudget | None,
        observation: _InvocationObservation,
    ) -> _ExecutionPolicies:
        resolved_limits = limits if limits is not None else self._default_limits
        resolved_budget = budget if budget is not None else self._default_budget
        return _ExecutionPolicies(
            limits=resolved_limits,
            budget=resolved_budget,
            deadline=ExecutionDeadline.start(resolved_limits.timeout_seconds),
            observation=observation,
        )

    def _start_runtime_observation(
        self,
        *,
        state: ExecutionState,
        mode: ExecutionMode,
        resumed: bool,
        parent: TraceContext | None,
    ) -> _InvocationObservation:
        """Start one fail-open root span and count the runtime invocation."""
        started_at = self._observability.now()
        span = self._observability.start_span(
            "atlas.agent.execution",
            parent=parent,
            attributes={
                "atlas.execution.id": state.execution_id,
                "atlas.agent.id": state.agent.agent_id,
                "atlas.execution.mode": mode.value,
                "atlas.execution.resumed": resumed,
            },
        )
        self._observability.increment(
            "atlas.runtime.invocations",
            attributes={"mode": mode.value, "resumed": resumed},
        )
        return _InvocationObservation(
            span=span,
            started_at=started_at,
            mode=mode,
            resumed=resumed,
        )

    def _start_operation_observation(
        self,
        *,
        name: str,
        policies: _ExecutionPolicies,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Mapping[str, object] | None = None,
    ) -> _OperationObservation:
        """Start one logical child operation under the invocation span."""
        return _OperationObservation(
            span=self._observability.start_span(
                name,
                kind=kind,
                parent=policies.observation.span.context,
                attributes=attributes,
            ),
            started_at=self._observability.now(),
        )

    def _finish_operation_observation(
        self,
        observation: _OperationObservation,
        *,
        outcome: str,
        status: SpanStatus,
        duration_metric: str | None = None,
        metric_attributes: Mapping[str, object] | None = None,
        error_code: str | None = None,
    ) -> None:
        """Finalize a child operation and its optional duration metric."""
        observation.span.set_attribute("atlas.outcome", outcome)
        if error_code is not None:
            observation.span.set_attribute("atlas.error.code", error_code)
        observation.span.set_status(status)
        if duration_metric is not None:
            self._observability.record(
                duration_metric,
                self._observability.elapsed_since(observation.started_at),
                attributes=metric_attributes,
            )
        observation.span.end()

    def _start_model_observation(
        self,
        *,
        state: ExecutionState,
        selection: ModelSelectionResult,
        policies: _ExecutionPolicies,
        mode: str,
        request_id: str,
    ) -> _OperationObservation:
        """Start one logical model turn and count its request."""
        return self._start_operation_observation(
            name=f"atlas.model.{mode}",
            policies=policies,
            kind=SpanKind.CLIENT,
            attributes={
                "atlas.model.provider": selection.provider_name,
                "atlas.model.id": selection.model,
                "atlas.model.turn": state.turn_count,
                "atlas.model.request_id": request_id,
            },
        )

    def _finish_model_observation(
        self,
        observation: _OperationObservation,
        *,
        selection: ModelSelectionResult,
        mode: str,
        outcome: str,
        status: SpanStatus,
        response: ModelResponse | None = None,
        error_code: str | None = None,
    ) -> None:
        """Finalize one model turn with safe usage facts only."""
        if response is not None:
            observation.span.set_attribute(
                "atlas.model.finish_reason", response.finish_reason.value
            )
            observation.span.set_attribute(
                "atlas.model.input_tokens", response.usage.input_tokens
            )
            observation.span.set_attribute(
                "atlas.model.output_tokens", response.usage.output_tokens
            )
            observation.span.set_attribute(
                "atlas.model.total_tokens", response.usage.total_tokens
            )
            if response.usage.estimated_cost is not None:
                observation.span.set_attribute(
                    "atlas.model.estimated_cost",
                    str(response.usage.estimated_cost),
                )
        self._observability.increment(
            "atlas.model.requests",
            attributes={
                "provider": selection.provider_name,
                "model": selection.model,
                "mode": mode,
                "outcome": outcome,
            },
        )
        self._finish_operation_observation(
            observation,
            outcome=outcome,
            status=status,
            duration_metric="atlas.model.duration",
            metric_attributes={
                "provider": selection.provider_name,
                "model": selection.model,
                "mode": mode,
                "outcome": outcome,
            },
            error_code=error_code,
        )

    def _finish_runtime_observation(
        self,
        state: ExecutionState,
        observation: _InvocationObservation,
    ) -> None:
        """Finalize one invocation without changing its functional state."""
        outcome, status = self._observation_outcome(state.status)
        span = observation.span
        span.set_attribute("atlas.execution.status", state.status.value)
        span.set_attribute("atlas.execution.turn_count", state.turn_count)
        span.set_attribute("atlas.execution.tool_call_count", state.tool_call_count)
        span.set_attribute("atlas.outcome", outcome)
        if state.error is not None:
            span.set_attribute("atlas.error.code", state.error.code)
        span.set_status(status)
        metric_attributes = {
            "mode": observation.mode.value,
            "resumed": observation.resumed,
            "status": state.status.value,
            "outcome": outcome,
        }
        self._observability.record(
            "atlas.execution.duration",
            self._observability.elapsed_since(observation.started_at),
            attributes=metric_attributes,
        )
        if state.is_terminal:
            self._observability.increment(
                "atlas.executions.terminal",
                attributes=metric_attributes,
            )
        span.end()

    @staticmethod
    def _observation_outcome(
        status: ExecutionStatus,
    ) -> tuple[str, SpanStatus]:
        if status is ExecutionStatus.COMPLETED:
            return "completed", SpanStatus.OK
        if status is ExecutionStatus.REJECTED:
            return "rejected", SpanStatus.OK
        if status is ExecutionStatus.WAITING_FOR_APPROVAL:
            return "suspended", SpanStatus.OK
        if status is ExecutionStatus.LIMIT_EXCEEDED:
            return "limit_exceeded", SpanStatus.OK
        if status is ExecutionStatus.BUDGET_EXCEEDED:
            return "budget_exceeded", SpanStatus.OK
        if status is ExecutionStatus.FAILED:
            return "failed", SpanStatus.ERROR
        if status is ExecutionStatus.TIMED_OUT:
            return "timed_out", SpanStatus.ERROR
        if status is ExecutionStatus.CANCELLED:
            return "cancelled", SpanStatus.UNSET
        return "cancelled", SpanStatus.UNSET

    def _enforce_usage(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        policies: _ExecutionPolicies,
    ) -> AgentResult[object] | None:
        violation = self._limit_checker.check_usage(
            limits=policies.limits,
            usage=state.usage,
        )
        if violation is not None:
            return self._exceed_limit(state, factory, violation)
        budget_violation = self._limit_checker.check_budget(
            budget=policies.budget,
            usage=state.usage,
        )
        if budget_violation is not None:
            return self._exceed_budget(state, factory, budget_violation)
        return None

    def _exceed_limit(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        violation: ExecutionLimitViolation,
    ) -> AgentResult[object]:
        code = f"execution_{violation.reason.value}_exceeded"
        error = AgentErrorInfo(
            code=code,
            message=(
                f"A execução excedeu a política configurada '{violation.reason.value}'."
            ),
            details={
                "reason": violation.reason.value,
                "limit": violation.limit,
                "observed": violation.observed,
            },
        )
        state.exceed_limit(error=error)
        state.record_event(factory.from_transition(state.transitions[-1]))
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_LIMIT_EXCEEDED,
            {
                "reason": violation.reason.value,
                "limit": violation.limit,
                "observed": violation.observed,
            },
        )
        return state.to_result()

    def _exceed_budget(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        violation: ExecutionBudgetViolation,
    ) -> AgentResult[object]:
        details: dict[str, object] = {
            "limit": str(violation.limit),
            "observed": str(violation.observed),
        }
        error = AgentErrorInfo(
            code="execution_budget_exceeded",
            message="A execução excedeu o budget de custo estimado configurado.",
            details=details,
        )
        state.exceed_budget(error=error)
        state.record_event(factory.from_transition(state.transitions[-1]))
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_BUDGET_EXCEEDED,
            details,
        )
        return state.to_result()

    def _timeout(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        deadline: ExecutionDeadline,
    ) -> None:
        timeout_seconds = deadline.timeout_seconds
        error = AgentErrorInfo(
            code="execution_timed_out",
            message="A execução excedeu o timeout total configurado.",
            details={"timeout_seconds": timeout_seconds},
        )
        state.timeout(error=error)
        state.record_event(factory.from_transition(state.transitions[-1]))
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_TIMED_OUT,
            {
                "timeout_seconds": timeout_seconds,
                "elapsed_seconds": deadline.elapsed_seconds,
            },
        )

    def _record(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        event_type: AgentEventType,
        data: Mapping[str, object] | None = None,
    ) -> AgentEvent:
        del self
        event = factory.create(event_type, data=data)
        state.record_event(event)
        return event

    def _record_model_stream_event(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        event: ModelStreamEvent,
    ) -> AgentEvent:
        event_type, data = self._map_model_stream_event(event)
        return self._record(state, factory, event_type, data)

    @staticmethod
    def _map_model_stream_event(
        event: ModelStreamEvent,
    ) -> tuple[AgentEventType, dict[str, object]]:
        if event.type is ModelStreamEventType.RESPONSE_STARTED:
            data: dict[str, object] = {"response_id": event.response_id}
            if "model" in event.data:
                data["model"] = event.data["model"]
            return AgentEventType.MODEL_STREAM_STARTED, data
        if event.type is ModelStreamEventType.TEXT_DELTA:
            return AgentEventType.MODEL_TEXT_DELTA, {"text": event.data["text"]}
        if event.type is ModelStreamEventType.TOOL_CALL_STARTED:
            return AgentEventType.MODEL_TOOL_CALL_STARTED, {
                "tool_call_id": event.data["tool_call_id"],
                "name": event.data["name"],
            }
        if event.type is ModelStreamEventType.TOOL_CALL_ARGUMENT_DELTA:
            return AgentEventType.MODEL_TOOL_CALL_ARGUMENT_DELTA, {
                "tool_call_id": event.data["tool_call_id"],
                "delta": event.data["delta"],
            }
        if event.type is ModelStreamEventType.TOOL_CALL_COMPLETED:
            tool_call = cast(dict[str, object], event.data["tool_call"])
            return AgentEventType.MODEL_TOOL_CALL_COMPLETED, {
                "tool_call_id": tool_call["tool_call_id"],
                "name": tool_call["name"],
            }
        if event.type is ModelStreamEventType.USAGE_UPDATED:
            return AgentEventType.MODEL_USAGE_UPDATED, {"usage": event.data["usage"]}
        if event.type is ModelStreamEventType.RESPONSE_COMPLETED:
            return AgentEventType.MODEL_STREAM_COMPLETED, {
                "outcome": "completed",
                "response_id": event.response_id,
                "model": event.data["model"],
                "finish_reason": event.data["finish_reason"],
            }
        return AgentEventType.MODEL_STREAM_COMPLETED, {
            "outcome": "error",
            "response_id": event.response_id,
        }

    @staticmethod
    def _stream_error(error: ModelStreamProtocolError) -> AgentErrorInfo:
        if isinstance(error, InvalidModelStreamSequenceError):
            code = "model_stream_sequence_error"
        elif isinstance(error, ModelStreamIncompleteError):
            code = "incomplete_model_stream"
        elif isinstance(error, ModelStreamReportedError):
            code = "model_stream_error"
        elif isinstance(error, InvalidModelStreamProtocolError):
            code = "invalid_model_stream_protocol"
        else:
            code = "model_stream_protocol_error"
        return AgentErrorInfo(code=code, message=str(error))

    @staticmethod
    def _transition(
        state: ExecutionState,
        factory: AgentEventFactory,
        status: ExecutionStatus,
        *,
        reason: str | None = None,
    ) -> None:
        transition = state.transition_to(status, reason=reason)
        state.record_event(factory.from_transition(transition))

    def _fail(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        error: AgentErrorInfo,
    ) -> None:
        state.fail(error)
        state.record_event(factory.from_transition(state.transitions[-1]))
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_FAILED,
            {"code": error.code},
        )

    def _fail_preparation(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        error: AgentErrorInfo,
    ) -> None:
        if state.status is ExecutionStatus.LOADING_CONTEXT:
            self._record(
                state,
                factory,
                AgentEventType.CONTEXT_LOADING_COMPLETED,
                {"outcome": "failed", "code": error.code},
            )
        self._fail(state, factory, error)

    def _reject(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        *,
        code: str,
        reason: str,
        retain_error: bool = False,
    ) -> None:
        if retain_error:
            state.reject(
                error=AgentErrorInfo(code=code, message=reason),
                reason=reason,
            )
            state.record_event(factory.from_transition(state.transitions[-1]))
        else:
            self._transition(
                state,
                factory,
                ExecutionStatus.REJECTED,
                reason=reason,
            )
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_REJECTED,
            {"code": code, "reason": reason},
        )

    def _cancel(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        *,
        reason: str,
    ) -> None:
        state.cancel(reason=reason)
        state.record_event(factory.from_transition(state.transitions[-1]))
        self._record(
            state,
            factory,
            AgentEventType.EXECUTION_CANCELLED,
            {"reason": reason},
        )

    @staticmethod
    def _runtime_error() -> AgentErrorInfo:
        return AgentErrorInfo(
            code="runtime_error",
            message="A execução falhou devido a um erro interno inesperado.",
        )
