"""Immutable validation and composition result contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ConfigIssueSeverity(StrEnum):
    """Classify configuration diagnostics without implicit policy."""

    ERROR = "error"
    WARNING = "warning"


class ConfigValidationIssue(BaseModel):
    """Describe one safe configuration diagnostic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    path: str
    message: str
    severity: ConfigIssueSeverity = ConfigIssueSeverity.ERROR


class ConfigValidationResult(BaseModel):
    """Collect all pure validation diagnostics deterministically."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issues: tuple[ConfigValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        """Return whether no error issue was reported."""
        return not any(
            issue.severity is ConfigIssueSeverity.ERROR for issue in self.issues
        )

    @property
    def errors(self) -> tuple[ConfigValidationIssue, ...]:
        """Return only error diagnostics."""
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is ConfigIssueSeverity.ERROR
        )
