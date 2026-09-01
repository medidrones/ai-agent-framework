"""Tests for controlled runtime execution state management."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentErrorInfo,
    AgentEvent,
    AgentEventFactory,
    AgentEventType,
    AgentInput,
    ExecutionAlreadyTerminalError,
    ExecutionLifecycle,
    ExecutionSnapshot,
    ExecutionState,
    ExecutionStateInvariantError,
    ExecutionStatus,
    InvalidExecutionTransitionError,
    MessageRole,
    ModelCapability,
    ModelDescriptor,
    ModelMessage,
    ModelSelectionResult,
    ModelUsage,
    TextContent,
)

START = datetime(2026, 1, 1, tzinfo=UTC)


class ControlledClock:
    """Return deterministic instants for state tests."""

    def __init__(self, *values: datetime) -> None:
        self._values: Iterator[datetime] = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def _state(
    *,
    context: AgentContext | None = None,
    metadata: dict[str, object] | None = None,
    lifecycle: ExecutionLifecycle | None = None,
    clock: ControlledClock | None = None,
) -> ExecutionState:
    return ExecutionState(
        execution_id="execution-1",
        agent=AgentDefinition(
            agent_id="agent-1",
            name="Agent",
            instructions="Answer safely.",
        ),
        input_data=AgentInput(message="Hello"),
        context=context or AgentContext(execution_id="execution-1"),
        metadata=metadata,
        lifecycle=lifecycle,
        clock=clock or ControlledClock(*([START] * 100)),
    )


def _message(text: str) -> ModelMessage:
    return ModelMessage(
        role=MessageRole.USER,
        content=(TextContent(text=text),),
    )


def _selection() -> ModelSelectionResult:
    capabilities = frozenset({ModelCapability.TEXT_GENERATION})
    descriptor = ModelDescriptor(
        provider="provider",
        model="model",
        capabilities=capabilities,
    )
    return ModelSelectionResult(
        provider_name="provider",
        model="model",
        descriptor=descriptor,
        matched_required_capabilities=capabilities,
        matched_preferred_capabilities=frozenset(),
        preferred_capability_matches=0,
        candidate_count=1,
    )


def _error() -> AgentErrorInfo:
    return AgentErrorInfo(code="runtime_error", message="Falha controlada")


def _advance_to_running(state: ExecutionState) -> None:
    state.transition_to(ExecutionStatus.VALIDATING_INPUT)
    state.transition_to(ExecutionStatus.LOADING_CONTEXT)
    state.transition_to(ExecutionStatus.RUNNING)


def _event(sequence: int, *, execution_id: str = "execution-1") -> AgentEvent:
    return AgentEvent(
        event_id=f"event-{sequence}",
        execution_id=execution_id,
        sequence=sequence,
        event_type=AgentEventType.EXECUTION_STATUS_CHANGED,
        timestamp=START,
    )


def test_creation_exposes_initial_state_and_references() -> None:
    state = _state()

    assert state.execution_id == "execution-1"
    assert state.agent.agent_id == "agent-1"
    assert state.input_data.message == "Hello"
    assert state.context.execution_id == "execution-1"
    assert state.status is ExecutionStatus.CREATED
    assert not state.is_terminal
    assert state.transitions == ()
    assert state.messages == ()
    assert state.events == ()
    assert state.model_selection is None
    assert state.usage.total_tokens == 0
    assert state.turn_count == 0
    assert state.tool_call_count == 0
    assert state.output is None
    assert state.error is None
    assert state.created_at == START
    assert state.updated_at == START
    assert state.created_at.utcoffset() is not None


def test_default_clock_creates_timezone_aware_timestamp() -> None:
    state = ExecutionState(
        execution_id="execution-1",
        agent=AgentDefinition(
            agent_id="agent-1", name="Agent", instructions="Answer safely."
        ),
        input_data=AgentInput(message="Hello"),
        context=AgentContext(execution_id="execution-1"),
    )

    assert state.created_at.utcoffset() is not None


def test_creation_rejects_empty_or_mismatched_execution_id() -> None:
    with pytest.raises(ExecutionStateInvariantError, match="não pode estar vazio"):
        ExecutionState(
            execution_id=" ",
            agent=AgentDefinition(
                agent_id="agent", name="Agent", instructions="Instructions"
            ),
            input_data=AgentInput(message="input"),
            context=AgentContext(execution_id="context-id"),
        )
    with pytest.raises(ExecutionStateInvariantError, match="contexto"):
        _state(context=AgentContext(execution_id="other"))


def test_creation_rejects_non_created_lifecycle() -> None:
    lifecycle = ExecutionLifecycle()
    lifecycle.transition_to(ExecutionStatus.VALIDATING_INPUT)

    with pytest.raises(ExecutionStateInvariantError, match="created"):
        _state(lifecycle=lifecycle)


def test_metadata_is_independent_from_context_and_explicit_input() -> None:
    context_metadata: dict[str, object] = {"nested": {"value": 1}}
    context = AgentContext(execution_id="execution-1", metadata=context_metadata)
    state = _state(context=context)
    context_metadata["changed"] = True
    exposed = state.metadata
    exposed["changed"] = True

    assert state.metadata == {"nested": {"value": 1}}

    explicit: dict[str, object] = {"source": ["runtime"]}
    explicit_state = _state(context=context, metadata=explicit)
    explicit["source"] = []
    assert explicit_state.metadata == {"source": ["runtime"]}


def test_creation_rejects_invalid_metadata_and_clock() -> None:
    with pytest.raises(ExecutionStateInvariantError, match="serializáveis"):
        _state(metadata={"invalid": object()})
    with pytest.raises(ExecutionStateInvariantError, match="relógio"):
        _state(clock=ControlledClock(datetime(2026, 1, 1)))


def test_transition_delegates_history_and_rejects_invalid_paths() -> None:
    state = _state()
    transition = state.transition_to(
        ExecutionStatus.VALIDATING_INPUT,
        reason="começar validação",
        metadata={"stage": 1},
    )

    assert state.status is ExecutionStatus.VALIDATING_INPUT
    assert state.transitions == (transition,)
    assert transition.reason == "começar validação"
    with pytest.raises(InvalidExecutionTransitionError):
        state.transition_to(ExecutionStatus.COMPLETED)
    with pytest.raises(ExecutionStateInvariantError, match=r"fail\(\)"):
        state.transition_to(ExecutionStatus.FAILED)


def test_messages_preserve_order_and_tuple_exposure() -> None:
    state = _state()
    first = _message("first")
    second = _message("second")

    state.add_message(first)
    state.add_message(second)

    assert state.messages == (first, second)
    assert isinstance(state.messages, tuple)


def test_model_selection_can_be_set_exactly_once() -> None:
    state = _state()
    selection = _selection()

    state.set_model_selection(selection)

    assert state.model_selection is selection
    with pytest.raises(ExecutionStateInvariantError, match="substituída"):
        state.set_model_selection(selection)


@pytest.mark.parametrize("count", [0, -1, True, 1.5])
def test_counters_are_monotonic_and_reject_invalid_tool_counts(count: object) -> None:
    state = _state()
    state.increment_turn()
    state.increment_turn()
    state.increment_tool_calls()
    state.increment_tool_calls(3)

    assert state.turn_count == 2
    assert state.tool_call_count == 4
    with pytest.raises(ExecutionStateInvariantError, match="positivo"):
        state.increment_tool_calls(count)  # type: ignore[arg-type]


def test_usage_aggregates_all_tokens_and_known_costs() -> None:
    state = _state()
    state.add_model_usage(
        ModelUsage(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cached_input_tokens=3,
            reasoning_tokens=2,
            estimated_cost=Decimal("0.10"),
        )
    )
    state.add_model_usage(
        ModelUsage(
            input_tokens=4,
            output_tokens=6,
            total_tokens=10,
            cached_input_tokens=1,
            reasoning_tokens=4,
            estimated_cost=Decimal("0.20"),
        )
    )

    assert state.usage.input_tokens == 14
    assert state.usage.output_tokens == 11
    assert state.usage.total_tokens == 25
    assert state.usage.cached_input_tokens == 4
    assert state.usage.reasoning_tokens == 6
    assert state.usage.estimated_cost == Decimal("0.30")


@pytest.mark.parametrize("unknown_first", [True, False])
def test_usage_unknown_cost_propagates(unknown_first: bool) -> None:
    state = _state()
    known = ModelUsage(
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        estimated_cost=Decimal("0.10"),
    )
    unknown = ModelUsage(input_tokens=1, output_tokens=0, total_tokens=1)

    for usage in (unknown, known) if unknown_first else (known, unknown):
        state.add_model_usage(usage)

    assert state.usage.estimated_cost is None


def test_first_known_usage_sets_cost_despite_zero_initial_aggregate() -> None:
    state = _state()

    state.add_model_usage(ModelUsage(total_tokens=0, estimated_cost=Decimal("0.05")))

    assert state.usage.estimated_cost == Decimal("0.05")


def test_events_validate_identity_sequence_and_allow_terminal_journal() -> None:
    state = _state()
    first = _event(1)
    second = _event(2)
    state.record_event(first)
    state.cancel()
    state.record_event(second)

    assert state.events == (first, second)
    assert isinstance(state.events, tuple)
    with pytest.raises(ExecutionStateInvariantError, match="mesma execução"):
        _state().record_event(_event(1, execution_id="other"))
    with pytest.raises(ExecutionStateInvariantError, match="contínua"):
        _state().record_event(_event(2))


def test_event_factory_and_state_responsibilities_remain_separate() -> None:
    state = _state()
    factory = AgentEventFactory(state.execution_id)
    transition = state.transition_to(ExecutionStatus.VALIDATING_INPUT)
    event = factory.from_transition(transition)

    assert state.events == ()
    state.record_event(event)
    assert len(state.events) == 1
    assert state.events[0] == event


def test_mutations_update_time_but_reads_do_not() -> None:
    later = START + timedelta(seconds=1)
    state = _state(clock=ControlledClock(START, later))
    before_read = state.updated_at
    _ = state.messages
    _ = state.snapshot()
    assert state.updated_at == before_read

    state.increment_turn()
    assert state.updated_at == later
    assert state.updated_at >= state.created_at


def test_mutation_rejects_naive_or_retrograde_timestamp() -> None:
    state = _state()
    with pytest.raises(ExecutionStateInvariantError, match="fuso horário"):
        state.transition_to(
            ExecutionStatus.VALIDATING_INPUT,
            timestamp=datetime(2026, 1, 1),
        )
    with pytest.raises(ExecutionStateInvariantError, match="retroceder"):
        state.transition_to(
            ExecutionStatus.VALIDATING_INPUT,
            timestamp=START - timedelta(seconds=1),
        )


def test_complete_requires_valid_lifecycle_path_and_maps_output() -> None:
    invalid = _state()
    with pytest.raises(InvalidExecutionTransitionError):
        invalid.complete("output")
    assert invalid.output is None

    state = _state()
    _advance_to_running(state)
    state.transition_to(ExecutionStatus.VALIDATING_OUTPUT)
    source = {"answer": [42]}
    state.complete(source)
    source["answer"].append(43)

    assert state.status is ExecutionStatus.COMPLETED
    assert state.output == {"answer": [42]}
    assert state.error is None


def test_fail_cancel_and_timeout_delegate_to_lifecycle() -> None:
    failed = _state()
    failed.fail(_error())
    assert failed.status is ExecutionStatus.FAILED
    assert failed.error == _error()

    cancelled = _state()
    cancelled.cancel(reason="solicitado")
    assert cancelled.status is ExecutionStatus.CANCELLED
    assert cancelled.transitions[-1].reason == "solicitado"

    timed_out = _state()
    timed_out.transition_to(ExecutionStatus.VALIDATING_INPUT)
    timed_out.timeout(error=_error())
    assert timed_out.status is ExecutionStatus.TIMED_OUT
    assert timed_out.error == _error()


def test_fail_requires_error() -> None:
    with pytest.raises(ExecutionStateInvariantError, match="erro estruturado"):
        _state().fail(None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "operation",
    [
        lambda state: state.add_message(_message("late")),
        lambda state: state.set_model_selection(_selection()),
        lambda state: state.increment_turn(),
        lambda state: state.increment_tool_calls(),
        lambda state: state.add_model_usage(ModelUsage()),
    ],
)
def test_operational_mutations_are_rejected_after_terminal(operation: object) -> None:
    state = _state()
    state.cancel()

    with pytest.raises(ExecutionAlreadyTerminalError):
        operation(state)  # type: ignore[operator]
    with pytest.raises(InvalidExecutionTransitionError):
        state.transition_to(ExecutionStatus.CREATED)
    with pytest.raises(InvalidExecutionTransitionError):
        state.transition_to(ExecutionStatus.FAILED)


def test_snapshot_is_frozen_serializable_and_isolated() -> None:
    state = _state(metadata={"nested": {"value": 1}})
    state.add_message(_message("before"))
    state.set_model_selection(_selection())
    state.increment_turn()
    state.increment_tool_calls(2)
    state.record_event(_event(1))
    snapshot = state.snapshot()

    state.add_message(_message("after"))
    state.increment_turn()
    exposed_metadata = snapshot.metadata
    exposed_metadata["changed"] = True

    assert isinstance(snapshot, ExecutionSnapshot)
    assert snapshot.agent_id == "agent-1"
    assert len(snapshot.messages) == 1
    assert snapshot.turn_count == 1
    assert snapshot.tool_call_count == 2
    assert snapshot.events == (_event(1),)
    assert snapshot.model_selection == _selection()
    assert snapshot.created_at == START
    assert snapshot.model_dump_json()
    with pytest.raises(ValidationError):
        snapshot.turn_count = 5


@pytest.mark.parametrize(
    "updates",
    [
        {"updated_at": START - timedelta(seconds=1)},
        {"status": ExecutionStatus.COMPLETED, "error": _error()},
        {"status": ExecutionStatus.FAILED, "error": None},
    ],
)
def test_snapshot_rejects_inconsistent_facts(updates: dict[str, object]) -> None:
    base: dict[str, object] = {
        "execution_id": "execution-1",
        "agent_id": "agent-1",
        "status": ExecutionStatus.CREATED,
        "created_at": START,
        "updated_at": START,
    }

    with pytest.raises(ValidationError):
        ExecutionSnapshot.model_validate(base | updates)


def test_to_result_rejects_non_terminal_state() -> None:
    with pytest.raises(ExecutionStateInvariantError, match="término"):
        _state().to_result()


@pytest.mark.parametrize(
    "terminal_status",
    [
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
        ExecutionStatus.LIMIT_EXCEEDED,
        ExecutionStatus.BUDGET_EXCEEDED,
        ExecutionStatus.REJECTED,
    ],
)
def test_all_terminal_states_produce_agent_result(
    terminal_status: ExecutionStatus,
) -> None:
    state = _state()
    if terminal_status is ExecutionStatus.COMPLETED:
        _advance_to_running(state)
        state.transition_to(ExecutionStatus.VALIDATING_OUTPUT)
        state.complete("done")
    elif terminal_status is ExecutionStatus.FAILED:
        state.fail(_error())
    elif terminal_status is ExecutionStatus.CANCELLED:
        state.cancel()
    elif terminal_status is ExecutionStatus.TIMED_OUT:
        state.transition_to(ExecutionStatus.VALIDATING_INPUT)
        state.timeout()
    elif terminal_status is ExecutionStatus.REJECTED:
        state.transition_to(ExecutionStatus.VALIDATING_INPUT)
        state.transition_to(terminal_status)
    else:
        _advance_to_running(state)
        state.transition_to(terminal_status)

    result = state.to_result()

    assert result.execution_id == state.execution_id
    assert result.status is terminal_status
    assert result.output == state.output
    assert result.usage == state.usage
    assert result.events == state.events
    assert result.error == state.error
