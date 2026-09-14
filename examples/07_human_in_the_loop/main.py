"""Suspend a tool call, approve it, and demonstrate rejection."""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas_agents import (
    AgentResult,
    ApprovalDecision,
    ApprovalDecisionType,
    ExecutionIdentity,
    ExecutionSuspension,
    ToolApprovalMode,
    ToolDefinition,
)

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import (
    InMemoryCheckpointStore,
    LocalTool,
    ScriptedModelProvider,
    agent,
    build_runtime,
    input_and_context,
    text_response,
    tool_response,
)


def _decision(
    suspension: ExecutionSuspension,
    decision: ApprovalDecisionType,
) -> ApprovalDecision:
    return ApprovalDecision(
        approval_request_id=suspension.approval_request.approval_request_id,
        decision=decision,
        decided_at=datetime.now(UTC),
        decided_by=ExecutionIdentity(subject="reviewer"),
        reason="Decisão explícita do exemplo.",
    )


def _refund_tool() -> LocalTool:
    return LocalTool(
        ToolDefinition(
            name="refund_payment",
            description="Simula um reembolso sem acessar serviço externo.",
            parameters={
                "type": "object",
                "properties": {"payment_id": {"type": "string"}},
                "required": ["payment_id"],
                "additionalProperties": False,
            },
            approval_mode=ToolApprovalMode.REQUIRED,
        ),
        lambda arguments: {"refunded": arguments["payment_id"]},
    )


async def _scenario(
    decision: ApprovalDecisionType,
) -> tuple[int, AgentResult[object]]:
    tool = _refund_tool()
    provider = ScriptedModelProvider(
        (
            tool_response("refund_payment", {"payment_id": "payment-demo"}),
            text_response("Reembolso simulado concluído."),
        )
    )
    runtime = build_runtime(
        provider,
        tools=(tool,),
        checkpoint_store=InMemoryCheckpointStore(),
    )
    input_data, context = input_and_context("Solicite o reembolso de demonstração.")
    outcome = await runtime.run(
        agent=agent(tools=("refund_payment",)),
        input_data=input_data,
        context=context,
    )
    if not isinstance(outcome, ExecutionSuspension) or tool.calls != 0:
        raise RuntimeError("A execução deveria suspender antes da ferramenta")
    result = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=_decision(outcome, decision),
    )
    if isinstance(result, ExecutionSuspension):
        raise RuntimeError("A retomada não deveria produzir outra suspensão.")
    return tool.calls, result


async def _run() -> None:
    approved_calls, approved = await _scenario(ApprovalDecisionType.APPROVE)
    rejected_calls, rejected = await _scenario(ApprovalDecisionType.REJECT)
    print(  # noqa: T201
        f"APROVAR: chamadas={approved_calls}, estado={approved.status.value}"
    )
    print(  # noqa: T201
        f"REJEITAR: chamadas={rejected_calls}, estado={rejected.status.value}"
    )


if __name__ == "__main__":
    asyncio.run(_run())
