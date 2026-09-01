"""Execution statuses shared by agent contracts."""

from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Represent the externally visible status of an agent execution."""

    CREATED = "created"
    VALIDATING_INPUT = "validating_input"
    LOADING_CONTEXT = "loading_context"
    RETRIEVING_KNOWLEDGE = "retrieving_knowledge"
    RUNNING = "running"
    WAITING_FOR_TOOL = "waiting_for_tool"
    EXECUTING_TOOL = "executing_tool"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    VALIDATING_OUTPUT = "validating_output"
    UPDATING_MEMORY = "updating_memory"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    LIMIT_EXCEEDED = "limit_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    REJECTED = "rejected"
