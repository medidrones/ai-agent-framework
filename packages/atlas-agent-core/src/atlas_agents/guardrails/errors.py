"""Guardrail configuration and evaluation errors."""


class GuardrailError(Exception):
    """Base error for provider-neutral guardrail failures."""


class GuardrailRegistryError(GuardrailError):
    """Base error for guardrail registry operations."""


class GuardrailNotRegisteredError(GuardrailRegistryError):
    """Report an unknown configured guardrail."""

    def __init__(self, guardrail_id: str) -> None:
        """Preserve the unknown opaque ID without exposing evaluated content."""
        self.guardrail_id = guardrail_id
        super().__init__("O guardrail solicitado não está registrado.")


class DuplicateGuardrailError(GuardrailRegistryError):
    """Report duplicate registration or configuration."""


class GuardrailStageMismatchError(GuardrailError):
    """Report a guardrail assigned to an incompatible stage."""


class GuardrailEvaluationError(GuardrailError):
    """Normalize an unexpected guardrail evaluation failure."""


class GuardrailProtocolError(GuardrailError):
    """Report a result that violates the guardrail protocol."""


class GuardrailTransformationError(GuardrailError):
    """Report an unsafe or invalid transformed value."""
