"""Controlled in-memory state for one agent execution."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

from atlas_agents._models import _json_mapping, _non_empty, _timezone_aware
from atlas_agents.agents import (
    AgentContext,
    AgentDefinition,
    AgentErrorInfo,
    AgentInput,
    AgentResult,
    ExecutionStatus,
    Usage,
)
from atlas_agents.events import AgentEvent
from atlas_agents.execution import ExecutionLifecycle, ExecutionTransition, is_terminal
from atlas_agents.models import ModelMessage, ModelSelectionResult, ModelUsage
from atlas_agents.runtime.errors import (
    ExecutionAlreadyTerminalError,
    ExecutionStateInvariantError,
)
from atlas_agents.runtime.snapshot import ExecutionSnapshot

Clock = Callable[[], datetime]


class ExecutionState:
    """Own controlled mutable state for one execution.

    An instance is scoped to one execution and is not thread-safe. The future
    runtime must coordinate access and remains responsible for all I/O.
    """

    def __init__(
        self,
        *,
        execution_id: str,
        agent: AgentDefinition,
        input_data: AgentInput,
        context: AgentContext,
        lifecycle: ExecutionLifecycle | None = None,
        metadata: Mapping[str, object] | None = None,
        clock: Clock | None = None,
    ) -> None:
        """Initialize a newly created execution without performing external work."""
        try:
            validated_execution_id = _non_empty(execution_id)
        except ValueError as exc:
            raise ExecutionStateInvariantError(
                "O identificador da execução não pode estar vazio."
            ) from exc
        if context.execution_id != validated_execution_id:
            raise ExecutionStateInvariantError(
                "O identificador do contexto deve coincidir com o da execução."
            )

        resolved_lifecycle = (
            lifecycle if lifecycle is not None else ExecutionLifecycle()
        )
        if resolved_lifecycle.status is not ExecutionStatus.CREATED:
            raise ExecutionStateInvariantError(
                "O lifecycle de um novo estado deve iniciar em created."
            )

        self._clock = clock if clock is not None else _utc_now
        created_at = self._read_clock()
        source_metadata = context.metadata if metadata is None else dict(metadata)
        try:
            isolated_metadata = _json_mapping(dict(source_metadata))
        except ValueError as exc:
            raise ExecutionStateInvariantError(
                "Os metadados do estado devem ser serializáveis em JSON."
            ) from exc

        self._execution_id = validated_execution_id
        self._agent = agent
        self._input_data = input_data
        self._context = context
        self._lifecycle = resolved_lifecycle
        self._messages: list[ModelMessage] = []
        self._model_selection: ModelSelectionResult | None = None
        self._usage = Usage()
        self._has_usage = False
        self._turn_count = 0
        self._tool_call_count = 0
        self._events: list[AgentEvent] = []
        self._output: object | None = None
        self._error: AgentErrorInfo | None = None
        self._created_at = created_at
        self._updated_at = created_at
        self._metadata = isolated_metadata

    @property
    def execution_id(self) -> str:
        """Return the opaque execution identifier."""
        return self._execution_id

    @property
    def agent(self) -> AgentDefinition:
        """Return the immutable declarative agent definition."""
        return self._agent

    @property
    def input_data(self) -> AgentInput:
        """Return the immutable original agent input."""
        return self._input_data

    @property
    def context(self) -> AgentContext:
        """Return the immutable execution context."""
        return self._context

    @property
    def status(self) -> ExecutionStatus:
        """Return the lifecycle status without exposing a setter."""
        return self._lifecycle.status

    @property
    def transitions(self) -> tuple[ExecutionTransition, ...]:
        """Return lifecycle history without maintaining a duplicate journal."""
        return self._lifecycle.history

    @property
    def is_terminal(self) -> bool:
        """Return whether the execution has permanently ended."""
        return self._lifecycle.is_terminal

    @property
    def messages(self) -> tuple[ModelMessage, ...]:
        """Return messages in insertion order as an immutable tuple."""
        return tuple(self._messages)

    @property
    def model_selection(self) -> ModelSelectionResult | None:
        """Return the single recorded model selection, when available."""
        return self._model_selection

    @property
    def usage(self) -> Usage:
        """Return immutable aggregate usage."""
        return self._usage

    @property
    def turn_count(self) -> int:
        """Return the monotonic turn counter."""
        return self._turn_count

    @property
    def tool_call_count(self) -> int:
        """Return the monotonic tool-call counter."""
        return self._tool_call_count

    @property
    def events(self) -> tuple[AgentEvent, ...]:
        """Return recorded events in sequence order as an immutable tuple."""
        return tuple(self._events)

    @property
    def output(self) -> object | None:
        """Return a defensive copy of the terminal output."""
        return deepcopy(self._output)

    @property
    def error(self) -> AgentErrorInfo | None:
        """Return structured terminal error information, when present."""
        return self._error

    @property
    def created_at(self) -> datetime:
        """Return the immutable creation timestamp."""
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        """Return the timestamp of the latest controlled mutation."""
        return self._updated_at

    @property
    def metadata(self) -> dict[str, object]:
        """Return an isolated copy of execution metadata."""
        return deepcopy(self._metadata)

    def transition_to(
        self,
        status: ExecutionStatus,
        *,
        reason: str | None = None,
        metadata: Mapping[str, object] | None = None,
        timestamp: datetime | None = None,
    ) -> ExecutionTransition:
        """Delegate a validated transition to the execution lifecycle."""
        if status is ExecutionStatus.FAILED and not self._lifecycle.is_terminal:
            raise ExecutionStateInvariantError(
                "Use fail() para registrar o erro obrigatório antes de encerrar."
            )
        mutation_time = self._mutation_timestamp(timestamp)
        transition = self._lifecycle.transition_to(
            status,
            reason=reason,
            metadata=metadata,
            timestamp=mutation_time,
        )
        self._updated_at = mutation_time
        return transition

    def add_message(self, message: ModelMessage) -> None:
        """Append one validated model message while the execution is active."""
        self._ensure_active()
        mutation_time = self._mutation_timestamp()
        self._messages.append(message)
        self._updated_at = mutation_time

    def set_model_selection(self, selection: ModelSelectionResult) -> None:
        """Record the immutable selection exactly once."""
        self._ensure_active()
        if self._model_selection is not None:
            raise ExecutionStateInvariantError(
                "A seleção de modelo não pode ser substituída nesta execução."
            )
        mutation_time = self._mutation_timestamp()
        self._model_selection = selection
        self._updated_at = mutation_time

    def increment_turn(self) -> None:
        """Increment the turn counter by exactly one."""
        self._ensure_active()
        mutation_time = self._mutation_timestamp()
        self._turn_count += 1
        self._updated_at = mutation_time

    def increment_tool_calls(self, count: int = 1) -> None:
        """Increment tool calls by a strictly positive count."""
        self._ensure_active()
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ExecutionStateInvariantError(
                "O incremento de chamadas de ferramenta deve ser inteiro e positivo."
            )
        mutation_time = self._mutation_timestamp()
        self._tool_call_count += count
        self._updated_at = mutation_time

    def add_model_usage(self, usage: ModelUsage) -> None:
        """Aggregate provider usage, propagating an unknown monetary cost."""
        self._ensure_active()
        mutation_time = self._mutation_timestamp()
        current_cost = self._usage.estimated_cost
        aggregate_cost: Decimal | None
        if not self._has_usage:
            aggregate_cost = usage.estimated_cost
        elif current_cost is None or usage.estimated_cost is None:
            aggregate_cost = None
        else:
            aggregate_cost = current_cost + usage.estimated_cost
        self._usage = Usage(
            input_tokens=self._usage.input_tokens + usage.input_tokens,
            output_tokens=self._usage.output_tokens + usage.output_tokens,
            cached_input_tokens=(
                self._usage.cached_input_tokens + usage.cached_input_tokens
            ),
            reasoning_tokens=self._usage.reasoning_tokens + usage.reasoning_tokens,
            estimated_cost=aggregate_cost,
        )
        self._has_usage = True
        self._updated_at = mutation_time

    def record_event(self, event: AgentEvent) -> None:
        """Append one event after validating execution identity and sequence."""
        if event.execution_id != self._execution_id:
            raise ExecutionStateInvariantError(
                "O evento deve pertencer à mesma execução do estado."
            )
        expected_sequence = len(self._events) + 1
        if event.sequence != expected_sequence:
            raise ExecutionStateInvariantError(
                "A sequência de eventos deve iniciar em 1 e ser contínua."
            )
        mutation_time = self._mutation_timestamp()
        self._events.append(event)
        self._updated_at = mutation_time

    def complete(self, output: object | None) -> None:
        """Store output and transition through the lifecycle to completed."""
        self._ensure_active()
        mutation_time = self._mutation_timestamp()
        transition = self._lifecycle.transition_to(
            ExecutionStatus.COMPLETED,
            timestamp=mutation_time,
        )
        self._output = deepcopy(output)
        self._error = None
        self._updated_at = transition.timestamp

    def fail(self, error: AgentErrorInfo) -> None:
        """Store a required structured error and transition to failed."""
        self._ensure_active()
        if error is None:
            raise ExecutionStateInvariantError(
                "Uma execução com falha deve informar um erro estruturado."
            )
        mutation_time = self._mutation_timestamp()
        transition = self._lifecycle.transition_to(
            ExecutionStatus.FAILED,
            timestamp=mutation_time,
        )
        self._error = error
        self._updated_at = transition.timestamp

    def cancel(self, *, reason: str | None = None) -> None:
        """Transition to cancelled while preserving an optional reason in history."""
        self._ensure_active()
        self.transition_to(ExecutionStatus.CANCELLED, reason=reason)

    def timeout(self, *, error: AgentErrorInfo | None = None) -> None:
        """Transition to timed out and optionally retain structured error details."""
        self._ensure_active()
        mutation_time = self._mutation_timestamp()
        transition = self._lifecycle.transition_to(
            ExecutionStatus.TIMED_OUT,
            timestamp=mutation_time,
        )
        self._error = error
        self._updated_at = transition.timestamp

    def exceed_limit(self, *, error: AgentErrorInfo) -> None:
        """Transition to limit exceeded and retain structured violation details."""
        self._terminate_by_policy(ExecutionStatus.LIMIT_EXCEEDED, error)

    def exceed_budget(self, *, error: AgentErrorInfo) -> None:
        """Transition to budget exceeded and retain structured violation details."""
        self._terminate_by_policy(ExecutionStatus.BUDGET_EXCEEDED, error)

    def snapshot(self) -> ExecutionSnapshot:
        """Create an isolated immutable observation of the current state."""
        return ExecutionSnapshot(
            execution_id=self._execution_id,
            agent_id=self._agent.agent_id,
            status=self.status,
            messages=self.messages,
            model_selection=self._model_selection,
            usage=self._usage,
            turn_count=self._turn_count,
            tool_call_count=self._tool_call_count,
            events=self.events,
            output=deepcopy(self._output),
            error=self._error,
            created_at=self._created_at,
            updated_at=self._updated_at,
            metadata=deepcopy(self._metadata),
        )

    def to_result(self) -> AgentResult[object]:
        """Create a public result only after the execution reaches terminal state."""
        if not is_terminal(self.status):
            raise ExecutionStateInvariantError(
                "O resultado só pode ser criado após o término da execução."
            )
        if self.status is ExecutionStatus.FAILED and self._error is None:
            raise ExecutionStateInvariantError(
                "Uma execução com falha deve possuir erro estruturado."
            )
        return AgentResult[object](
            execution_id=self._execution_id,
            status=self.status,
            output=deepcopy(self._output),
            usage=self._usage,
            events=self.events,
            error=self._error,
        )

    def _ensure_active(self) -> None:
        if self._lifecycle.is_terminal:
            raise ExecutionAlreadyTerminalError(
                "A execução já terminou e não aceita mutações operacionais."
            )

    def _terminate_by_policy(
        self,
        status: ExecutionStatus,
        error: AgentErrorInfo,
    ) -> None:
        self._ensure_active()
        mutation_time = self._mutation_timestamp()
        transition = self._lifecycle.transition_to(status, timestamp=mutation_time)
        self._error = error
        self._updated_at = transition.timestamp

    def _read_clock(self) -> datetime:
        try:
            return _timezone_aware(self._clock(), label="do estado de execução")
        except ValueError as exc:
            raise ExecutionStateInvariantError(
                "O relógio do estado deve produzir timestamps com fuso horário."
            ) from exc

    def _mutation_timestamp(self, timestamp: datetime | None = None) -> datetime:
        try:
            value = (
                self._read_clock()
                if timestamp is None
                else _timezone_aware(timestamp, label="da mutação")
            )
        except ValueError as exc:
            raise ExecutionStateInvariantError(
                "O timestamp da mutação deve possuir fuso horário."
            ) from exc
        if value < self._updated_at:
            raise ExecutionStateInvariantError(
                "O timestamp da mutação não pode retroceder no tempo."
            )
        return value


def _utc_now() -> datetime:
    return datetime.now(UTC)
