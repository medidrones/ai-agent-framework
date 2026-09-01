"""Public exception contracts for Atlas Agent Framework."""

from atlas_agents.exceptions.base import AtlasAgentError
from atlas_agents.exceptions.lifecycle import InvalidExecutionTransitionError
from atlas_agents.exceptions.model import (
    DuplicateModelProviderError,
    InvalidModelDescriptorError,
    ModelAuthenticationError,
    ModelCapabilityMismatchError,
    ModelInvalidRequestError,
    ModelNotAvailableError,
    ModelNotFoundError,
    ModelPermissionError,
    ModelProviderError,
    ModelProviderNotRegisteredError,
    ModelProviderRegistryError,
    ModelRateLimitError,
    ModelResponseError,
    ModelSelectionError,
    ModelTimeoutError,
    ModelUnavailableError,
    NoMatchingModelError,
)

__all__ = [
    "AtlasAgentError",
    "DuplicateModelProviderError",
    "InvalidExecutionTransitionError",
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
]
