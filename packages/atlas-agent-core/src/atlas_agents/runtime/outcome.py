"""Public runtime outcome union."""

from atlas_agents.agents import AgentResult
from atlas_agents.approvals import ExecutionSuspension

type RuntimeOutcome = AgentResult[object] | ExecutionSuspension
