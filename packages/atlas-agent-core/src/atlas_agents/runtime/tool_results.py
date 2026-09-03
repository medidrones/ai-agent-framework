"""Model-facing serialization of normalized tool execution results."""

import json

from atlas_agents.models import MessageRole, ModelMessage, TextContent
from atlas_agents.tools import ToolExecutionResult


class ToolResultMessageMapper:
    """Map safe result facts to a deterministic provider-neutral TOOL message."""

    def map(self, result: ToolExecutionResult) -> ModelMessage:
        """Serialize only status, functional output, and normalized error facts."""
        error = result.error
        payload: dict[str, object] = {
            "status": result.status.value,
            "output": None if result.output is None else result.output.content,
            "error": (
                None
                if error is None
                else {
                    "code": error.code,
                    "message": error.message,
                    "retryable": error.retryable,
                }
            ),
        }
        content = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return ModelMessage(
            role=MessageRole.TOOL,
            tool_call_id=result.tool_call_id,
            content=(TextContent(text=content),),
        )
