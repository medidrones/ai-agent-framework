"""Smoke tests for the public package."""

import atlas_agents


def test_package_can_be_imported() -> None:
    """The installed package exposes a non-empty string version."""
    assert isinstance(atlas_agents.__version__, str)
    assert atlas_agents.__version__


def test_model_abstraction_is_intentionally_public() -> None:
    expected = {
        "AudioContent",
        "DeterministicModelSelectionStrategy",
        "FinishReason",
        "ImageContent",
        "MessageContent",
        "MessageRole",
        "ModelCapability",
        "ModelCandidate",
        "ModelCatalogEntry",
        "ModelDescriptor",
        "ModelExecutionContext",
        "ModelMessage",
        "ModelProvider",
        "ModelProviderRegistry",
        "ModelRequest",
        "ModelResponse",
        "ModelSelectionRequest",
        "ModelSelectionResult",
        "ModelSelectionStrategy",
        "ModelStreamEvent",
        "ModelStreamEventType",
        "ModelToolDefinition",
        "ModelUsage",
        "StructuredOutputDefinition",
        "TextContent",
        "ToolCall",
    }

    assert expected <= set(atlas_agents.__all__)


def test_model_error_hierarchy_is_intentionally_public() -> None:
    expected = {
        "AtlasAgentError",
        "DuplicateModelProviderError",
        "InvalidModelDescriptorError",
        "ModelAuthenticationError",
        "ModelCapabilityMismatchError",
        "ModelInvalidRequestError",
        "ModelNotAvailableError",
        "ModelNotFoundError",
        "ModelPermissionError",
        "ModelProviderError",
        "ModelProviderNotRegisteredError",
        "ModelProviderRegistryError",
        "ModelRateLimitError",
        "ModelResponseError",
        "ModelSelectionError",
        "ModelTimeoutError",
        "ModelUnavailableError",
        "NoMatchingModelError",
    }

    assert expected <= set(atlas_agents.__all__)


def test_runtime_state_contracts_are_intentionally_public() -> None:
    expected = {
        "ExecutionAlreadyTerminalError",
        "ExecutionSnapshot",
        "ExecutionState",
        "ExecutionStateError",
        "ExecutionStateInvariantError",
    }

    assert expected <= set(atlas_agents.__all__)
