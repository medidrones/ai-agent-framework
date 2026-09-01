"""Public exception contracts for Atlas Agent Framework."""

from atlas_agents.exceptions.base import AtlasAgentError
from atlas_agents.exceptions.lifecycle import InvalidExecutionTransitionError
from atlas_agents.exceptions.model import (
    ModelAuthenticationError,
    ModelInvalidRequestError,
    ModelNotFoundError,
    ModelPermissionError,
    ModelProviderError,
    ModelRateLimitError,
    ModelResponseError,
    ModelTimeoutError,
    ModelUnavailableError,
)

__all__ = [
    "AtlasAgentError",
    "InvalidExecutionTransitionError",
    "ModelAuthenticationError",
    "ModelInvalidRequestError",
    "ModelNotFoundError",
    "ModelPermissionError",
    "ModelProviderError",
    "ModelRateLimitError",
    "ModelResponseError",
    "ModelTimeoutError",
    "ModelUnavailableError",
]
