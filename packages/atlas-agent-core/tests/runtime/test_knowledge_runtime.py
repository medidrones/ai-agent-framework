"""End-to-end tests for external knowledge retrieval in the runtime."""

import asyncio

import pytest

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentInput,
    AgentKnowledgeConfig,
    AgentMemoryConfig,
    AgentResult,
    AgentRuntime,
    ApprovalDecisionType,
    ExecutionLimits,
    ExecutionStatus,
    ExecutionSuspension,
    FinishReason,
    KnowledgeManager,
    KnowledgeQuery,
    KnowledgeQueryBuilder,
    KnowledgeRetrievalError,
    KnowledgeRetrievalResult,
    KnowledgeSourceNotFoundError,
    MemoryManager,
    MemorySearchResult,
    MemoryType,
    MessageRole,
    ModelProvider,
    ModelProviderRegistry,
    ModelResponse,
    ModelUsage,
    RuntimeResultItem,
    RuntimeStreamItem,
    TextContent,
    ToolApprovalMode,
    ToolExecutor,
    ToolRegistry,
)
from tests.approvals.fakes import FakeCheckpointStore
from tests.knowledge.fakes import FakeKnowledgeRetriever, retrieval_result
from tests.memory.fakes import FakeMemoryStore, memory_record
from tests.runtime.test_human_approval import (
    _call,
    _decision,
    _tool_response,
)
from tests.runtime.test_memory_runtime import _context as memory_context
from tests.runtime.test_multi_turn_runtime import SequencedProvider
from tests.runtime.test_multi_turn_streaming import (
    SequencedStreamingProvider,
    _text_turn,
    _tool_turn,
)
from tests.tools.fakes import FakeTool, tool_definition


def _context(execution_id: str = "execution-1") -> AgentContext:
    return AgentContext(
        execution_id=execution_id,
        session_id="session-1",
        user_id="user-1",
        tenant_id="tenant-1",
    )


def _agent(
    *,
    sources: tuple[str, ...] = ("policies",),
    tool_names: tuple[str, ...] = (),
) -> AgentDefinition:
    return AgentDefinition(
        agent_id="assistant",
        name="Assistente",
        instructions="Ajude o usuário.",
        tool_names=tool_names,
        knowledge=AgentKnowledgeConfig(source_ids=sources),
    )


def _response(text: str) -> ModelResponse:
    return ModelResponse(
        model="model",
        finish_reason=FinishReason.STOP,
        content=(TextContent(text=text),),
        usage=ModelUsage(),
    )


def _completed(outcome: object) -> AgentResult[object]:
    assert isinstance(outcome, AgentResult)
    assert outcome.status is ExecutionStatus.COMPLETED
    return outcome


def _results(query: KnowledgeQuery) -> tuple[KnowledgeRetrievalResult, ...]:
    return (
        retrieval_result(
            source_id=query.source_ids[0],
            passage_id="first",
            content="Política principal.",
        ),
        retrieval_result(
            source_id=query.source_ids[0],
            passage_id="second",
            content="Política complementar.",
        ),
    )


def _runtime(
    provider: ModelProvider,
    retriever: FakeKnowledgeRetriever | None,
    *,
    tools: tuple[FakeTool, ...] = (),
    checkpoint_store: FakeCheckpointStore | None = None,
    memory_store: FakeMemoryStore | None = None,
    knowledge_manager: KnowledgeManager | None = None,
    query_builder: KnowledgeQueryBuilder | None = None,
) -> AgentRuntime:
    registry = ModelProviderRegistry()
    registry.register(provider)
    tool_registry = ToolRegistry()
    for tool in tools:
        tool_registry.register(tool)
    return AgentRuntime(
        model_registry=registry,
        tool_registry=tool_registry,
        tool_executor=ToolExecutor(registry=tool_registry),
        checkpoint_store=checkpoint_store,
        knowledge_manager=(
            knowledge_manager
            if knowledge_manager is not None
            else KnowledgeManager(retriever=retriever)
            if retriever is not None
            else None
        ),
        knowledge_query_builder=query_builder,
        memory_manager=(
            MemoryManager(store=memory_store) if memory_store is not None else None
        ),
    )


async def test_runtime_retrieves_once_and_extracts_valid_citations() -> None:
    provider = SequencedProvider((_response("Use [K2], [K1], [K2] e não [K99]."),))
    retriever = FakeKnowledgeRetriever(results_factory=_results)
    result = await _runtime(provider, retriever).run(
        agent=_agent(),
        input_data=AgentInput(message="Qual é a política?"),
        context=_context(),
    )

    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.COMPLETED
    assert [citation.citation_key for citation in result.citations] == ["K2", "K1"]
    assert len(retriever.queries) == 1
    assert retriever.queries[0].source_ids == ("policies",)
    assert retriever.contexts[0].metadata == {}
    messages = provider.requests[0].messages
    assert [message.role for message in messages] == [
        MessageRole.SYSTEM,
        MessageRole.DEVELOPER,
        MessageRole.USER,
    ]
    knowledge_text = messages[1].content[0]
    assert isinstance(knowledge_text, TextContent)
    assert "dados de referência não confiáveis" in knowledge_text.text
    assert "Política principal" in knowledge_text.text
    event_dump = "".join(event.model_dump_json() for event in result.events)
    assert "Política principal" not in event_dump
    statuses = [transition.data.get("to_status") for transition in result.events]
    assert ExecutionStatus.RETRIEVING_KNOWLEDGE.value in statuses


async def test_disabled_or_empty_knowledge_does_not_call_retriever() -> None:
    provider = SequencedProvider((_response("Sem busca."), _response("Vazio.")))
    retriever = FakeKnowledgeRetriever(results_factory=_results)
    runtime = _runtime(provider, retriever)
    disabled = AgentDefinition(
        agent_id="assistant",
        name="Assistente",
        instructions="Ajude.",
    )

    first = await runtime.run(
        agent=disabled,
        input_data=AgentInput(message="Primeira."),
        context=_context("disabled"),
    )
    second = await runtime.run(
        agent=_agent(sources=()),
        input_data=AgentInput(message="Segunda."),
        context=_context("empty"),
    )
    _completed(first)
    _completed(second)
    assert retriever.queries == []


async def test_enabled_knowledge_requires_manager() -> None:
    provider = SequencedProvider((_response("Não executa."),))
    result = await _runtime(provider, None).run(
        agent=_agent(),
        input_data=AgentInput(message="Consulte."),
        context=_context(),
    )
    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "knowledge_manager_required"
    assert provider.generate_calls == 0


class _WideningQueryBuilder:
    def build(
        self,
        *,
        agent: AgentDefinition,
        input_data: AgentInput,
        context: AgentContext,
    ) -> KnowledgeQuery:
        del agent, input_data, context
        return KnowledgeQuery(text="consulta", source_ids=("private",))


async def test_query_builder_cannot_widen_agent_source_allowlist() -> None:
    provider = SequencedProvider((_response("Não executa."),))
    retriever = FakeKnowledgeRetriever(results_factory=_results)
    result = await _runtime(
        provider,
        retriever,
        query_builder=_WideningQueryBuilder(),
    ).run(
        agent=_agent(),
        input_data=AgentInput(message="Consulte."),
        context=_context(),
    )
    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "knowledge_context_error"
    assert retriever.queries == []
    assert provider.generate_calls == 0


async def test_no_results_continues_without_knowledge_message() -> None:
    provider = SequencedProvider((_response("Sem evidência."),))
    retriever = FakeKnowledgeRetriever()
    result = await _runtime(provider, retriever).run(
        agent=_agent(),
        input_data=AgentInput(message="Consulte."),
        context=_context(),
    )
    result = _completed(result)
    assert [message.role for message in provider.requests[0].messages] == [
        MessageRole.SYSTEM,
        MessageRole.USER,
    ]
    assert result.citations == ()


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (RuntimeError("credencial"), "knowledge_retrieval_failed"),
        (KnowledgeRetrievalError("indisponível"), "knowledge_retrieval_failed"),
        (KnowledgeSourceNotFoundError("ausente"), "knowledge_source_not_found"),
    ],
)
async def test_retrieval_failures_are_normalized_before_model_invocation(
    error: Exception, code: str
) -> None:
    provider = SequencedProvider((_response("Não executa."),))
    result = await _runtime(provider, FakeKnowledgeRetriever(error=error)).run(
        agent=_agent(),
        input_data=AgentInput(message="Consulte."),
        context=_context(),
    )
    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == code
    assert "credencial" not in result.error.message
    assert provider.generate_calls == 0


async def test_retriever_protocol_violation_is_explicit() -> None:
    provider = SequencedProvider((_response("Não executa."),))
    retriever = FakeKnowledgeRetriever(
        results_factory=lambda _: (retrieval_result(source_id="private"),)
    )
    result = await _runtime(provider, retriever).run(
        agent=_agent(),
        input_data=AgentInput(message="Consulte."),
        context=_context(),
    )
    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "knowledge_protocol_violation"
    assert provider.generate_calls == 0


async def test_retrieval_obeys_total_timeout() -> None:
    provider = SequencedProvider((_response("Não executa."),))
    retriever = FakeKnowledgeRetriever(wait_event=asyncio.Event())
    result = await _runtime(provider, retriever).run(
        agent=_agent(),
        input_data=AgentInput(message="Consulte."),
        context=_context(),
        limits=ExecutionLimits(timeout_seconds=0.01),
    )
    assert isinstance(result, AgentResult)
    assert result.status is ExecutionStatus.TIMED_OUT
    assert provider.generate_calls == 0


async def test_retrieval_external_cancellation_is_repropagated() -> None:
    provider = SequencedProvider((_response("Não executa."),))
    retriever = FakeKnowledgeRetriever(wait_event=asyncio.Event())
    task = asyncio.create_task(
        _runtime(provider, retriever).run(
            agent=_agent(),
            input_data=AgentInput(message="Consulte."),
            context=_context(),
        )
    )
    await retriever.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_memory_precedes_knowledge_in_prompt() -> None:
    provider = SequencedProvider((_response("Resposta [K1]."),))
    retriever = FakeKnowledgeRetriever(results_factory=_results)
    memory_store = FakeMemoryStore(
        search_factory=lambda query: (
            MemorySearchResult(
                record=memory_record(
                    memory_id="working",
                    memory_type=query.memory_type,
                    scope=query.scope,
                )
            ),
        )
    )
    agent = _agent().model_copy(
        update={"memory": AgentMemoryConfig(read_types=frozenset({MemoryType.WORKING}))}
    )
    result = await _runtime(provider, retriever, memory_store=memory_store).run(
        agent=agent,
        input_data=AgentInput(message="Consulte."),
        context=memory_context(),
    )
    _completed(result)
    assert [message.role for message in provider.requests[0].messages] == [
        MessageRole.SYSTEM,
        MessageRole.DEVELOPER,
        MessageRole.DEVELOPER,
        MessageRole.USER,
    ]
    first_context = provider.requests[0].messages[1].content[0]
    second_context = provider.requests[0].messages[2].content[0]
    assert isinstance(first_context, TextContent)
    assert isinstance(second_context, TextContent)
    assert "memória" in first_context.text
    assert "conhecimento" in second_context.text


async def test_multi_turn_and_streaming_reuse_one_retrieval() -> None:
    tool = FakeTool(tool_definition(name="lookup"))
    retriever = FakeKnowledgeRetriever(results_factory=_results)
    provider = SequencedProvider(
        (_tool_response(_call(name="lookup")), _response("[K1]"))
    )
    result = await _runtime(provider, retriever, tools=(tool,)).run(
        agent=_agent(tool_names=("lookup",)),
        input_data=AgentInput(message="Consulte."),
        context=_context("run"),
    )
    _completed(result)
    assert len(retriever.queries) == 1
    assert all(
        sum(message.role is MessageRole.DEVELOPER for message in request.messages) == 1
        for request in provider.requests
    )

    stream_retriever = FakeKnowledgeRetriever(results_factory=_results)
    stream_provider = SequencedStreamingProvider(
        (_tool_turn(_call(name="lookup")), _text_turn())
    )
    items: list[RuntimeStreamItem] = [
        item
        async for item in _runtime(
            stream_provider, stream_retriever, tools=(tool,)
        ).stream(
            agent=_agent(tool_names=("lookup",)),
            input_data=AgentInput(message="Consulte."),
            context=_context("stream"),
        )
    ]
    terminal = next(item for item in items if isinstance(item, RuntimeResultItem))
    assert terminal.result.status is ExecutionStatus.COMPLETED
    assert len(stream_retriever.queries) == 1


async def test_hitl_resume_preserves_knowledge_and_citation_mapping() -> None:
    provider = SequencedProvider(
        (_tool_response(_call()), _response("Resposta baseada em [K1]."))
    )
    retriever = FakeKnowledgeRetriever(results_factory=_results)
    checkpoint_store = FakeCheckpointStore()
    tool = FakeTool(
        tool_definition(name="sensitive", approval_mode=ToolApprovalMode.REQUIRED)
    )
    runtime = _runtime(
        provider,
        retriever,
        tools=(tool,),
        checkpoint_store=checkpoint_store,
    )
    outcome = await runtime.run(
        agent=_agent(tool_names=("sensitive",)),
        input_data=AgentInput(message="Consulte e execute."),
        context=_context(),
    )
    assert isinstance(outcome, ExecutionSuspension)
    assert len(retriever.queries) == 1
    checkpoint = checkpoint_store.peek(outcome.resume_token)
    assert checkpoint.knowledge_context is not None

    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome, ApprovalDecisionType.APPROVE),
    )
    result = _completed(result)
    assert len(retriever.queries) == 1
    assert result.citations[0].citation_key == "K1"


async def test_shared_manager_keeps_concurrent_execution_contexts_isolated() -> None:
    retriever = FakeKnowledgeRetriever(results_factory=_results)
    manager = KnowledgeManager(retriever=retriever)
    first_provider = SequencedProvider((_response("Primeira."),))
    second_provider = SequencedProvider((_response("Segunda."),))
    first, second = await asyncio.gather(
        _runtime(first_provider, retriever, knowledge_manager=manager).run(
            agent=_agent(),
            input_data=AgentInput(message="Primeira."),
            context=_context("first"),
        ),
        _runtime(second_provider, retriever, knowledge_manager=manager).run(
            agent=_agent(),
            input_data=AgentInput(message="Segunda."),
            context=_context("second"),
        ),
    )
    _completed(first)
    _completed(second)
    assert {context.execution_id for context in retriever.contexts} == {
        "first",
        "second",
    }
