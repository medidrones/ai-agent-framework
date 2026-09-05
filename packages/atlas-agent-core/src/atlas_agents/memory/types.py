"""Stable provider-neutral memory type identifiers."""

from enum import StrEnum


class MemoryType(StrEnum):
    """Classify memory by its intended lifetime and sharing boundary."""

    WORKING = "working"
    CONVERSATION = "conversation"
    LONG_TERM = "long_term"


_MEMORY_TYPE_ORDER = (
    MemoryType.WORKING,
    MemoryType.CONVERSATION,
    MemoryType.LONG_TERM,
)
