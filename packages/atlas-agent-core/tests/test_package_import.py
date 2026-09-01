"""Smoke tests for the public package."""

import atlas_agents


def test_package_can_be_imported() -> None:
    """The installed package exposes a non-empty string version."""
    assert isinstance(atlas_agents.__version__, str)
    assert atlas_agents.__version__


def test_model_abstraction_is_intentionally_public() -> None:
    expected = {
        "AudioContent",
        "FinishReason",
        "ImageContent",
        "MessageContent",
        "MessageRole",
        "ModelCapability",
        "ModelDescriptor",
        "ModelExecutionContext",
        "ModelMessage",
        "ModelProvider",
        "ModelRequest",
        "ModelResponse",
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
        "ModelAuthenticationError",
        "ModelInvalidRequestError",
        "ModelNotFoundError",
        "ModelPermissionError",
        "ModelProviderError",
        "ModelRateLimitError",
        "ModelResponseError",
        "ModelTimeoutError",
        "ModelUnavailableError",
    }

    assert expected <= set(atlas_agents.__all__)
