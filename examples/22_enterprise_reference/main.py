"""Run the consolidated deterministic enterprise reference scenario."""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas_agents import (
    AgentContext,
    AgentDefinition,
    AgentGuardrailConfig,
    AgentInput,
    AgentKnowledgeConfig,
    AgentMemoryConfig,
    ApprovalDecision,
    ApprovalDecisionType,
    ExecutionIdentity,
    ExecutionStatus,
    ExecutionSuspension,
    GuardrailContext,
    GuardrailDecision,
    GuardrailManager,
    GuardrailRegistry,
    GuardrailResult,
    GuardrailStage,
    KnowledgeDocument,
    KnowledgeManager,
    KnowledgePassage,
    KnowledgeQuery,
    KnowledgeRetrievalContext,
    KnowledgeRetrievalResult,
    KnowledgeSource,
    MemoryManager,
    MemoryScope,
    MemoryType,
    MemoryWriteRequest,
    ObservabilityManager,
    ToolApprovalMode,
    ToolDefinition,
    ToolRegistry,
)
from atlas_agents.config import load_yaml
from atlas_agents.evaluation import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationExpectation,
    EvaluationObservation,
    EvaluationRunner,
    EvaluatorRegistry,
    ExactMatchEvaluator,
)
from atlas_agents.mcp import (
    MCPClient,
    MCPToolImporter,
    StdioMCPTransport,
    StdioMCPTransportConfig,
)

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import (
    InMemoryCheckpointStore,
    InMemoryMemoryStore,
    LocalTool,
    RecordingMetrics,
    RecordingTracer,
    ScriptedModelProvider,
    build_runtime,
    text_response,
    tool_response,
)


class SupportKnowledgeRetriever:
    """Return the approved deterministic support policy."""

    async def sources(self) -> tuple[KnowledgeSource, ...]:
        """Describe the only allowlisted knowledge source."""
        return (KnowledgeSource(source_id="support-policy", name="Política"),)

    async def retrieve(
        self,
        query: KnowledgeQuery,
        context: KnowledgeRetrievalContext,
    ) -> tuple[KnowledgeRetrievalResult, ...]:
        """Return a policy passage without network access."""
        del query, context
        return (
            KnowledgeRetrievalResult(
                passage=KnowledgePassage(
                    passage_id="compensation",
                    document=KnowledgeDocument(
                        document_id="support-policy-v1",
                        source_id="support-policy",
                        title="Política de compensação",
                        uri="atlas.yaml",
                    ),
                    content=(
                        "Pedidos com três dias de atraso podem receber compensação "
                        "após aprovação humana."
                    ),
                )
            ),
        )


class PassThroughGuardrail:
    """Allow typed values while proving both configured runtime boundaries."""

    def __init__(self, guardrail_id: str, stage: GuardrailStage) -> None:
        """Store the configured identity and boundary."""
        self._guardrail_id = guardrail_id
        self._stage = stage
        self.calls = 0

    @property
    def guardrail_id(self) -> str:
        """Return the stable configured ID."""
        return self._guardrail_id

    @property
    def stage(self) -> GuardrailStage:
        """Return the exact enforcement boundary."""
        return self._stage

    async def evaluate(
        self,
        value: object,
        context: GuardrailContext,
    ) -> GuardrailResult[object]:
        """Allow this fixture while recording that enforcement occurred."""
        del context
        self.calls += 1
        return GuardrailResult(
            guardrail_id=self.guardrail_id,
            stage=self.stage,
            decision=GuardrailDecision.ALLOW,
            output=value,
        )


async def _evaluate(output: object) -> bool:
    expected = "Pedido 1234 atrasado; compensação preparada [K1]."
    report = await EvaluationRunner(
        registry=EvaluatorRegistry((ExactMatchEvaluator(),))
    ).evaluate_dataset(
        dataset=EvaluationDataset(
            dataset_id="enterprise-reference",
            name="Cenário corporativo",
            version="1",
            cases=(
                EvaluationCase(
                    case_id="delayed-order",
                    name="Pedido atrasado",
                    expectations=(
                        EvaluationExpectation(
                            expectation_id="exact-output",
                            evaluator_id="exact-output",
                            expected=expected,
                        ),
                    ),
                ),
            ),
        ),
        observations={
            "delayed-order": EvaluationObservation(
                execution_id="enterprise-execution",
                agent_id="enterprise-support",
                status=ExecutionStatus.COMPLETED,
                output=str(output),
            )
        },
        evaluation_run_id="enterprise-evaluation",
    )
    return report.summary.passed_case_count == 1


async def _run() -> None:
    config = load_yaml(
        Path(__file__).with_name("atlas.yaml").read_text(encoding="utf-8")
    )
    if "enterprise-support" not in config.agents:
        raise RuntimeError("O agente declarativo não foi carregado.")

    transport = StdioMCPTransport(
        StdioMCPTransportConfig(
            command=sys.executable,
            args=(str(Path(__file__).with_name("server.py")),),
        )
    )
    async with MCPClient(transport) as client:
        imported_registry = ToolRegistry()
        remote_tools = await MCPToolImporter(
            client=client,
            registry=imported_registry,
            server_alias="local",
        ).import_tools(include_names=frozenset({"order_status"}))
        compensation = LocalTool(
            ToolDefinition(
                name="request_compensation",
                description="Simula o registro de uma compensação.",
                parameters={
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                    "additionalProperties": False,
                },
                approval_mode=ToolApprovalMode.REQUIRED,
            ),
            lambda arguments: {
                "order_id": arguments["order_id"],
                "compensation": "prepared",
            },
        )
        provider = ScriptedModelProvider(
            (
                tool_response(
                    "local__order_status",
                    {"order_id": "1234"},
                    tool_call_id="order-call",
                ),
                tool_response(
                    "request_compensation",
                    {"order_id": "1234"},
                    tool_call_id="compensation-call",
                ),
                text_response("Pedido 1234 atrasado; compensação preparada [K1]."),
            )
        )
        memory_store = InMemoryMemoryStore()
        memory_manager = MemoryManager(store=memory_store)
        scope = MemoryScope(
            agent_id="enterprise-support",
            user_id="customer-1",
            session_id="support-session",
        )
        await memory_manager.remember(
            MemoryWriteRequest(
                memory_type=MemoryType.CONVERSATION,
                scope=scope,
                content="O usuário prefere respostas objetivas.",
            )
        )
        input_guardrail = PassThroughGuardrail("safe-input", GuardrailStage.INPUT)
        output_guardrail = PassThroughGuardrail(
            "safe-output", GuardrailStage.FINAL_OUTPUT
        )
        guardrails = GuardrailManager(
            GuardrailRegistry((input_guardrail, output_guardrail))
        )
        tracer = RecordingTracer()
        metrics = RecordingMetrics()
        runtime = build_runtime(
            provider,
            tools=(*remote_tools, compensation),
            checkpoint_store=InMemoryCheckpointStore(),
            memory_manager=memory_manager,
            knowledge_manager=KnowledgeManager(retriever=SupportKnowledgeRetriever()),
            guardrail_manager=guardrails,
            observability_manager=ObservabilityManager(
                tracer=tracer,
                metrics=metrics,
            ),
        )
        definition = AgentDefinition(
            agent_id="enterprise-support",
            name="Agente corporativo de suporte",
            instructions="Use somente fontes autorizadas e ferramentas allowlisted.",
            tool_names=("local__order_status", "request_compensation"),
            memory=AgentMemoryConfig(read_types=frozenset({MemoryType.CONVERSATION})),
            knowledge=AgentKnowledgeConfig(source_ids=("support-policy",)),
            guardrails=AgentGuardrailConfig(
                input_guardrails=("safe-input",),
                final_output_guardrails=("safe-output",),
            ),
        )
        context = AgentContext(
            execution_id="enterprise-execution",
            session_id="support-session",
            user_id="customer-1",
            identity=ExecutionIdentity(subject="customer-1"),
        )
        outcome = await runtime.run(
            agent=definition,
            input_data=AgentInput(
                message=(
                    "Verifique o status do pedido 1234 e, se estiver atrasado, "
                    "prepare uma solicitação de compensação."
                )
            ),
            context=context,
        )
        if not isinstance(outcome, ExecutionSuspension):
            raise RuntimeError("O pedido deveria aguardar aprovação humana.")
        result = await runtime.resume(
            resume_token=outcome.resume_token,
            decision=ApprovalDecision(
                approval_request_id=(outcome.approval_request.approval_request_id),
                decision=ApprovalDecisionType.APPROVE,
                decided_at=datetime.now(UTC),
                decided_by=ExecutionIdentity(subject="reviewer-1"),
                reason="Compensação autorizada no cenário local.",
            ),
        )
    print(f"Status: {result.status.value}")  # noqa: T201
    print(f"Saída: {result.output}")  # noqa: T201
    print(f"Citações: {len(result.citations)}")  # noqa: T201
    print(f"HITL executou a ferramenta: {compensation.calls == 1}")  # noqa: T201
    print(f"Guardrails executados: {input_guardrail.calls + output_guardrail.calls}")  # noqa: T201
    print(f"Spans registrados: {len(tracer.spans)}")  # noqa: T201
    print(f"Avaliação aprovada: {await _evaluate(result.output)}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
