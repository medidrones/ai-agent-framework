"""Tests for provider-neutral model capabilities and descriptors."""

import pytest
from pydantic import ValidationError

from atlas_agents import ModelCapability, ModelDescriptor


def test_model_capability_values_are_stable_and_serializable() -> None:
    assert {capability.value for capability in ModelCapability} == {
        "text_generation",
        "streaming",
        "structured_output",
        "tool_calling",
        "parallel_tool_calling",
        "vision",
        "audio_input",
        "audio_output",
        "json_mode",
    }
    descriptor = ModelDescriptor(
        provider="local",
        model="atlas-test",
        capabilities=frozenset({ModelCapability.TEXT_GENERATION}),
    )

    assert descriptor.model_dump(mode="json")["capabilities"] == ["text_generation"]


def test_model_descriptor_preserves_immutable_capabilities_and_metadata() -> None:
    metadata: dict[str, object] = {"region": "local"}
    descriptor = ModelDescriptor(
        provider=" provider ",
        model="model",
        capabilities=frozenset(
            {ModelCapability.TEXT_GENERATION, ModelCapability.STREAMING}
        ),
        context_window=8192,
        max_output_tokens=1024,
        metadata=metadata,
    )
    metadata["region"] = "altered"

    assert isinstance(descriptor.capabilities, frozenset)
    assert descriptor.provider == "provider"
    assert descriptor.metadata == {"region": "local"}
    with pytest.raises(ValidationError):
        descriptor.model = "other"


@pytest.mark.parametrize("field", ["provider", "model"])
def test_model_descriptor_rejects_empty_identifiers(field: str) -> None:
    data = {
        "provider": "provider",
        "model": "model",
        "capabilities": frozenset[ModelCapability](),
    }
    data[field] = "  "

    with pytest.raises(ValidationError):
        ModelDescriptor.model_validate(data)


@pytest.mark.parametrize("field", ["context_window", "max_output_tokens"])
@pytest.mark.parametrize("value", [0, -1])
def test_model_descriptor_rejects_non_positive_limits(
    field: str,
    value: int,
) -> None:
    data: dict[str, object] = {
        "provider": "provider",
        "model": "model",
        "capabilities": frozenset[ModelCapability](),
        field: value,
    }

    with pytest.raises(ValidationError):
        ModelDescriptor.model_validate(data)
