"""Validation contracts for externally supplied approval decisions."""

from typing import Protocol

from atlas_agents.approvals.decision import ApprovalDecision
from atlas_agents.approvals.errors import ApprovalDecisionMismatchError
from atlas_agents.approvals.request import ApprovalRequest


class ApprovalDecisionValidator(Protocol):
    """Validate whether a decision may resolve one approval request."""

    def validate(
        self,
        *,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> None:
        """Raise a safe approval error when the decision is unacceptable."""
        ...


class DefaultApprovalDecisionValidator:
    """Validate only request identity, leaving organization rules to adapters."""

    def validate(
        self,
        *,
        request: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> None:
        """Require the decision to target the exact pending request."""
        if decision.approval_request_id != request.approval_request_id:
            raise ApprovalDecisionMismatchError(
                "A decisão não corresponde à solicitação de aprovação pendente."
            )
