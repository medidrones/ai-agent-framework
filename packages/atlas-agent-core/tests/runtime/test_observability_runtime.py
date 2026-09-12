"""End-to-end tests for fail-open runtime observability."""

import asyncio
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import cast

import pytest

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentGuardrailConfig,
    AgentInput,
    AgentKnowledgeConfig,
    AgentMemoryConfig,
    AgentResult,
    AgentRuntime,
    ApprovalDecisionType,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionStatus,
    ExecutionSuspension,
    FinishReason,
    GuardrailDecision,
    GuardrailManager,
    GuardrailRegistry,
    GuardrailStage,
    KnowledgeManager,
    MemoryCandidate,
    MemoryManager,
    MemoryType,
    ModelProvider,
    ModelProviderRegistry,
    ObservabilityManager,
    RuntimeEventItem,
    RuntimeResultItem,
    RuntimeStreamItem,
    RuntimeSuspensionItem,
    SpanStatus,
    ToolApprovalMode,
    ToolOutput,
    ToolRegistry,
    TraceContext,
)
from tests.approvals.fakes import FakeCheckpointStore
from tests.guardrails.fakes import FakeGuardrail
from tests.knowledge.fakes import FakeKnowledgeRetriever, retrieval_result
from tests.memory.fakes import FakeMemoryStore, FixedMemoryWritePolicy
from tests.observability.fakes import FakeMetricsRecorder, FakeSpan, FakeTracer
from tests.runtime.test_agent_runtime import (
    _agent as simple_agent,
)
from tests.runtime.test_agent_runtime import (
    _provider,
    _response,
)
from tests.runtime.test_human_approval import _decision
from tests.runtime.test_multi_turn_runtime import (
    ConcurrentToolProvider,
    SequencedProvider,
    _call,
    _final_response,
    _tool_response,
)
from tests.runtime.test_multi_turn_runtime import (
    _agent as tool_agent,
)
from tests.runtime.test_multi_turn_streaming import (
    SequencedStreamingProvider,
    _text_turn,
    _tool_turn,
)
from tests.tools.fakes import FakeTool, tool_definition


def _runtime(
    provider: ModelProvider,
    tracer: FakeTracer,
    metrics: FakeMetricsRecorder,
    *,
    tools: tuple[FakeTool, ...] = (),
    store: FakeCheckpointStore | None = None,
    guardrails: tuple[FakeGuardrail, ...] = (),
) -> AgentRuntime:
    models = ModelProviderRegistry()
    models.register(provider)
    tool_registry = ToolRegistry()
    for tool in tools:
        tool_registry.register(tool)
    return AgentRuntime(
        model_registry=models,
        tool_registry=tool_registry,
        checkpoint_store=store,
        guardrail_manager=(
            GuardrailManager(GuardrailRegistry(guardrails)) if guardrails else None
        ),
        observability_manager=ObservabilityManager(
            tracer=tracer,
            metrics=metrics,
        ),
    )


async def _run_simple(
    runtime: AgentRuntime,
    *,
    execution_id: str = "execution",
    limits: ExecutionLimits | None = None,
    budget: ExecutionBudget | None = None,
    trace_context: TraceContext | None = None,
) -> AgentResult[object]:
    outcome = await runtime.run(
        agent=simple_agent(),
        input_data=AgentInput(
            message="segredo de entrada",
            metadata={"secret": "metadata secreta"},
        ),
        context=AgentContext(
            execution_id=execution_id,
            user_id="user-secret",
            session_id="session-secret",
            trace_context=trace_context,
            metadata={"secret": "contexto secreto"},
        ),
        limits=limits,
        budget=budget,
    )
    assert isinstance(outcome, AgentResult)
    return outcome


def _spans(tracer: FakeTracer, name: str) -> list[FakeSpan]:
    return [span for span in tracer.spans if span.name == name]


async def test_successful_run_records_root_selection_model_and_safe_metrics() -> None:
    tracer = FakeTracer()
    metrics = FakeMetricsRecorder()
    incoming = TraceContext(trace_id="incoming", span_id="parent")
    result = await _run_simple(
        _runtime(_provider(), tracer, metrics),
        trace_context=incoming,
    )

    assert result.status is ExecutionStatus.COMPLETED
    assert [span.name for span in tracer.spans] == [
        "atlas.agent.execution",
        "atlas.model.select",
        "atlas.model.generate",
    ]
    root, selection, model = tracer.spans
    assert root.parent == incoming
    assert root.statuses[-1] == (SpanStatus.OK, None)
    assert root.attributes["atlas.outcome"] == "completed"
    assert root.end_count == 1
    assert selection.parent == root.context
    assert model.parent == root.context
    assert model.attributes["atlas.model.turn"] == 1
    assert model.attributes["atlas.model.finish_reason"] == "stop"
    assert model.attributes["atlas.model.total_tokens"] == 30
    assert model.attributes["atlas.model.estimated_cost"] == "0.05"
    metric_names = [call.name for call in metrics.calls]
    assert "atlas.runtime.invocations" in metric_names
    assert "atlas.model.requests" in metric_names
    assert "atlas.model.duration" in metric_names
    assert "atlas.execution.duration" in metric_names
    assert "atlas.executions.terminal" in metric_names
    forbidden = {
        "execution_id",
        "trace_id",
        "request_id",
        "tool_call_id",
        "user_id",
        "session_id",
        "conversation_id",
    }
    assert all(not (forbidden & call.attributes.keys()) for call in metrics.calls)
    telemetry = repr((tracer.spans, metrics.calls))
    assert "segredo de entrada" not in telemetry
    assert "metadata secreta" not in telemetry
    assert "contexto secreto" not in telemetry
    assert "user-secret" not in telemetry
    assert "session-secret" not in telemetry


async def test_broken_telemetry_preserves_result_and_event_journal() -> None:
    plain = await _run_simple(
        _runtime(_provider(), FakeTracer(), FakeMetricsRecorder()),
        execution_id="same-execution",
    )
    broken = await _run_simple(
        _runtime(
            _provider(),
            FakeTracer(fail_operations=True),
            FakeMetricsRecorder(fail=True),
        ),
        execution_id="same-execution",
    )

    assert broken.status == plain.status
    assert broken.output == plain.output
    assert broken.usage == plain.usage
    assert broken.error == plain.error
    assert broken.citations == plain.citations
    assert [event.sequence for event in broken.events] == [
        event.sequence for event in plain.events
    ]
    assert [event.event_type for event in broken.events] == [
        event.event_type for event in plain.events
    ]
    assert [event.data for event in broken.events] == [
        event.data for event in plain.events
    ]


@pytest.mark.parametrize(
    ("finish_reason", "expected_status", "expected_outcome", "span_status"),
    [
        (
            FinishReason.CONTENT_FILTER,
            ExecutionStatus.REJECTED,
            "rejected",
            SpanStatus.OK,
        ),
        (FinishReason.ERROR, ExecutionStatus.FAILED, "failed", SpanStatus.ERROR),
    ],
)
async def test_root_outcome_mapping_for_rejection_and_failure(
    finish_reason: FinishReason,
    expected_status: ExecutionStatus,
    expected_outcome: str,
    span_status: SpanStatus,
) -> None:
    tracer = FakeTracer()
    result = await _run_simple(
        _runtime(
            _provider(response=_response(finish_reason)),
            tracer,
            FakeMetricsRecorder(),
        )
    )

    assert result.status is expected_status
    root = _spans(tracer, "atlas.agent.execution")[0]
    assert root.attributes["atlas.outcome"] == expected_outcome
    assert root.statuses[-1] == (span_status, None)
    assert root.end_count == 1


async def test_limit_budget_timeout_and_cancellation_span_mapping() -> None:
    limited_tracer = FakeTracer()
    limited = await _run_simple(
        _runtime(_provider(), limited_tracer, FakeMetricsRecorder()),
        limits=ExecutionLimits(max_total_tokens=1),
    )
    budget_tracer = FakeTracer()
    budgeted = await _run_simple(
        _runtime(_provider(), budget_tracer, FakeMetricsRecorder()),
        budget=ExecutionBudget(max_estimated_cost=Decimal("0.01")),
    )
    timeout_tracer = FakeTracer()
    timed_out = await _run_simple(
        _runtime(
            _provider(generate_delay_seconds=0.05),
            timeout_tracer,
            FakeMetricsRecorder(),
        ),
        limits=ExecutionLimits(timeout_seconds=0.001),
    )
    cancelled_tracer = FakeTracer()
    with pytest.raises(asyncio.CancelledError):
        await _run_simple(
            _runtime(
                _provider(generate_exception=asyncio.CancelledError()),
                cancelled_tracer,
                FakeMetricsRecorder(),
            )
        )

    assert limited.status is ExecutionStatus.LIMIT_EXCEEDED
    assert budgeted.status is ExecutionStatus.BUDGET_EXCEEDED
    assert timed_out.status is ExecutionStatus.TIMED_OUT
    expected = [
        (limited_tracer, "limit_exceeded", SpanStatus.OK),
        (budget_tracer, "budget_exceeded", SpanStatus.OK),
        (timeout_tracer, "timed_out", SpanStatus.ERROR),
        (cancelled_tracer, "cancelled", SpanStatus.UNSET),
    ]
    for tracer, outcome, status in expected:
        root = _spans(tracer, "atlas.agent.execution")[0]
        assert root.attributes["atlas.outcome"] == outcome
        assert root.statuses[-1] == (status, None)
        assert root.end_count == 1


async def test_stream_spans_complete_and_close_early_without_leaks() -> None:
    completed_tracer = FakeTracer()
    completed_metrics = FakeMetricsRecorder()
    provider = SequencedStreamingProvider((_text_turn(),))
    completed_runtime = _runtime(provider, completed_tracer, completed_metrics)
    items = [
        item
        async for item in completed_runtime.stream(
            agent=simple_agent(),
            input_data=AgentInput(message="stream secret"),
            context=AgentContext(execution_id="stream-completed"),
        )
    ]

    assert isinstance(items[-1], RuntimeResultItem)
    assert items[-1].result.status is ExecutionStatus.COMPLETED
    stream_span = _spans(completed_tracer, "atlas.model.stream")[0]
    assert stream_span.end_count == 1
    assert stream_span.attributes["atlas.model.stream.event_count"] == 4
    assert any(
        call.name == "atlas.model.stream.event_count"
        for call in completed_metrics.calls
    )
    assert _spans(completed_tracer, "atlas.agent.execution")[0].end_count == 1

    early_tracer = FakeTracer()
    early_runtime = _runtime(
        SequencedStreamingProvider((_text_turn(),)),
        early_tracer,
        FakeMetricsRecorder(),
    )
    iterator = cast(
        AsyncGenerator[RuntimeStreamItem, None],
        early_runtime.stream(
            agent=simple_agent(),
            input_data=AgentInput(message="stream secret"),
            context=AgentContext(execution_id="stream-closed"),
        ),
    )
    while True:
        item = await anext(iterator)
        if (
            isinstance(item, RuntimeEventItem)
            and item.event.event_type.value == "model_text_delta"
        ):
            break
    await iterator.aclose()

    assert _spans(early_tracer, "atlas.model.stream")[0].end_count == 1
    early_root = _spans(early_tracer, "atlas.agent.execution")[0]
    assert early_root.end_count == 1
    assert early_root.attributes["atlas.outcome"] == "cancelled"
    assert early_root.statuses[-1] == (SpanStatus.UNSET, None)


async def test_multi_turn_tool_execution_and_duplicate_replay_are_counted_once() -> (
    None
):
    call = _call(customer_id="sensitive-customer")
    provider = SequencedProvider(
        (_tool_response(call), _tool_response(call), _final_response("safe final"))
    )
    tool = FakeTool(
        tool_definition(),
        output=ToolOutput(content={"secret-result": "must-not-leak"}),
    )
    tracer = FakeTracer()
    metrics = FakeMetricsRecorder()
    result = await _runtime(
        provider,
        tracer,
        metrics,
        tools=(tool,),
    ).run(
        agent=tool_agent("get_customer"),
        input_data=AgentInput(message="execute"),
        context=AgentContext(execution_id="tools"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert len(_spans(tracer, "atlas.model.generate")) == 3
    tool_spans = _spans(tracer, "atlas.tool.execute")
    assert len(tool_spans) == 1
    assert tool_spans[0].statuses[-1] == (SpanStatus.OK, None)
    assert tool.call_count == 1
    assert (
        len([call for call in metrics.calls if call.name == "atlas.tool.executions"])
        == 1
    )
    telemetry = repr((tracer.spans, metrics.calls))
    assert "sensitive-customer" not in telemetry
    assert "must-not-leak" not in telemetry


async def test_denied_or_invalid_tool_does_not_create_execution_span() -> None:
    unknown = _call(name="unknown")
    provider = SequencedProvider((_tool_response(unknown), _final_response()))
    available = FakeTool(tool_definition(name="available"))
    tracer = FakeTracer()
    result = await _runtime(
        provider,
        tracer,
        FakeMetricsRecorder(),
        tools=(available,),
    ).run(
        agent=tool_agent("available"),
        input_data=AgentInput(message="execute"),
        context=AgentContext(execution_id="denied"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert _spans(tracer, "atlas.tool.execute") == []


async def test_tool_failure_marks_only_actual_execution_span_as_error() -> None:
    call = _call()
    provider = SequencedProvider((_tool_response(call), _final_response()))
    tool = FakeTool(tool_definition(), exception=RuntimeError("tool secret"))
    tracer = FakeTracer()
    result = await _runtime(
        provider,
        tracer,
        FakeMetricsRecorder(),
        tools=(tool,),
    ).run(
        agent=tool_agent("get_customer"),
        input_data=AgentInput(message="execute"),
        context=AgentContext(execution_id="tool-failure"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    tool_span = _spans(tracer, "atlas.tool.execute")[0]
    assert tool_span.statuses[-1] == (SpanStatus.ERROR, None)
    assert tool_span.exceptions == []
    assert "tool secret" not in repr(tracer.spans)


async def test_hitl_checkpoint_preserves_trace_and_resume_parent() -> None:
    call = _call(name="sensitive")
    provider = SequencedProvider((_tool_response(call), _final_response()))
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    store = FakeCheckpointStore()
    tracer = FakeTracer()
    metrics = FakeMetricsRecorder()
    runtime = _runtime(provider, tracer, metrics, tools=(tool,), store=store)
    outcome = await runtime.run(
        agent=tool_agent("sensitive"),
        input_data=AgentInput(message="execute"),
        context=AgentContext(execution_id="hitl"),
    )

    assert isinstance(outcome, ExecutionSuspension)
    first_root = _spans(tracer, "atlas.agent.execution")[0]
    assert first_root.attributes["atlas.outcome"] == "suspended"
    assert first_root.end_count == 1
    checkpoint = store.peek(outcome.resume_token)
    assert checkpoint.trace_context == first_root.context

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome, ApprovalDecisionType.APPROVE),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    roots = _spans(tracer, "atlas.agent.execution")
    assert len(roots) == 2
    assert roots[1].parent == first_root.context
    assert _spans(tracer, "atlas.checkpoint.save")[0].end_count == 1
    assert _spans(tracer, "atlas.checkpoint.consume")[0].end_count == 1
    telemetry = repr((tracer.spans, metrics.calls))
    assert outcome.resume_token.value not in telemetry


async def test_resume_stream_continues_trace_and_instruments_stream_mode() -> None:
    call = _call(name="sensitive")
    provider = SequencedStreamingProvider((_tool_turn(call), _text_turn()))
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    store = FakeCheckpointStore()
    tracer = FakeTracer()
    runtime = _runtime(
        provider,
        tracer,
        FakeMetricsRecorder(),
        tools=(tool,),
        store=store,
    )
    initial_items = [
        item
        async for item in runtime.stream(
            agent=tool_agent("sensitive"),
            input_data=AgentInput(message="execute"),
            context=AgentContext(execution_id="stream-hitl"),
        )
    ]
    suspension_item = next(
        item for item in initial_items if isinstance(item, RuntimeSuspensionItem)
    )
    first_root = _spans(tracer, "atlas.agent.execution")[0]

    resumed_items = [
        item
        async for item in runtime.resume_stream(
            resume_token=suspension_item.suspension.resume_token,
            decision=_decision(
                suspension_item.suspension,
                ApprovalDecisionType.APPROVE,
            ),
        )
    ]

    assert isinstance(resumed_items[-1], RuntimeResultItem)
    assert resumed_items[-1].result.status is ExecutionStatus.COMPLETED
    roots = _spans(tracer, "atlas.agent.execution")
    assert len(roots) == 2
    assert roots[1].parent == first_root.context
    assert roots[1].attributes["atlas.execution.mode"] == "stream"
    assert roots[1].attributes["atlas.execution.resumed"] is True
    assert all(root.end_count == 1 for root in roots)


async def test_memory_and_knowledge_instrumentation_is_content_free() -> None:
    memory_store = FakeMemoryStore()
    write_policy = FixedMemoryWritePolicy(
        (
            MemoryCandidate(
                memory_type=MemoryType.LONG_TERM,
                content="memory write secret",
            ),
        )
    )
    retriever = FakeKnowledgeRetriever(
        results_factory=lambda query: (
            retrieval_result(
                source_id=query.source_ids[0],
                content="knowledge passage secret",
            ),
        )
    )
    provider = SequencedProvider((_final_response("final output secret"),))
    models = ModelProviderRegistry()
    models.register(provider)
    tracer = FakeTracer()
    metrics = FakeMetricsRecorder()
    runtime = AgentRuntime(
        model_registry=models,
        memory_manager=MemoryManager(store=memory_store),
        memory_write_policy=write_policy,
        knowledge_manager=KnowledgeManager(retriever=retriever),
        observability_manager=ObservabilityManager(
            tracer=tracer,
            metrics=metrics,
        ),
    )
    agent = AgentDefinition(
        agent_id="assistant",
        name="Assistente",
        instructions="Ajude.",
        memory=AgentMemoryConfig(
            read_types=frozenset({MemoryType.LONG_TERM}),
            write_types=frozenset({MemoryType.LONG_TERM}),
        ),
        knowledge=AgentKnowledgeConfig(source_ids=("policies",)),
    )

    result = await runtime.run(
        agent=agent,
        input_data=AgentInput(message="memory query secret"),
        context=AgentContext(
            execution_id="memory-knowledge",
            user_id="sensitive-user",
        ),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert len(_spans(tracer, "atlas.memory.retrieve")) == 1
    assert len(_spans(tracer, "atlas.memory.write")) == 1
    assert len(_spans(tracer, "atlas.knowledge.retrieve")) == 1
    telemetry = repr((tracer.spans, metrics.calls))
    assert "memory query secret" not in telemetry
    assert "memory write secret" not in telemetry
    assert "knowledge passage secret" not in telemetry
    assert "final output secret" not in telemetry
    assert "sensitive-user" not in telemetry
    assert "urn:policy:cancellation" not in telemetry


async def test_guardrail_pipeline_spans_are_stage_level_and_rejection_is_ok() -> None:
    input_guardrail = FakeGuardrail("input", GuardrailStage.INPUT)
    final_guardrail = FakeGuardrail("final", GuardrailStage.FINAL_OUTPUT)
    reject_guardrail = FakeGuardrail(
        "reject",
        GuardrailStage.INPUT,
        decision=GuardrailDecision.REJECT,
    )
    tracer = FakeTracer()
    metrics = FakeMetricsRecorder()
    runtime = _runtime(
        _provider(),
        tracer,
        metrics,
        guardrails=(input_guardrail, final_guardrail),
    )
    agent = simple_agent().model_copy(
        update={
            "guardrails": AgentGuardrailConfig(
                input_guardrails=("input",),
                final_output_guardrails=("final",),
            )
        }
    )
    result = await runtime.run(
        agent=agent,
        input_data=AgentInput(message="guarded secret"),
        context=AgentContext(execution_id="guarded"),
    )

    assert isinstance(result, AgentResult)
    guardrail_spans = _spans(tracer, "atlas.guardrail.evaluate")
    assert [span.attributes["atlas.guardrail.stage"] for span in guardrail_spans] == [
        "input",
        "final_output",
    ]
    assert all(span.statuses[-1] == (SpanStatus.OK, None) for span in guardrail_spans)
    assert (
        len(
            [
                call
                for call in metrics.calls
                if call.name == "atlas.guardrail.evaluations"
            ]
        )
        == 2
    )

    reject_tracer = FakeTracer()
    rejected = await _runtime(
        _provider(),
        reject_tracer,
        FakeMetricsRecorder(),
        guardrails=(reject_guardrail,),
    ).run(
        agent=simple_agent().model_copy(
            update={"guardrails": AgentGuardrailConfig(input_guardrails=("reject",))}
        ),
        input_data=AgentInput(message="rejected secret"),
        context=AgentContext(execution_id="rejected"),
    )
    assert isinstance(rejected, AgentResult)
    assert rejected.status is ExecutionStatus.REJECTED
    rejected_span = _spans(reject_tracer, "atlas.guardrail.evaluate")[0]
    assert rejected_span.attributes["atlas.guardrail.decision"] == "reject"
    assert rejected_span.statuses[-1] == (SpanStatus.OK, None)


async def test_guardrail_exception_is_fail_closed_without_raw_exception_telemetry() -> (
    None
):
    guardrail = FakeGuardrail(
        "failure",
        GuardrailStage.INPUT,
        exception=RuntimeError("guardrail secret"),
    )
    tracer = FakeTracer()
    result = await _runtime(
        _provider(),
        tracer,
        FakeMetricsRecorder(),
        guardrails=(guardrail,),
    ).run(
        agent=simple_agent().model_copy(
            update={"guardrails": AgentGuardrailConfig(input_guardrails=("failure",))}
        ),
        input_data=AgentInput(message="guarded"),
        context=AgentContext(execution_id="guardrail-failure"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.FAILED
    guardrail_span = _spans(tracer, "atlas.guardrail.evaluate")[0]
    assert guardrail_span.statuses[-1] == (SpanStatus.ERROR, None)
    assert guardrail_span.exceptions == []
    assert "guardrail secret" not in repr(tracer.spans)


async def test_concurrent_executions_keep_root_contexts_isolated() -> None:
    provider = ConcurrentToolProvider()
    tool = FakeTool(tool_definition())
    tracer = FakeTracer()
    metrics = FakeMetricsRecorder()
    runtime = _runtime(provider, tracer, metrics, tools=(tool,))

    async def execute(execution_id: str) -> AgentResult[object]:
        outcome = await runtime.run(
            agent=tool_agent("get_customer"),
            input_data=AgentInput(message="execute"),
            context=AgentContext(
                execution_id=execution_id,
                trace_context=TraceContext(
                    trace_id=f"parent-{execution_id}",
                    span_id="parent",
                ),
            ),
        )
        assert isinstance(outcome, AgentResult)
        return outcome

    first, second = await asyncio.gather(execute("first"), execute("second"))

    assert first.output == "first"
    assert second.output == "second"
    roots = _spans(tracer, "atlas.agent.execution")
    assert {span.attributes["atlas.execution.id"] for span in roots} == {
        "first",
        "second",
    }
    assert {span.parent.trace_id for span in roots if span.parent is not None} == {
        "parent-first",
        "parent-second",
    }
    assert all(span.end_count == 1 for span in roots)
