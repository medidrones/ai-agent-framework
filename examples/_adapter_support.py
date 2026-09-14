"""Shared host composition for official external-adapter examples."""

from atlas_agents import AgentDefinition, AgentRuntime, ExecutionLimits
from atlas_agents.adapters import (
    AgentExecutionService,
    AgentRegistry,
    AllowAllAgentAccessPolicy,
    BoundedExecutionPolicyResolver,
    InMemoryIdempotencyStore,
    SubjectExecutionIdentityMapper,
)


def build_execution_service(
    runtime: AgentRuntime,
    definition: AgentDefinition,
) -> AgentExecutionService:
    """Compose one transport-neutral service with explicit development policies."""
    registry = AgentRegistry()
    registry.register(definition)
    return AgentExecutionService(
        runtime=runtime,
        agent_registry=registry,
        identity_mapper=SubjectExecutionIdentityMapper(),
        access_policy=AllowAllAgentAccessPolicy(),
        policy_resolver=BoundedExecutionPolicyResolver(
            maximum_limits=ExecutionLimits(
                max_turns=8,
                max_tool_calls=4,
                timeout_seconds=30,
            )
        ),
        idempotency_store=InMemoryIdempotencyStore(),
        execution_id_factory=lambda: "example-execution",
    )
