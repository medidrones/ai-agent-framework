"""Immutable discriminated items emitted by the public runtime stream."""

from typing import Annotated, Literal

from pydantic import Field

from atlas_agents._models import _FrozenModel
from atlas_agents.agents import AgentResult
from atlas_agents.approvals import ExecutionSuspension
from atlas_agents.events import AgentEvent


class RuntimeEventItem(_FrozenModel):
    """Wrap one incremental Atlas execution event."""

    type: Literal["event"] = "event"
    event: AgentEvent


class RuntimeResultItem(_FrozenModel):
    """Wrap the single terminal agent result emitted as the final stream item."""

    type: Literal["result"] = "result"
    result: AgentResult[object]


class RuntimeSuspensionItem(_FrozenModel):
    """Wrap a resumable suspension as the final item of one stream invocation."""

    type: Literal["suspension"] = "suspension"
    suspension: ExecutionSuspension


RuntimeStreamItem = Annotated[
    RuntimeEventItem | RuntimeResultItem | RuntimeSuspensionItem,
    Field(discriminator="type"),
]
