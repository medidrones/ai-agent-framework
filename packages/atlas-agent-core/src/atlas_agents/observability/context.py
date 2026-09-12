"""Provider-neutral distributed tracing context."""

from pydantic import field_validator

from atlas_agents._models import _FrozenModel, _non_empty


class TraceContext(_FrozenModel):
    """Carry opaque trace correlation identifiers across runtime boundaries."""

    trace_id: str
    span_id: str
    trace_flags: str | None = None
    trace_state: str | None = None

    @field_validator("trace_id", "span_id")
    @classmethod
    def validate_required_ids(cls, value: str) -> str:
        """Reject blank opaque identifiers."""
        return _non_empty(value)

    @field_validator("trace_flags", "trace_state")
    @classmethod
    def validate_optional_values(cls, value: str | None) -> str | None:
        """Reject blank optional propagation values."""
        return None if value is None else _non_empty(value)
