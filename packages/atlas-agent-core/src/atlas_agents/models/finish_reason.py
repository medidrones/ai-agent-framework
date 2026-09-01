"""Normalized reasons why model generation ended."""

from enum import StrEnum


class FinishReason(StrEnum):
    """Identify a provider-neutral model completion reason."""

    STOP = "stop"
    TOOL_CALL = "tool_call"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    CANCELLED = "cancelled"
    ERROR = "error"
    UNKNOWN = "unknown"
