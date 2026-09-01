"""Execution statuses shared by agent contracts."""

from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Represent the externally visible status of an agent execution."""

    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    LIMIT_EXCEEDED = "limit_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    REJECTED = "rejected"
