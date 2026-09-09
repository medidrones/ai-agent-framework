"""End-to-end tests for guardrail enforcement in the agent runtime."""

import asyncio

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
    ExecutionLimits,
    ExecutionStatus,
    ExecutionSuspension,
    FinalOutputGuardrailInput,
    FinishReason,
    GuardrailDecision,
    GuardrailEnforcement,
    GuardrailManager,
    GuardrailRegistry,
    GuardrailStage,
    InputGuardrailInput,
    KnowledgeManager,
    MemoryCandidate,
    MemoryManager,
    MemoryType,
    MessageRole,
    ModelOutputGuardrailInput,
    ModelProviderRegistry,
    ModelResponse,
    ModelUsage,
    RuntimeEventItem,
    RuntimeResultItem,
    TextContent,
    ToolApprovalMode,
    ToolCallGuardrailInput,
    ToolOutput,
    ToolRegistry,
    ToolResultGuardrailInput,
)
from tests.approvals.fakes import FakeCheckpointStore
from tests.guardrails.fakes import FakeGuardrail
from tests.knowledge.fakes import FakeKnowledgeRetriever, retrieval_result
from tests.memory.fakes import FakeMemoryStore, FixedMemoryWritePolicy
from tests.runtime.test_human_approval import _call, _decision, _tool_response
from tests.runtime.test_multi_turn_runtime import SequencedProvider
from tests.runtime.test_multi_turn_streaming import (
    SequencedStreamingProvider,
    _text_turn,
)
from tests.tools.fakes import FakeTool, tool_definition


def _final(text: str = "Resposta final.") -> ModelResponse:
    return ModelResponse(
        model="model",
        content=(TextContent(text=text),),
        finish_reason=FinishReason.STOP,
        usage=ModelUsage(input_tokens=2, output_tokens=1, total_tokens=3),
    )


def _agent(
    config: AgentGuardrailConfig,
    *,
    tools: tuple[str, ...] = (),
) -> AgentDefinition:
    return AgentDefinition(
        agent_id="assistant",
        name="Assistente",
        instructions="Ajude o usuário.",
        tool_names=tools,
        guardrails=config,
    )


def _runtime(
    provider: SequencedProvider,
    guardrails: tuple[FakeGuardrail, ...],
    *,
    tools: tuple[FakeTool, ...] = (),
    checkpoint_store: FakeCheckpointStore | None = None,
) -> AgentRuntime:
    models = ModelProviderRegistry()
    models.register(provider)
    tool_registry = ToolRegistry()
    for tool in tools:
        tool_registry.register(tool)
    return AgentRuntime(
        model_registry=models,
        tool_registry=tool_registry,
        checkpoint_store=checkpoint_store,
        guardrail_manager=GuardrailManager(GuardrailRegistry(guardrails)),
    )


async def test_input_transform_preserves_original_and_reaches_provider() -> None:
    def redact(value: object) -> object:
        assert isinstance(value, InputGuardrailInput)
        return value.model_copy(
            update={
                "input_data": value.input_data.model_copy(
                    update={"message": "mensagem protegida"}
                )
            }
        )

    guardrail = FakeGuardrail(
        "input-redaction",
        GuardrailStage.INPUT,
        decision=GuardrailDecision.TRANSFORM,
        transform=redact,
    )
    provider = SequencedProvider((_final(),))
    result = await _runtime(provider, (guardrail,)).run(
        agent=_agent(AgentGuardrailConfig(input_guardrails=("input-redaction",))),
        input_data=AgentInput(message="segredo"),
        context=AgentContext(execution_id="execution"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    user_message = provider.requests[0].messages[-1]
    assert user_message.role is MessageRole.USER
    assert user_message.content == (TextContent(text="mensagem protegida"),)
    evaluated = guardrail.values[0]
    assert isinstance(evaluated, InputGuardrailInput)
    assert evaluated.input_data.message == "segredo"
    event_dump = "".join(event.model_dump_json() for event in result.events)
    assert "segredo" not in event_dump
    assert "mensagem protegida" not in event_dump


async def test_input_reject_stops_before_provider_and_manager_is_required() -> None:
    reject = FakeGuardrail(
        "reject-input",
        GuardrailStage.INPUT,
        decision=GuardrailDecision.REJECT,
    )
    provider = SequencedProvider((_final(),))
    agent = _agent(AgentGuardrailConfig(input_guardrails=("reject-input",)))
    rejected = await _runtime(provider, (reject,)).run(
        agent=agent,
        input_data=AgentInput(message="blocked"),
        context=AgentContext(execution_id="reject"),
    )

    assert isinstance(rejected, AgentResult)
    assert rejected.status is ExecutionStatus.REJECTED
    assert rejected.error is not None
    assert rejected.error.code == "input_guardrail_rejected"
    assert provider.generate_calls == 0

    models = ModelProviderRegistry()
    models.register(provider)
    failed = await AgentRuntime(model_registry=models).run(
        agent=agent,
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="missing"),
    )
    assert isinstance(failed, AgentResult)
    assert failed.status is ExecutionStatus.FAILED
    assert failed.error is not None
    assert failed.error.code == "guardrail_manager_required"


async def test_invalid_and_wrong_stage_config_fail_before_provider() -> None:
    provider = SequencedProvider((_final(), _final()))
    input_guardrail = FakeGuardrail("input", GuardrailStage.INPUT)
    runtime = _runtime(provider, (input_guardrail,))
    unknown = await runtime.run(
        agent=_agent(AgentGuardrailConfig(input_guardrails=("unknown",))),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="unknown"),
    )
    mismatch = await runtime.run(
        agent=_agent(AgentGuardrailConfig(final_output_guardrails=("input",))),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="mismatch"),
    )

    assert isinstance(unknown, AgentResult)
    assert unknown.error is not None
    assert unknown.error.code == "guardrail_not_registered"
    assert isinstance(mismatch, AgentResult)
    assert mismatch.error is not None
    assert mismatch.error.code == "guardrail_stage_mismatch"
    assert provider.generate_calls == 0


async def test_guardrail_exception_fails_closed_and_cancellation_propagates() -> None:
    failing = FakeGuardrail(
        "failure",
        GuardrailStage.INPUT,
        exception=RuntimeError("sensitive detail"),
    )
    provider = SequencedProvider((_final(),))
    result = await _runtime(provider, (failing,)).run(
        agent=_agent(AgentGuardrailConfig(input_guardrails=("failure",))),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="failure"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "guardrail_evaluation_failed"
    assert "sensitive" not in result.model_dump_json()

    slow = FakeGuardrail("slow", GuardrailStage.INPUT, delay=1)
    task = asyncio.create_task(
        _runtime(provider, (slow,)).run(
            agent=_agent(AgentGuardrailConfig(input_guardrails=("slow",))),
            input_data=AgentInput(message="test"),
            context=AgentContext(execution_id="cancel"),
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_runtime_deadline_covers_guardrail_evaluation() -> None:
    slow = FakeGuardrail("slow", GuardrailStage.INPUT, delay=0.05)
    result = await _runtime(SequencedProvider((_final(),)), (slow,)).run(
        agent=_agent(AgentGuardrailConfig(input_guardrails=("slow",))),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="timeout"),
        limits=ExecutionLimits(timeout_seconds=0.001),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.TIMED_OUT


async def test_model_and_final_output_transformations_and_rejections() -> None:
    def transform_model(value: object) -> object:
        assert isinstance(value, ModelOutputGuardrailInput)
        response = value.response.model_copy(
            update={"content": (TextContent(text="modelo transformado"),)}
        )
        return value.model_copy(update={"response": response})

    def transform_final(value: object) -> object:
        assert isinstance(value, FinalOutputGuardrailInput)
        return value.model_copy(update={"output": "saída protegida"})

    model_guard = FakeGuardrail(
        "model",
        GuardrailStage.MODEL_OUTPUT,
        decision=GuardrailDecision.TRANSFORM,
        transform=transform_model,
    )
    final_guard = FakeGuardrail(
        "final",
        GuardrailStage.FINAL_OUTPUT,
        decision=GuardrailDecision.TRANSFORM,
        transform=transform_final,
    )
    result = await _runtime(
        SequencedProvider((_final("original"),)), (model_guard, final_guard)
    ).run(
        agent=_agent(
            AgentGuardrailConfig(
                model_output_guardrails=("model",),
                final_output_guardrails=("final",),
            )
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="transform"),
    )

    assert isinstance(result, AgentResult)
    assert result.output == "saída protegida"
    assert result.usage.total_tokens == 3

    reject = FakeGuardrail(
        "reject-model",
        GuardrailStage.MODEL_OUTPUT,
        decision=GuardrailDecision.REJECT,
    )
    rejected = await _runtime(SequencedProvider((_final(),)), (reject,)).run(
        agent=_agent(AgentGuardrailConfig(model_output_guardrails=("reject-model",))),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="model-reject"),
    )
    assert isinstance(rejected, AgentResult)
    assert rejected.status is ExecutionStatus.REJECTED
    assert rejected.usage.total_tokens == 3


async def test_tool_call_transform_revalidates_and_tool_result_transforms() -> None:
    def transform_call(value: object) -> object:
        assert isinstance(value, ToolCallGuardrailInput)
        call = value.tool_call.model_copy(
            update={"arguments": {"customer_id": "guarded"}}
        )
        return value.model_copy(update={"tool_call": call})

    def transform_result(value: object) -> object:
        assert isinstance(value, ToolResultGuardrailInput)
        result = value.tool_result.model_copy(
            update={"output": ToolOutput(content={"value": "redacted"})}
        )
        return value.model_copy(update={"tool_result": result})

    call_guard = FakeGuardrail(
        "call",
        GuardrailStage.TOOL_CALL,
        decision=GuardrailDecision.TRANSFORM,
        transform=transform_call,
    )
    result_guard = FakeGuardrail(
        "result",
        GuardrailStage.TOOL_RESULT,
        decision=GuardrailDecision.TRANSFORM,
        transform=transform_result,
    )
    tool = FakeTool(tool_definition(name="sensitive"))
    provider = SequencedProvider((_tool_response(_call()), _final()))
    result = await _runtime(provider, (call_guard, result_guard), tools=(tool,)).run(
        agent=_agent(
            AgentGuardrailConfig(
                tool_call_guardrails=("call",),
                tool_result_guardrails=("result",),
            ),
            tools=("sensitive",),
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="tools"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert tool.calls[0][0] == {"customer_id": "guarded"}
    tool_message = provider.requests[1].messages[-1]
    assert "redacted" in tool_message.model_dump_json()


async def test_tool_call_operation_reject_returns_safe_denial() -> None:
    reject = FakeGuardrail(
        "deny-call",
        GuardrailStage.TOOL_CALL,
        decision=GuardrailDecision.REJECT,
        enforcement=GuardrailEnforcement.OPERATION,
    )
    tool = FakeTool(tool_definition(name="sensitive"))
    provider = SequencedProvider((_tool_response(_call()), _final()))
    result = await _runtime(provider, (reject,), tools=(tool,)).run(
        agent=_agent(
            AgentGuardrailConfig(tool_call_guardrails=("deny-call",)),
            tools=("sensitive",),
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="deny-tool"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert tool.call_count == 0
    assert "tool_call_guardrail_rejected" in provider.requests[1].model_dump_json()


async def test_invalid_tool_call_transformation_fails_without_execution() -> None:
    def invalid(value: object) -> object:
        assert isinstance(value, ToolCallGuardrailInput)
        call = value.tool_call.model_copy(update={"arguments": {}})
        return value.model_copy(update={"tool_call": call})

    guardrail = FakeGuardrail(
        "invalid",
        GuardrailStage.TOOL_CALL,
        decision=GuardrailDecision.TRANSFORM,
        transform=invalid,
    )
    tool = FakeTool(tool_definition(name="sensitive"))
    result = await _runtime(
        SequencedProvider((_tool_response(_call()),)),
        (guardrail,),
        tools=(tool,),
    ).run(
        agent=_agent(
            AgentGuardrailConfig(tool_call_guardrails=("invalid",)),
            tools=("sensitive",),
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="invalid-tool"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "guardrail_invalid_transformation"
    assert tool.call_count == 0


async def test_tool_result_operation_and_execution_rejections() -> None:
    tool = FakeTool(tool_definition(name="sensitive"))
    operation = FakeGuardrail(
        "deny-result",
        GuardrailStage.TOOL_RESULT,
        decision=GuardrailDecision.REJECT,
        enforcement=GuardrailEnforcement.OPERATION,
    )
    completed = await _runtime(
        SequencedProvider((_tool_response(_call()), _final())),
        (operation,),
        tools=(tool,),
    ).run(
        agent=_agent(
            AgentGuardrailConfig(tool_result_guardrails=("deny-result",)),
            tools=("sensitive",),
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="result-operation"),
    )
    assert isinstance(completed, AgentResult)
    assert completed.status is ExecutionStatus.COMPLETED

    execution = FakeGuardrail(
        "reject-result",
        GuardrailStage.TOOL_RESULT,
        decision=GuardrailDecision.REJECT,
    )
    rejected = await _runtime(
        SequencedProvider((_tool_response(_call("call-2")),)),
        (execution,),
        tools=(tool,),
    ).run(
        agent=_agent(
            AgentGuardrailConfig(tool_result_guardrails=("reject-result",)),
            tools=("sensitive",),
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="result-execution"),
    )
    assert isinstance(rejected, AgentResult)
    assert rejected.status is ExecutionStatus.REJECTED


async def test_effective_input_is_used_by_memory_and_knowledge() -> None:
    def redact(value: object) -> object:
        assert isinstance(value, InputGuardrailInput)
        return value.model_copy(
            update={
                "input_data": value.input_data.model_copy(
                    update={"message": "consulta protegida"}
                )
            }
        )

    guardrail = FakeGuardrail(
        "redact",
        GuardrailStage.INPUT,
        decision=GuardrailDecision.TRANSFORM,
        transform=redact,
    )
    memory = FakeMemoryStore()
    knowledge = FakeKnowledgeRetriever()
    models = ModelProviderRegistry()
    provider = SequencedProvider((_final(),))
    models.register(provider)
    runtime = AgentRuntime(
        model_registry=models,
        memory_manager=MemoryManager(store=memory),
        knowledge_manager=KnowledgeManager(retriever=knowledge),
        guardrail_manager=GuardrailManager(GuardrailRegistry((guardrail,))),
    )
    agent = AgentDefinition(
        agent_id="assistant",
        name="Assistente",
        instructions="Ajude.",
        memory=AgentMemoryConfig(read_types=frozenset({MemoryType.CONVERSATION})),
        knowledge=AgentKnowledgeConfig(source_ids=("policies",)),
        guardrails=AgentGuardrailConfig(input_guardrails=("redact",)),
    )
    result = await runtime.run(
        agent=agent,
        input_data=AgentInput(message="segredo original"),
        context=AgentContext(
            execution_id="effective-context",
            session_id="session",
            user_id="user",
        ),
    )

    assert isinstance(result, AgentResult)
    assert memory.searches[0].text == "consulta protegida"
    assert knowledge.queries[0].text == "consulta protegida"


async def test_duplicate_tool_replay_reuses_guarded_result() -> None:
    call_guard = FakeGuardrail("call", GuardrailStage.TOOL_CALL)
    result_guard = FakeGuardrail("result", GuardrailStage.TOOL_RESULT)
    tool = FakeTool(tool_definition(name="sensitive"))
    call = _call()
    provider = SequencedProvider((_tool_response(call), _tool_response(call), _final()))
    result = await _runtime(
        provider,
        (call_guard, result_guard),
        tools=(tool,),
    ).run(
        agent=_agent(
            AgentGuardrailConfig(
                tool_call_guardrails=("call",),
                tool_result_guardrails=("result",),
            ),
            tools=("sensitive",),
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="replay"),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert tool.call_count == 1
    assert len(call_guard.values) == 1
    assert len(result_guard.values) == 1


async def test_hitl_checkpoint_preserves_guardrail_and_does_not_rerun() -> None:
    def transform(value: object) -> object:
        assert isinstance(value, ToolCallGuardrailInput)
        return value.model_copy(
            update={
                "tool_call": value.tool_call.model_copy(
                    update={"arguments": {"customer_id": "guarded"}}
                )
            }
        )

    call_guard = FakeGuardrail(
        "call",
        GuardrailStage.TOOL_CALL,
        decision=GuardrailDecision.TRANSFORM,
        transform=transform,
    )
    input_guard = FakeGuardrail(
        "input",
        GuardrailStage.INPUT,
        decision=GuardrailDecision.TRANSFORM,
        transform=lambda value: (
            value.model_copy(
                update={
                    "input_data": value.input_data.model_copy(
                        update={"message": "guarded input"}
                    )
                }
            )
            if isinstance(value, InputGuardrailInput)
            else value
        ),
    )
    store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(
            name="sensitive",
            approval_mode=ToolApprovalMode.REQUIRED,
        )
    )
    runtime = _runtime(
        SequencedProvider((_tool_response(_call()), _final())),
        (input_guard, call_guard),
        tools=(tool,),
        checkpoint_store=store,
    )
    suspended = await runtime.run(
        agent=_agent(
            AgentGuardrailConfig(
                input_guardrails=("input",),
                tool_call_guardrails=("call",),
            ),
            tools=("sensitive",),
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(execution_id="hitl"),
    )

    assert isinstance(suspended, ExecutionSuspension)
    checkpoint = store.peek(suspended.resume_token)
    assert checkpoint.guardrail_records[-1].guardrail_id == "call"
    assert checkpoint.input_data.message == "test"
    assert checkpoint.effective_input is not None
    assert checkpoint.effective_input.message == "guarded input"
    assert checkpoint.pending_tool_calls[0].arguments == {"customer_id": "guarded"}
    resumed = await runtime.resume(
        resume_token=suspended.resume_token,
        decision=_decision(suspended),
    )
    assert isinstance(resumed, AgentResult)
    assert resumed.status is ExecutionStatus.COMPLETED
    assert len(call_guard.values) == 1
    assert tool.call_count == 1
    assert tool.calls[0][0] == {"customer_id": "guarded"}


async def test_streaming_guardrail_rejects_only_after_emitted_deltas() -> None:
    reject = FakeGuardrail(
        "final",
        GuardrailStage.FINAL_OUTPUT,
        decision=GuardrailDecision.REJECT,
    )
    provider = SequencedStreamingProvider((_text_turn(),))
    models = ModelProviderRegistry()
    models.register(provider)
    runtime = AgentRuntime(
        model_registry=models,
        guardrail_manager=GuardrailManager(GuardrailRegistry((reject,))),
    )
    items = [
        item
        async for item in runtime.stream(
            agent=_agent(AgentGuardrailConfig(final_output_guardrails=("final",))),
            input_data=AgentInput(message="test"),
            context=AgentContext(execution_id="stream-reject"),
        )
    ]

    assert any(
        isinstance(item, RuntimeEventItem)
        and item.event.event_type.value == "model_text_delta"
        for item in items
    )
    final = next(item for item in items if isinstance(item, RuntimeResultItem))
    assert final.result.status is ExecutionStatus.REJECTED


async def test_final_transform_recalculates_citations_before_memory_write() -> None:
    def remove_citation(value: object) -> object:
        assert isinstance(value, FinalOutputGuardrailInput)
        return value.model_copy(update={"output": "resposta protegida"})

    guardrail = FakeGuardrail(
        "final",
        GuardrailStage.FINAL_OUTPUT,
        decision=GuardrailDecision.TRANSFORM,
        transform=remove_citation,
    )
    memory = FakeMemoryStore()
    write_policy = FixedMemoryWritePolicy(
        (MemoryCandidate(memory_type=MemoryType.CONVERSATION, content="registro"),)
    )
    knowledge = FakeKnowledgeRetriever(results_factory=lambda _: (retrieval_result(),))
    models = ModelProviderRegistry()
    models.register(SequencedProvider((_final("resposta [K1]"),)))
    runtime = AgentRuntime(
        model_registry=models,
        memory_manager=MemoryManager(store=memory),
        memory_write_policy=write_policy,
        knowledge_manager=KnowledgeManager(retriever=knowledge),
        guardrail_manager=GuardrailManager(GuardrailRegistry((guardrail,))),
    )
    result = await runtime.run(
        agent=AgentDefinition(
            agent_id="assistant",
            name="Assistente",
            instructions="Ajude.",
            memory=AgentMemoryConfig(write_types=frozenset({MemoryType.CONVERSATION})),
            knowledge=AgentKnowledgeConfig(source_ids=("policies",)),
            guardrails=AgentGuardrailConfig(final_output_guardrails=("final",)),
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(
            execution_id="final-memory",
            session_id="session",
            user_id="user",
        ),
    )

    assert isinstance(result, AgentResult)
    assert result.output == "resposta protegida"
    assert result.citations == ()
    assert write_policy.outputs == ["resposta protegida"]
    assert len(memory.writes) == 1


async def test_final_reject_prevents_memory_write() -> None:
    reject = FakeGuardrail(
        "reject-final",
        GuardrailStage.FINAL_OUTPUT,
        decision=GuardrailDecision.REJECT,
    )
    memory = FakeMemoryStore()
    write_policy = FixedMemoryWritePolicy(
        (MemoryCandidate(memory_type=MemoryType.CONVERSATION, content="registro"),)
    )
    models = ModelProviderRegistry()
    models.register(SequencedProvider((_final("não persistir"),)))
    runtime = AgentRuntime(
        model_registry=models,
        memory_manager=MemoryManager(store=memory),
        memory_write_policy=write_policy,
        guardrail_manager=GuardrailManager(GuardrailRegistry((reject,))),
    )
    result = await runtime.run(
        agent=AgentDefinition(
            agent_id="assistant",
            name="Assistente",
            instructions="Ajude.",
            memory=AgentMemoryConfig(write_types=frozenset({MemoryType.CONVERSATION})),
            guardrails=AgentGuardrailConfig(final_output_guardrails=("reject-final",)),
        ),
        input_data=AgentInput(message="test"),
        context=AgentContext(
            execution_id="final-reject",
            session_id="session",
            user_id="user",
        ),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.REJECTED
    assert result.output is None
    assert write_policy.calls == 0
    assert memory.writes == []
