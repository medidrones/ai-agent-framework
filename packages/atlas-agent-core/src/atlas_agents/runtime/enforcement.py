"""Pure provider-agnostic checks for execution limits and budgets."""

from atlas_agents.agents import Usage
from atlas_agents.runtime.budget import ExecutionBudget, ExecutionBudgetViolation
from atlas_agents.runtime.limits import (
    ExecutionLimitReason,
    ExecutionLimits,
    ExecutionLimitViolation,
)


class ExecutionLimitChecker:
    """Evaluate policies without mutating execution state or lifecycle."""

    @staticmethod
    def check_turn_allowed(
        *,
        limits: ExecutionLimits,
        current_turn_count: int,
    ) -> ExecutionLimitViolation | None:
        """Check whether one additional model invocation is allowed."""
        if limits.max_turns is None or current_turn_count < limits.max_turns:
            return None
        return ExecutionLimitViolation(
            reason=ExecutionLimitReason.MAX_TURNS,
            limit=limits.max_turns,
            observed=current_turn_count + 1,
        )

    @staticmethod
    def check_tool_call_allowed(
        *,
        limits: ExecutionLimits,
        current_tool_call_count: int,
    ) -> ExecutionLimitViolation | None:
        """Check whether one additional future tool execution is allowed."""
        if (
            limits.max_tool_calls is None
            or current_tool_call_count < limits.max_tool_calls
        ):
            return None
        return ExecutionLimitViolation(
            reason=ExecutionLimitReason.MAX_TOOL_CALLS,
            limit=limits.max_tool_calls,
            observed=current_tool_call_count + 1,
        )

    @staticmethod
    def check_usage(
        *,
        limits: ExecutionLimits,
        usage: Usage,
    ) -> ExecutionLimitViolation | None:
        """Return the first token violation in the documented precedence order."""
        checks = (
            (
                ExecutionLimitReason.MAX_INPUT_TOKENS,
                limits.max_input_tokens,
                usage.input_tokens,
            ),
            (
                ExecutionLimitReason.MAX_OUTPUT_TOKENS,
                limits.max_output_tokens,
                usage.output_tokens,
            ),
            (
                ExecutionLimitReason.MAX_TOTAL_TOKENS,
                limits.max_total_tokens,
                usage.total_tokens,
            ),
        )
        for reason, limit, observed in checks:
            if limit is not None and observed > limit:
                return ExecutionLimitViolation(
                    reason=reason,
                    limit=limit,
                    observed=observed,
                )
        return None

    @staticmethod
    def check_budget(
        *,
        budget: ExecutionBudget,
        usage: Usage,
    ) -> ExecutionBudgetViolation | None:
        """Check known cost without treating unknown cost as zero or failure."""
        limit = budget.max_estimated_cost
        observed = usage.estimated_cost
        if limit is None or observed is None or observed <= limit:
            return None
        return ExecutionBudgetViolation(limit=limit, observed=observed)
