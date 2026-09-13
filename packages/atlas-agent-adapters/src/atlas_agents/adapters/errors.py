"""Safe application and transport adapter errors."""

from atlas_agents.exceptions import AtlasAgentError


class AdapterError(AtlasAgentError):
    """Base error with a stable wire code and retry indication."""

    code = "adapter_error"
    retryable = False


class AdapterConfigurationError(AdapterError):
    """Report invalid explicit adapter configuration."""

    code = "adapter_configuration_error"


class AgentNotRegisteredError(AdapterError):
    """Report an unknown agent without exposing registry contents."""

    code = "agent_not_registered"


class DuplicateAgentError(AdapterError):
    """Reject silent replacement of an existing agent."""

    code = "duplicate_agent"


class AgentAccessDeniedError(AdapterError):
    """Report transport-level agent authorization denial."""

    code = "agent_access_denied"


class InvalidExternalRequestError(AdapterError):
    """Report semantically invalid external input."""

    code = "invalid_external_request"


class IdentityMappingError(AdapterError):
    """Report failure to map a trusted transport principal."""

    code = "identity_mapping_error"


class IdempotencyConflictError(AdapterError):
    """Report reuse of a key with a different canonical request."""

    code = "idempotency_conflict"


class AdapterSerializationError(AdapterError):
    """Report data that cannot cross a wire boundary."""

    code = "adapter_serialization_error"


class AdapterStreamingError(AdapterError):
    """Report an adapter streaming failure."""

    code = "adapter_streaming_error"


class AdapterUnavailableError(AdapterError):
    """Report a transient application or transport dependency failure."""

    code = "adapter_unavailable"
    retryable = True
