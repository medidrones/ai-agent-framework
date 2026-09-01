"""Focused tests for runtime request building and safe error normalization."""

from atlas_agents import (
    AgentAttachment,
    AgentContext,
    AgentDefinition,
    AgentInput,
    ExecutionState,
    InvalidModelDescriptorError,
    MessageRole,
    ModelCapability,
    ModelCapabilityMismatchError,
    ModelDescriptor,
    ModelNotAvailableError,
    ModelProviderRegistryError,
    ModelSelectionError,
    ModelSelectionRequest,
    ModelSelectionResult,
    NoMatchingModelError,
)
from atlas_agents.runtime.error_mapping import (
    model_selection_error_to_agent_error,
    registry_error_to_agent_error,
)
from atlas_agents.runtime.model_request import ModelRequestBuilder


def _agent() -> AgentDefinition:
    return AgentDefinition(
        agent_id="agent",
        name="Agent",
        instructions="Be concise.",
    )


def test_builder_accepts_attachment_only_and_maps_audio_content() -> None:
    input_data = AgentInput(
        message="",
        attachments=(
            AgentAttachment(
                attachment_id="audio",
                name="audio.wav",
                media_type="audio/wav",
                uri="memory://audio",
            ),
        ),
    )
    builder = ModelRequestBuilder()

    messages = builder.build_initial_messages(_agent(), input_data)
    selection = builder.derive_selection_request(input_data)

    assert [message.role for message in messages] == [
        MessageRole.SYSTEM,
        MessageRole.USER,
    ]
    assert len(messages[1].content) == 1
    assert selection.required_capabilities == frozenset(
        {ModelCapability.TEXT_GENERATION, ModelCapability.AUDIO_INPUT}
    )


def test_builder_preserves_caller_selection_policy_and_builds_request() -> None:
    input_data = AgentInput(message="Hello")
    requested = ModelSelectionRequest(
        provider="provider",
        model="model",
        required_capabilities=frozenset({ModelCapability.JSON_MODE}),
        preferred_capabilities=frozenset({ModelCapability.STREAMING}),
        minimum_context_window=100,
        minimum_max_output_tokens=10,
        metadata={"policy": "caller"},
    )
    builder = ModelRequestBuilder()
    merged = builder.derive_selection_request(input_data, requested)
    descriptor = ModelDescriptor(
        provider="provider",
        model="model",
        capabilities=merged.required_capabilities,
    )
    selection = ModelSelectionResult(
        provider_name="provider",
        model="model",
        descriptor=descriptor,
        matched_required_capabilities=merged.required_capabilities,
        matched_preferred_capabilities=frozenset(),
        preferred_capability_matches=0,
        candidate_count=1,
    )
    state = ExecutionState(
        execution_id="execution",
        agent=_agent(),
        input_data=input_data,
        context=AgentContext(execution_id="execution"),
    )
    for message in builder.build_initial_messages(_agent(), input_data):
        state.add_message(message)

    request = builder.build_request(state, selection)

    assert merged.provider == "provider"
    assert merged.model == "model"
    assert merged.required_capabilities == frozenset(
        {ModelCapability.TEXT_GENERATION, ModelCapability.JSON_MODE}
    )
    assert merged.preferred_capabilities == frozenset({ModelCapability.STREAMING})
    assert merged.minimum_context_window == 100
    assert merged.minimum_max_output_tokens == 10
    assert merged.metadata == {"policy": "caller"}
    assert request.model == "model"
    assert request.messages == state.messages


def test_selection_error_mapping_covers_specific_and_generic_codes() -> None:
    no_match = NoMatchingModelError(
        requested_provider=None,
        requested_model=None,
        required_capabilities=frozenset(),
        minimum_context_window=None,
        minimum_max_output_tokens=None,
    )
    unavailable = ModelNotAvailableError(provider_name=None, model="missing")
    mismatch = ModelCapabilityMismatchError(
        provider_name="provider",
        model="model",
        missing_capabilities=frozenset({"vision"}),
    )

    assert model_selection_error_to_agent_error(no_match).code == "no_matching_model"
    assert (
        model_selection_error_to_agent_error(unavailable).code == "model_not_available"
    )
    assert (
        model_selection_error_to_agent_error(mismatch).code
        == "model_capability_mismatch"
    )
    assert (
        model_selection_error_to_agent_error(ModelSelectionError("selection")).code
        == "model_selection_error"
    )


def test_registry_error_mapping_covers_descriptor_and_generic_codes() -> None:
    descriptor_error = InvalidModelDescriptorError(
        "provider",
        "model",
        "inconsistente",
    )

    assert (
        registry_error_to_agent_error(descriptor_error).code
        == "invalid_model_descriptor"
    )
    assert (
        registry_error_to_agent_error(ModelProviderRegistryError("registry")).code
        == "model_registry_error"
    )
