"""Immutable discriminated items emitted by the public runtime stream."""

from typing import Annotated, Literal

from pydantic import Field

from atlas_agents._models import _FrozenModel
from atlas_agents.agents import AgentResult
from atlas_agents.events import AgentEvent


class RuntimeEventItem(_FrozenModel):
    """Wrap one incremental Atlas execution event."""

    type: Literal["event"] = "event"
    event: AgentEvent


class RuntimeResultItem(_FrozenModel):
    """Wrap the single terminal agent result emitted as the final stream item."""

    type: Literal["result"] = "result"
    result: AgentResult[object]


RuntimeStreamItem = Annotated[
    RuntimeEventItem | RuntimeResultItem,
    Field(discriminator="type"),
]
