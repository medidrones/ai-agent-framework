"""Stable enumerations for human approval contracts."""

from enum import StrEnum


class ApprovalDecisionType(StrEnum):
    """Represent the only human decisions supported by the core."""

    APPROVE = "approve"
    REJECT = "reject"


class ApprovalKind(StrEnum):
    """Identify the operation governed by an approval request."""

    TOOL_EXECUTION = "tool_execution"


class ToolApprovalMode(StrEnum):
    """Declare a tool's baseline human approval behavior."""

    NOT_REQUIRED = "not_required"
    POLICY_CONTROLLED = "policy_controlled"
    REQUIRED = "required"
