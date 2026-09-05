"""Reusable test doubles for checkpoint and approval policies."""

import asyncio

from atlas_agents import (
    ApprovalContext,
    ApprovalNotRequired,
    ApprovalRequired,
    ApprovalRequirement,
    CheckpointNotFoundError,
    ExecutionCheckpoint,
    ResumeToken,
    ToolDefinition,
    ToolExecutionRequest,
)


class FakeCheckpointStore:
    def __init__(self, *, fail_save: bool = False) -> None:
        self._checkpoints: dict[str, ExecutionCheckpoint] = {}
        self._lock = asyncio.Lock()
        self.fail_save = fail_save
        self.save_calls = 0
        self.consume_calls = 0

    async def save(
        self,
        *,
        resume_token: ResumeToken,
        checkpoint: ExecutionCheckpoint,
    ) -> None:
        self.save_calls += 1
        if self.fail_save:
            raise RuntimeError("Falha de persistência simulada.")
        async with self._lock:
            self._checkpoints[resume_token.value] = checkpoint

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        self.consume_calls += 1
        async with self._lock:
            try:
                return self._checkpoints.pop(resume_token.value)
            except KeyError as error:
                raise CheckpointNotFoundError(
                    "O token é desconhecido ou já foi consumido."
                ) from error

    def peek(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        return self._checkpoints[resume_token.value]


class FixedApprovalPolicy:
    def __init__(self, *, required: bool) -> None:
        self.required = required
        self.call_count = 0

    def evaluate_tool(
        self,
        *,
        tool: ToolDefinition,
        request: ToolExecutionRequest,
        context: ApprovalContext,
    ) -> ApprovalRequirement:
        del tool, request, context
        self.call_count += 1
        if self.required:
            return ApprovalRequired(
                reason="A política exige revisão humana.",
                summary="Autorizar operação controlada?",
            )
        return ApprovalNotRequired()
