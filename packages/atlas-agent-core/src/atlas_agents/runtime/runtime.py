"""Single-turn agent runtime orchestrating one complete model invocation."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
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
from atlas_agents.events import AgentEvent, AgentEventFactory, AgentEventType
from atlas_agents.exceptions import (
    ModelProviderError,
    ModelProviderRegistryError,
    ModelSelectionError,
)
from atlas_agents.models import (
    FinishReason,
    MessageRole,
    ModelCapability,
    ModelExecutionContext,
    ModelMessage,
    ModelProvider,
    ModelProviderRegistry,
    ModelRequest,
    ModelResponse,
    ModelSelectionRequest,
    ModelSelectionResult,
    ModelStreamEvent,
    ModelStreamEventType,
    TextContent,
)
from atlas_agents.runtime.budget import ExecutionBudget, ExecutionBudgetViolation
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
from atlas_agents.runtime.state import ExecutionState
from atlas_agents.runtime.stream_accumulator import ModelStreamAccumulator
from atlas_agents.runtime.stream_items import (
    RuntimeEventItem,
    RuntimeResultItem,
    RuntimeStreamItem,
)


@dataclass(frozen=True)
class _PreparedExecution:
    state: ExecutionState
    factory: AgentEventFactory
    provider: ModelProvider
    request: ModelRequest
    model_context: ModelExecutionContext
    selection: ModelSelectionResult


@dataclass(frozen=True)
class _ExecutionPolicies:
    limits: ExecutionLimits
    budget: ExecutionBudget
    deadline: ExecutionDeadline


@runtime_checkable
class _AsyncClosable(Protocol):
    async def aclose(self) -> None:
        """Close an asynchronous provider iterator."""


class AgentRuntime:
    """Own the provider-agnostic execution loop for one model turn."""

    def __init__(
        self,
        *,
        model_registry: ModelProviderRegistry,
        request_builder: ModelRequestBuilder | None = None,
        limits: ExecutionLimits | None = None,
        budget: ExecutionBudget | None = None,
    ) -> None:
        """Initialize the runtime with explicit replaceable dependencies."""
        self._model_registry = model_registry
        self._request_builder = (
            request_builder if request_builder is not None else ModelRequestBuilder()
        )
        self._default_limits = limits if limits is not None else ExecutionLimits()
        self._default_budget = budget if budget is not None else ExecutionBudget()
        self._limit_checker = ExecutionLimitChecker()

    async def run(
        self,
        *,
        agent: AgentDefinition,
        input_data: AgentInput,
        context: AgentContext,
        model_selection: ModelSelectionRequest | None = None,
        limits: ExecutionLimits | None = None,
        budget: ExecutionBudget | None = None,
    ) -> AgentResult[object]:
        """Execute exactly one model generation and return a terminal result."""
        policies = self._resolve_policies(limits=limits, budget=budget)
        state = ExecutionState(
            execution_id=context.execution_id,
            agent=agent,
            input_data=input_data,
            context=context,
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
                if state.turn_count > 0:
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

    async def _run_execution(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        agent: AgentDefinition,
        input_data: AgentInput,
        model_selection: ModelSelectionRequest | None,
        policies: _ExecutionPolicies,
    ) -> AgentResult[object]:
        """Run the generation path inside one execution policy scope."""
        prepared = await self._prepare(
            state=state,
            factory=factory,
            agent=agent,
            input_data=input_data,
            model_selection=model_selection,
        )
        if isinstance(prepared, AgentResult):
            return prepared
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
            },
        )
        state.increment_turn()
        try:
            response = await prepared.provider.generate(
                prepared.request,
                prepared.model_context,
            )
        except ModelProviderError as error:
            self._record(
                state,
                factory,
                AgentEventType.MODEL_EXECUTION_COMPLETED,
                {"outcome": "failed"},
            )
            self._fail(state, factory, model_provider_error_to_agent_error(error))
            return state.to_result()
        except Exception:
            self._record(
                state,
                factory,
                AgentEventType.MODEL_EXECUTION_COMPLETED,
                {"outcome": "failed"},
            )
            self._fail(state, factory, self._runtime_error())
            return state.to_result()

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
        state.add_message(
            ModelMessage(role=MessageRole.ASSISTANT, content=response.content)
        )
        self._transition(state, factory, ExecutionStatus.VALIDATING_OUTPUT)
        self._record(state, factory, AgentEventType.OUTPUT_VALIDATION_STARTED)
        return self._finish_response(state, factory, response)

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
        policies = self._resolve_policies(limits=limits, budget=budget)
        state = ExecutionState(
            execution_id=context.execution_id,
            agent=agent,
            input_data=input_data,
            context=context,
        )
        factory = AgentEventFactory(context.execution_id)
        self._start_execution(state, factory)
        emitted_events = 0
        provider_iterator: AsyncIterator[ModelStreamEvent] | None = None
        provider_exhausted = False
        invocation_started = False
        try:
            prepared = await policies.deadline.wait_for(
                lambda: self._prepare(
                    state=state,
                    factory=factory,
                    agent=agent,
                    input_data=input_data,
                    model_selection=model_selection,
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
                invocation_started = True
                accumulator = ModelStreamAccumulator()
                try:
                    provider_iterator = prepared.provider.stream(
                        prepared.request,
                        prepared.model_context,
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
                    raise
                except ModelProviderError as error:
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
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "failed", "mode": "stream"},
                    )
                    self._fail(state, factory, self._stream_error(error))
                    result = state.to_result()
                except Exception:
                    self._record(
                        state,
                        factory,
                        AgentEventType.MODEL_EXECUTION_COMPLETED,
                        {"outcome": "failed", "mode": "stream"},
                    )
                    self._fail(state, factory, self._runtime_error())
                    result = state.to_result()
                else:
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
                        result = self._finish_response(state, factory, response)
        except ExecutionDeadlineExpiredError:
            if not state.is_terminal:
                if invocation_started:
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
                if invocation_started:
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
            if not state.is_terminal:
                if invocation_started:
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

        for event in state.events[emitted_events:]:
            yield RuntimeEventItem(event=event)
            emitted_events += 1
        yield RuntimeResultItem(result=result)

    async def _prepare(
        self,
        *,
        state: ExecutionState,
        factory: AgentEventFactory,
        agent: AgentDefinition,
        input_data: AgentInput,
        model_selection: ModelSelectionRequest | None,
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
        self._record(
            state,
            factory,
            AgentEventType.INPUT_VALIDATION_COMPLETED,
            {"outcome": "accepted"},
        )

        self._transition(state, factory, ExecutionStatus.LOADING_CONTEXT)
        self._record(state, factory, AgentEventType.CONTEXT_LOADING_STARTED)
        messages = self._request_builder.build_initial_messages(agent, input_data)
        for message in messages:
            state.add_message(message)
        selection_request = self._request_builder.derive_selection_request(
            input_data,
            model_selection,
            additional_required_capabilities=additional_required_capabilities,
        )
        try:
            selection = await self._model_registry.select(selection_request)
            state.set_model_selection(selection)
            provider = self._model_registry.get(selection.provider_name)
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

        self._record(
            state,
            factory,
            AgentEventType.CONTEXT_LOADING_COMPLETED,
            {"outcome": "completed"},
        )
        self._transition(state, factory, ExecutionStatus.RUNNING)
        request = self._request_builder.build_request(state, selection)
        model_context = ModelExecutionContext(
            execution_id=state.execution_id,
            agent_id=agent.agent_id,
            request_id=str(uuid4()),
        )
        return _PreparedExecution(
            state=state,
            factory=factory,
            provider=provider,
            request=request,
            model_context=model_context,
            selection=selection,
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

    def _finish_response(
        self,
        state: ExecutionState,
        factory: AgentEventFactory,
        response: ModelResponse,
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
            self._record(
                state,
                factory,
                AgentEventType.OUTPUT_VALIDATION_COMPLETED,
                {
                    "outcome": "accepted",
                    "partial": response.finish_reason is FinishReason.LENGTH,
                },
            )
            state.complete(output)
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
                "Chamadas de ferramentas não são suportadas pelo runtime single-turn.",
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
    ) -> _ExecutionPolicies:
        resolved_limits = limits if limits is not None else self._default_limits
        resolved_budget = budget if budget is not None else self._default_budget
        return _ExecutionPolicies(
            limits=resolved_limits,
            budget=resolved_budget,
            deadline=ExecutionDeadline.start(resolved_limits.timeout_seconds),
        )

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
    ) -> None:
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
