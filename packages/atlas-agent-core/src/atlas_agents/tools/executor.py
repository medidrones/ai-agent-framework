"""Secure operational boundary for executing explicitly registered tools."""

from datetime import UTC, datetime

from atlas_agents.tools.context import ToolExecutionContext
from atlas_agents.tools.errors import ToolError, ToolExecutionInvariantError
from atlas_agents.tools.permissions import ToolPermissionEvaluator
from atlas_agents.tools.registry import ToolRegistry
from atlas_agents.tools.request import ToolExecutionRequest
from atlas_agents.tools.result import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolOutput,
)
from atlas_agents.tools.validation import (
    JsonSchemaToolArgumentValidator,
    ToolArgumentValidator,
)


class ToolExecutor:
    """Resolve, authorize, validate, execute, and normalize one tool call."""

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        validator: ToolArgumentValidator | None = None,
        permission_evaluator: ToolPermissionEvaluator | None = None,
    ) -> None:
        """Receive every collaborator explicitly without global lookup."""
        self._registry = registry
        self._validator = (
            validator if validator is not None else JsonSchemaToolArgumentValidator()
        )
        self._permission_evaluator = (
            permission_evaluator
            if permission_evaluator is not None
            else ToolPermissionEvaluator()
        )

    async def execute(
        self,
        request: ToolExecutionRequest,
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        """Execute one request while preserving identity and cancellation."""
        started_at = datetime.now(UTC)
        tool = self._registry.try_get(request.tool_name)
        if tool is None:
            return self._failure(
                request=request,
                started_at=started_at,
                status=ToolExecutionStatus.FAILED,
                error=ToolExecutionError(
                    code="tool_not_found",
                    message="A ferramenta solicitada não está registrada.",
                ),
            )

        if request.tool_call_id != context.tool_call_id:
            raise ToolExecutionInvariantError(
                "O tool_call_id da solicitação diverge do contexto de execução."
            )

        permission = self._permission_evaluator.evaluate(
            definition=tool.definition,
            context=context,
        )
        if not permission.allowed:
            return self._failure(
                request=request,
                started_at=started_at,
                status=ToolExecutionStatus.DENIED,
                error=ToolExecutionError(
                    code="tool_permission_denied",
                    message="A identidade não possui todas as permissões exigidas.",
                    details={
                        "missing_permissions": sorted(permission.missing_permissions)
                    },
                ),
            )

        validation = self._validator.validate(
            schema=tool.definition.parameters,
            arguments=request.arguments,
        )
        if not validation.valid:
            return self._failure(
                request=request,
                started_at=started_at,
                status=ToolExecutionStatus.INVALID_ARGUMENTS,
                error=ToolExecutionError(
                    code="tool_invalid_arguments",
                    message="Os argumentos da ferramenta são inválidos.",
                    details={
                        "issues": [
                            issue.model_dump(mode="json") for issue in validation.issues
                        ]
                    },
                ),
            )

        try:
            output = await tool.execute(request.arguments, context)
        except ToolError as exc:
            return self._failure(
                request=request,
                started_at=started_at,
                status=ToolExecutionStatus.FAILED,
                error=ToolExecutionError(
                    code=exc.code,
                    message=str(exc),
                    retryable=exc.retryable,
                    details=exc.details,
                ),
            )
        except Exception:
            return self._failure(
                request=request,
                started_at=started_at,
                status=ToolExecutionStatus.FAILED,
                error=ToolExecutionError(
                    code="tool_execution_error",
                    message="A ferramenta falhou durante a execução.",
                ),
            )

        if not isinstance(output, ToolOutput):
            return self._failure(
                request=request,
                started_at=started_at,
                status=ToolExecutionStatus.FAILED,
                error=ToolExecutionError(
                    code="tool_invalid_output",
                    message="A ferramenta retornou um output incompatível.",
                ),
            )
        return ToolExecutionResult(
            tool_call_id=request.tool_call_id,
            tool_name=request.tool_name,
            status=ToolExecutionStatus.SUCCEEDED,
            output=output,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            metadata=request.metadata,
        )

    @staticmethod
    def _failure(
        *,
        request: ToolExecutionRequest,
        started_at: datetime,
        status: ToolExecutionStatus,
        error: ToolExecutionError,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_call_id=request.tool_call_id,
            tool_name=request.tool_name,
            status=status,
            error=error,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            metadata=request.metadata,
        )
