"""Provider-neutral citations and deterministic output marker extraction."""

import re

from pydantic import field_validator

from atlas_agents._models import _FrozenModel, _non_empty
from atlas_agents.knowledge.document import KnowledgeLocation

_CITATION_PATTERN = re.compile(r"\[(K[1-9][0-9]*)\]")


class Citation(_FrozenModel):
    """Expose reference metadata without embedding retrieved passage content."""

    citation_key: str
    source_id: str
    document_id: str
    passage_id: str
    title: str | None = None
    uri: str | None = None
    location: KnowledgeLocation | None = None

    @field_validator("citation_key", "source_id", "document_id", "passage_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Reject blank citation and external identifiers."""
        return _non_empty(value)

    @field_validator("citation_key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        """Require the local K-number citation syntax."""
        if re.fullmatch(r"K[1-9][0-9]*", value) is None:
            raise ValueError("A chave de citação deve seguir o formato K<número>")
        return value

    @field_validator("title", "uri")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        """Reject explicitly blank optional citation references."""
        return None if value is None else _non_empty(value)


def extract_citations(
    output: object,
    available: tuple[Citation, ...],
) -> tuple[Citation, ...]:
    """Map valid markers from textual final output in first-occurrence order."""
    if not isinstance(output, str):
        return ()
    by_key = {citation.citation_key: citation for citation in available}
    selected: list[Citation] = []
    seen: set[str] = set()
    for match in _CITATION_PATTERN.finditer(output):
        key = match.group(1)
        citation = by_key.get(key)
        if citation is not None and key not in seen:
            selected.append(citation)
            seen.add(key)
    return tuple(selected)
