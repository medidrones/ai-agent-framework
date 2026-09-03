"""Multi-turn agent runtime orchestrating model and tool invocations."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
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
    ModelResponse,
    ModelSelectionRequest,
    ModelSelectionResult,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelToolDefinition,
    TextContent,
    ToolCall,
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
from atlas_agents.runtime.tool_calls import ToolCallRecord
from atlas_agents.runtime.tool_results import ToolResultMessageMapper
from atlas_agents.tools import (
    ToolExecutionContext,
    ToolExecutionInvariantError,
    ToolExecutionRequest,
    ToolExecutionResult,
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
        """Execute model and tool turns and return a terminal result."""
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
    ) -> AgentResult[object]:
        """Run model and tool turns inside one unchanged policy scope."""
        prepared = await self._prepare(
            state=state,
            factory=factory,
            agent=agent,
            input_data=input_data,
            model_selection=model_selection,
        )
        if isinstance(prepared, AgentResult):
            return prepared

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
            model_context = self._model_context(state, agent)
            try:
                response = await prepared.provider.generate(request, model_context)
            except ModelProviderError as error:
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
            if response.finish_reason is FinishReason.TOOL_CALL:
                tool_result = await self._process_tool_calls(
                    state=state,
                    factory=factory,
                    response=response,
                    policies=policies,
                )
                if tool_result is not None:
                    return tool_result
                continue

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
                accumulator = ModelStreamAccumulator()
                try:
                    request = self._request_builder.build_request(
                        state,
                        prepared.selection,
                        tools=prepared.tool_definitions,
                    )
                    provider_iterator = prepared.provider.stream(
                        request,
                        self._model_context(state, agent),
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
                    elif response.finish_reason is FinishReason.TOOL_CALL:
                        tool_result = await self._process_tool_calls(
                            state=state,
                            factory=factory,
                            response=response,
                            policies=policies,
                        )
                        for event in state.events[emitted_events:]:
                            yield RuntimeEventItem(event=event)
                            emitted_events += 1
                        if tool_result is not None:
                            result = tool_result
                        else:
                            async for item in self._stream_followup_turns(
                                state=state,
                                factory=factory,
                                prepared=prepared,
                                agent=agent,
                                policies=policies,
                            ):
                                yield item
                            return
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
                    reason="O consumidor encerrou o stream antes da conclusão.",
                )

        for event in state.events[emitted_events:]:
            yield RuntimeEventItem(event=event)
            emitted_events += 1
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
        result: AgentResult[object] | None = None
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
            try:
                request = self._request_builder.build_request(
                    state,
                    prepared.selection,
                    tools=prepared.tool_definitions,
                )
                provider_iterator = prepared.provider.stream(
                    request,
                    self._model_context(state, agent),
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
                break
            except ModelStreamProtocolError as error:
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
            if result is None and response.finish_reason is FinishReason.TOOL_CALL:
                result = await self._process_tool_calls(
                    state=state,
                    factory=factory,
                    response=response,
                    policies=policies,
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
                result = self._finish_response(state, factory, response)

            for event in state.events[emitted_events:]:
                yield RuntimeEventItem(event=event)
                emitted_events += 1

        if result is None:
            raise RuntimeError("O loop incremental terminou sem resultado.")
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
        return _PreparedExecution(
            state=state,
            factory=factory,
            provider=provider,
            selection=selection,
            tool_definitions=tool_definitions,
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
    ) -> AgentResult[object] | None:
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
        self._transition(state, factory, ExecutionStatus.EXECUTING_TOOL)

        for call in response.tool_calls:
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
                self._record_tool_completion(
                    state,
                    factory,
                    previous.result,
                    deduplicated=True,
                )
                state.add_message(self._tool_result_mapper.map(previous.result))
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
                self._record_processed_tool_call(state, call, prepared)
                self._record_tool_completion(state, factory, prepared)
                state.add_message(self._tool_result_mapper.map(prepared))
                continue

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
            try:
                result = await policies.deadline.wait_for(
                    partial(self._tool_executor.execute_prepared, prepared)
                )
            except ExecutionDeadlineExpiredError:
                raise
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
            self._record_processed_tool_call(state, call, result)
            self._record_tool_completion(state, factory, result)
            state.add_message(self._tool_result_mapper.map(result))

        self._transition(state, factory, ExecutionStatus.RUNNING)
        return None

    @staticmethod
    def _record_processed_tool_call(
        state: ExecutionState,
        call: ToolCall,
        result: ToolExecutionResult,
    ) -> None:
        state.record_tool_call(
            ToolCallRecord(
                tool_call_id=call.tool_call_id,
                tool_name=call.name,
                arguments=call.arguments,
                result=result,
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
