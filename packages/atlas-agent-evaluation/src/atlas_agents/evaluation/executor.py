"""Adapter from the public production runtime API to evaluation observations."""

from atlas_agents import (
    AgentDefinition,
    AgentResult,
    AgentRuntime,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionSuspension,
    ModelSelectionRequest,
)
from atlas_agents.evaluation.case import EvaluationCase
from atlas_agents.evaluation.errors import EvaluationExecutionError
from atlas_agents.evaluation.evaluator import EvaluationContextFactory
from atlas_agents.evaluation.observation import (
    EvaluationCapturePolicy,
    EvaluationObservation,
)


class AgentRuntimeEvaluationExecutor:
    """Execute cases through the unchanged public `AgentRuntime.run` path."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        agent: AgentDefinition,
        context_factory: EvaluationContextFactory,
        model_selection: ModelSelectionRequest | None = None,
        limits: ExecutionLimits | None = None,
        budget: ExecutionBudget | None = None,
        capture_policy: EvaluationCapturePolicy | None = None,
    ) -> None:
        """Store explicit dependencies without modifying runtime behavior."""
        self._runtime = runtime
        self._agent = agent
        self._context_factory = context_factory
        self._model_selection = model_selection
        self._limits = limits
        self._budget = budget
        self._capture_policy = capture_policy or EvaluationCapturePolicy()

    async def execute(self, case: EvaluationCase) -> EvaluationObservation:
        """Run one case and map result or HITL suspension without auto-approval."""
        input_data = case.input.agent_input
        if input_data is None:
            raise EvaluationExecutionError(
                "O caso não possui AgentInput para execução."
            )
        outcome = await self._runtime.run(
            agent=self._agent,
            input_data=input_data,
            context=self._context_factory(case),
            model_selection=self._model_selection,
            limits=self._limits,
            budget=self._budget,
        )
        if isinstance(outcome, ExecutionSuspension):
            return EvaluationObservation.from_execution_suspension(
                outcome,
                agent_id=self._agent.agent_id,
            )
        if isinstance(outcome, AgentResult):
            return EvaluationObservation.from_agent_result(
                outcome,
                agent_id=self._agent.agent_id,
                capture_policy=self._capture_policy,
            )
        raise EvaluationExecutionError(
            "O runtime retornou um outcome incompatível com evaluation."
        )
