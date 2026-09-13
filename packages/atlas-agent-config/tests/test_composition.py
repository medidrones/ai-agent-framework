from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from config_test_support import (
    FailingResource,
    FakeAdapter,
    FakeApprovalProviderFactory,
    FakePlugin,
    FakeProviderFactory,
    FakeResource,
    FakeToolFactory,
    registry_with_all,
)

from atlas_agents.adapters import (
    AllowAllAgentAccessPolicy,
    BoundedExecutionPolicyResolver,
    SubjectExecutionIdentityMapper,
)
from atlas_agents.agents import (
    AgentContext,
    AgentInput,
    ExecutionIdentity,
    ExecutionStatus,
)
from atlas_agents.approvals import (
    ApprovalDecision,
    ApprovalDecisionType,
    ExecutionSuspension,
    ResumeToken,
)
from atlas_agents.config import (
    AtlasCompositionBuilder,
    ComponentFactoryNotFoundError,
    CompositionBuildError,
    CompositionCloseError,
    ConfigReferenceError,
    ConfigurationFactoryRegistry,
    ConfigValidationError,
    ExternalExecutionDependencies,
    MappingSecretResolver,
    RuntimeDependencies,
    load_yaml,
)
from atlas_agents.runtime import ExecutionCheckpoint, ExecutionLimits


def external_dependencies() -> ExternalExecutionDependencies:
    return ExternalExecutionDependencies(
        identity_mapper=SubjectExecutionIdentityMapper(),
        access_policy=AllowAllAgentAccessPolicy(),
        policy_resolver=BoundedExecutionPolicyResolver(
            maximum_limits=ExecutionLimits(max_turns=10, timeout_seconds=60)
        ),
    )


FULL_CONFIG = """
schema_version: 1
atlas:
  default_limits:
    max_turns: 4
providers:
  fake:
    type: fake_provider
tools:
  lookup:
    type: fake_tool
memory:
  local:
    type: fake_memory
knowledge:
  company:
    type: fake_knowledge
    source_ids: [docs]
guardrails:
  safe-input:
    type: fake_guardrail
observability:
  local:
    type: fake_observability
mcp:
  internal:
    type: fake_mcp
    enabled: true
    import_tools:
      include: []
adapters:
  api:
    type: fake_adapter
    enabled: true
agents:
  assistant:
    name: Assistente
    instructions: Responda com clareza.
    model:
      provider: fake
      model: fake-model
      required_capabilities: [text_generation]
    tools: [lookup]
    memory:
      read_types: [working]
    knowledge:
      sources: [docs]
    guardrails:
      input: [safe-input]
"""


@pytest.mark.asyncio
async def test_full_yaml_builds_operational_runtime_and_subsystems() -> None:
    registry, provider_factory, tool_factory, mcp_factory = registry_with_all()
    builder = AtlasCompositionBuilder(
        factories=registry,
        external_execution_dependencies=external_dependencies(),
        atlas_version="0.1.0",
    )
    composition = await builder.build(load_yaml(FULL_CONFIG))
    agent = composition.agent_registry.get("assistant")
    result = await composition.runtime.run(
        agent=agent,
        input_data=AgentInput(message="Olá"),
        context=AgentContext(execution_id="execution-1"),
        model_selection=composition.model_selections["assistant"],
    )
    assert result.status is ExecutionStatus.COMPLETED
    assert provider_factory.calls == 1
    assert tool_factory.calls == 1
    assert composition.memory_manager is not None
    assert composition.knowledge_manager is not None
    assert composition.guardrail_registry.get("safe-input") is not None
    assert composition.execution_service is not None
    assert composition.adapters[0].component_id == "api"
    adapter = composition.adapters[0]
    assert isinstance(adapter, FakeAdapter)
    assert adapter.started is False
    assert composition.mcp_integrations[0].component_id == "internal"
    assert mcp_factory.includes == ()
    await composition.close()


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self.checkpoints: dict[str, ExecutionCheckpoint] = {}

    async def save(
        self, *, resume_token: ResumeToken, checkpoint: ExecutionCheckpoint
    ) -> None:
        self.checkpoints[resume_token.value] = checkpoint

    async def consume(self, resume_token: ResumeToken) -> ExecutionCheckpoint:
        return self.checkpoints.pop(resume_token.value)


@pytest.mark.asyncio
async def test_configured_hitl_suspends_and_resumes_execution() -> None:
    registry = ConfigurationFactoryRegistry()
    registry.register_provider_factory(FakeApprovalProviderFactory())
    registry.register_tool_factory(FakeToolFactory())
    checkpoint_store = InMemoryCheckpointStore()
    composition = await AtlasCompositionBuilder(
        factories=registry,
        runtime_dependencies=RuntimeDependencies(checkpoint_store=checkpoint_store),
        atlas_version="0.1.0",
    ).build(
        load_yaml(
            """
schema_version: 1
providers:
  fake: {type: approval_provider}
tools:
  sensitive:
    type: fake_tool
    config: {approval_required: true}
agents:
  assistant:
    name: Assistente
    instructions: Execute com aprovação.
    model: {provider: fake, model: fake-model}
    tools: [sensitive]
"""
        )
    )
    outcome = await composition.runtime.run(
        agent=composition.agent_registry.get("assistant"),
        input_data=AgentInput(message="Execute."),
        context=AgentContext(execution_id="hitl-1"),
        model_selection=composition.model_selections["assistant"],
    )
    assert isinstance(outcome, ExecutionSuspension)
    result = await composition.runtime.resume(
        resume_token=outcome.resume_token,
        decision=ApprovalDecision(
            approval_request_id=outcome.approval_request.approval_request_id,
            decision=ApprovalDecisionType.APPROVE,
            decided_at=datetime.now(UTC),
            decided_by=ExecutionIdentity(subject="supervisor"),
        ),
    )
    assert not isinstance(result, ExecutionSuspension)
    assert result.status is ExecutionStatus.COMPLETED
    assert result.output == "Operação aprovada"
    await composition.close()


@pytest.mark.asyncio
async def test_secure_defaults_build_no_optional_components() -> None:
    registry, _, _, mcp = registry_with_all()
    composition = await AtlasCompositionBuilder(
        factories=registry,
        atlas_version="0.1.0",
    ).build(
        load_yaml(
            """
schema_version: 1
providers:
  fake: {type: fake_provider}
agents:
  assistant:
    name: Assistente
    instructions: Ajude.
"""
        )
    )
    agent = composition.agent_registry.get("assistant")
    assert agent.tool_names == ()
    assert agent.memory is None
    assert agent.knowledge is None
    assert agent.guardrails is None
    assert composition.adapters == ()
    assert composition.mcp_integrations == ()
    assert mcp.includes is None
    await composition.close()


@pytest.mark.asyncio
async def test_disabled_components_are_not_constructed() -> None:
    registry, provider, tool, mcp = registry_with_all()
    config = load_yaml(
        """
schema_version: 1
providers:
  fake: {type: fake_provider, enabled: false}
tools:
  lookup: {type: fake_tool, enabled: false}
mcp:
  server: {type: fake_mcp, enabled: false}
adapters:
  api: {type: fake_adapter}
"""
    )
    composition = await AtlasCompositionBuilder(
        factories=registry,
        atlas_version="0.1.0",
    ).build(config)
    assert provider.calls == 0
    assert tool.calls == 0
    assert mcp.includes is None
    assert composition.adapters == ()
    await composition.close()


@pytest.mark.asyncio
async def test_reference_validation_happens_before_any_factory() -> None:
    registry = ConfigurationFactoryRegistry()
    provider = FakeProviderFactory()
    registry.register_provider_factory(provider)
    config = load_yaml(
        """
schema_version: 1
providers:
  fake: {type: fake_provider}
agents:
  assistant:
    name: Assistente
    instructions: Ajude.
    tools: [missing]
"""
    )
    with pytest.raises(ConfigReferenceError):
        await AtlasCompositionBuilder(factories=registry, atlas_version="0.1.0").build(
            config
        )
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_all_factories_are_preflighted_before_construction() -> None:
    registry = ConfigurationFactoryRegistry()
    provider = FakeProviderFactory()
    registry.register_provider_factory(provider)
    config = load_yaml(
        """
schema_version: 1
providers:
  fake: {type: fake_provider}
tools:
  missing: {type: missing_factory}
"""
    )
    with pytest.raises(ComponentFactoryNotFoundError):
        await AtlasCompositionBuilder(factories=registry, atlas_version="0.1.0").build(
            config
        )
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_factory_specific_validation_precedes_construction() -> None:
    registry = ConfigurationFactoryRegistry()
    provider = FakeProviderFactory()
    registry.register_provider_factory(provider)
    config = load_yaml(
        """
schema_version: 1
providers:
  fake:
    type: fake_provider
    config: {invalid: true}
"""
    )
    with pytest.raises(ConfigValidationError):
        await AtlasCompositionBuilder(factories=registry, atlas_version="0.1.0").build(
            config
        )
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_adapters_require_explicit_external_security_policies() -> None:
    registry, _, _, _ = registry_with_all()
    config = load_yaml(
        "schema_version: 1\nadapters:\n  api: {type: fake_adapter, enabled: true}\n"
    )
    with pytest.raises(ConfigValidationError, match="políticas externas"):
        await AtlasCompositionBuilder(
            factories=registry,
            atlas_version="0.1.0",
        ).build(config)


@pytest.mark.asyncio
async def test_component_output_identity_mismatch_fails_safely() -> None:
    registry = ConfigurationFactoryRegistry()
    registry.register_provider_factory(FakeProviderFactory(returned_id="other"))
    with pytest.raises(CompositionBuildError) as captured:
        await AtlasCompositionBuilder(factories=registry, atlas_version="0.1.0").build(
            load_yaml(
                "schema_version: 1\nproviders:\n  expected: {type: fake_provider}\n"
            )
        )
    assert captured.value.path == "$.providers.expected"


@pytest.mark.asyncio
async def test_fake_openai_factory_does_not_leak_secret() -> None:
    secret = "PROVIDER-SECRET"  # noqa: S105

    class FakeOpenAIFactory(FakeProviderFactory):
        type_name = "openai"

    factory = FakeOpenAIFactory()
    registry = ConfigurationFactoryRegistry()
    registry.register_provider_factory(factory)
    composition = await AtlasCompositionBuilder(
        factories=registry,
        secret_resolver=MappingSecretResolver({"openai/key": secret}),
        atlas_version="0.1.0",
    ).build(
        load_yaml(
            "schema_version: 1\nproviders:\n  openai:\n"
            "    type: openai\n"
            "    config:\n      api_key: {secret_ref: openai/key}\n"
        )
    )
    assert factory.resolved_secret_repr == "SecretValue(********)"  # noqa: S105
    assert secret not in composition.config.model_dump_json()
    assert secret not in composition.configuration_fingerprint
    await composition.close()


@pytest.mark.asyncio
async def test_partial_build_failure_closes_owned_resources() -> None:
    order: list[str] = []
    first = FakeResource("first", order)
    registry = ConfigurationFactoryRegistry()
    registry.register_provider_factory(FakeProviderFactory(resource=first))
    registry.register_tool_factory(FakeToolFactory(fail=True))
    config = load_yaml(
        """
schema_version: 1
providers:
  fake: {type: fake_provider}
tools:
  tool: {type: fake_tool}
"""
    )
    with pytest.raises(CompositionBuildError) as captured:
        await AtlasCompositionBuilder(factories=registry, atlas_version="0.1.0").build(
            config
        )
    assert first.close_calls == 1
    assert order == ["first"]
    assert "detalhe" not in str(captured.value)


@pytest.mark.asyncio
async def test_composition_close_is_reverse_order_and_idempotent() -> None:
    order: list[str] = []
    first = FakeResource("first", order)
    second = FakeResource("second", order)
    registry = ConfigurationFactoryRegistry()
    registry.register_provider_factory(FakeProviderFactory(resource=first))

    class SecondProviderFactory(FakeProviderFactory):
        type_name = "second_provider"

    registry.register_provider_factory(SecondProviderFactory(resource=second))
    composition = await AtlasCompositionBuilder(
        factories=registry, atlas_version="0.1.0"
    ).build(
        load_yaml(
            """
schema_version: 1
providers:
  first: {type: fake_provider}
  second: {type: second_provider}
"""
        )
    )
    await composition.close()
    await composition.close()
    assert order == ["second", "first"]
    assert composition.closed is True


@pytest.mark.asyncio
async def test_close_attempts_remaining_cleanup_after_failure() -> None:
    order: list[str] = []
    failing = FailingResource("failing", order)
    final = FakeResource("final", order)
    registry = ConfigurationFactoryRegistry()
    registry.register_provider_factory(FakeProviderFactory(resource=final))

    class FailingProviderFactory(FakeProviderFactory):
        type_name = "failing_provider"

    registry.register_provider_factory(FailingProviderFactory(resource=failing))
    composition = await AtlasCompositionBuilder(
        factories=registry, atlas_version="0.1.0"
    ).build(
        load_yaml(
            """
schema_version: 1
providers:
  final: {type: fake_provider}
  failing: {type: failing_provider}
"""
        )
    )
    with pytest.raises(CompositionCloseError):
        await composition.close()
    assert order == ["failing", "final"]
    await composition.close()


@pytest.mark.asyncio
async def test_plugin_activation_is_explicit_and_secret_safe() -> None:
    plugin = FakePlugin()
    secret = "PLUGIN-SECRET"  # noqa: S105
    config = load_yaml(
        """
schema_version: 1
plugins:
  acme.plugin:
    config:
      api_key: {secret_ref: plugin/key}
plugin_activation: [acme.plugin]
agents:
  assistant:
    name: Assistente
    instructions: Ajude.
"""
    )
    composition = await AtlasCompositionBuilder(
        factories=ConfigurationFactoryRegistry(),
        plugins=(plugin,),
        secret_resolver=MappingSecretResolver({"plugin/key": secret}),
        atlas_version="0.1.0",
    ).build(config)
    assert plugin.activate_calls == 1
    assert plugin.secret_seen == secret
    assert secret not in repr(composition.config)
    assert secret not in composition.config.model_dump_json()
    assert secret not in composition.configuration_fingerprint
    await composition.close()
    assert plugin.deactivate_calls == 1


@pytest.mark.asyncio
async def test_registered_but_undeclared_plugin_is_never_activated() -> None:
    plugin = FakePlugin()
    composition = await AtlasCompositionBuilder(
        factories=ConfigurationFactoryRegistry(),
        plugins=(plugin,),
        atlas_version="0.1.0",
    ).build(load_yaml("schema_version: 1\n"))
    assert plugin.activate_calls == 0
    await composition.close()
    assert plugin.deactivate_calls == 0


@pytest.mark.asyncio
async def test_declared_plugin_must_be_registered_by_host() -> None:
    config = load_yaml(
        """
schema_version: 1
plugins:
  missing: {}
plugin_activation: [missing]
"""
    )
    with pytest.raises(ConfigReferenceError, match="não foi registrado"):
        await AtlasCompositionBuilder(
            factories=ConfigurationFactoryRegistry(), atlas_version="0.1.0"
        ).build(config)


@pytest.mark.asyncio
async def test_async_context_manager_closes_composition() -> None:
    registry, _, _, _ = registry_with_all()
    async with await AtlasCompositionBuilder(
        factories=registry,
        atlas_version="0.1.0",
    ).build(load_yaml("schema_version: 1\n")) as composition:
        assert composition.closed is False
    assert composition.closed is True


class CallerOwnedCheckpoint:
    def __init__(self) -> None:
        self.close_calls = 0

    async def save(self, **kwargs: object) -> None:
        del kwargs

    async def consume(self, token: object) -> object:
        del token
        raise RuntimeError("não usado")

    async def aclose(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
async def test_caller_owned_runtime_dependency_is_not_closed() -> None:
    checkpoint = CallerOwnedCheckpoint()
    composition = await AtlasCompositionBuilder(
        factories=ConfigurationFactoryRegistry(),
        runtime_dependencies=RuntimeDependencies(
            checkpoint_store=checkpoint  # type: ignore[arg-type]
        ),
        atlas_version="0.1.0",
    ).build(load_yaml("schema_version: 1\n"))
    await composition.close()
    assert checkpoint.close_calls == 0


@pytest.mark.asyncio
async def test_cancelled_build_closes_previous_resources_and_repropagates() -> None:
    resource = FakeResource("provider")
    registry = ConfigurationFactoryRegistry()
    registry.register_provider_factory(FakeProviderFactory(resource=resource))

    registry.register_tool_factory(FakeToolFactory(cancel=True))
    config = load_yaml(
        """
schema_version: 1
providers:
  fake: {type: fake_provider}
tools:
  tool: {type: fake_tool}
"""
    )
    with pytest.raises(asyncio.CancelledError):
        await AtlasCompositionBuilder(factories=registry, atlas_version="0.1.0").build(
            config
        )
    assert resource.close_calls == 1


def test_builder_does_not_retain_build_session_state() -> None:
    builder = AtlasCompositionBuilder(
        factories=ConfigurationFactoryRegistry(), atlas_version="0.1.0"
    )
    assert not any("session" in name for name in vars(builder))
    assert datetime.now(UTC).tzinfo is not None


@pytest.mark.asyncio
async def test_concurrent_builds_have_independent_registries_and_lifecycle() -> None:
    registry = ConfigurationFactoryRegistry()
    registry.register_provider_factory(FakeProviderFactory())
    builder = AtlasCompositionBuilder(factories=registry, atlas_version="0.1.0")
    config = load_yaml("schema_version: 1\nproviders:\n  fake: {type: fake_provider}\n")
    first, second = await asyncio.gather(builder.build(config), builder.build(config))
    assert first.model_provider_registry is not second.model_provider_registry
    await first.close()
    assert first.closed is True
    assert second.closed is False
    await second.close()
