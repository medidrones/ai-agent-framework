"""Provider-neutral JSON Schema validation contracts for tool arguments."""

from collections.abc import Sequence
from typing import Protocol, Self

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from pydantic import model_validator

from atlas_agents._models import _FrozenModel, _non_empty


class ToolArgumentValidationIssue(_FrozenModel):
    """Describe one normalized argument validation issue."""

    path: str
    code: str
    message: str

    @classmethod
    def from_jsonschema_error(
        cls,
        error: ValidationError,
    ) -> "ToolArgumentValidationIssue":
        """Normalize a jsonschema error without exposing internal objects."""
        code = str(error.validator or "schema_violation")
        return cls(
            path=_json_pointer(tuple(error.absolute_path)),
            code=code,
            message=_localized_validation_message(code),
        )

    @classmethod
    def invalid_schema(cls) -> "ToolArgumentValidationIssue":
        """Represent an invalid registered schema as a safe issue."""
        return cls(
            path="/",
            code="invalid_schema",
            message="O schema de argumentos da ferramenta é inválido.",
        )

    @model_validator(mode="after")
    def validate_text(self) -> Self:
        """Reject empty issue fields."""
        _non_empty(self.path)
        _non_empty(self.code)
        _non_empty(self.message)
        return self


class ToolArgumentValidationResult(_FrozenModel):
    """Represent the complete deterministic validation outcome."""

    valid: bool
    issues: tuple[ToolArgumentValidationIssue, ...] = ()

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        """Keep the validity flag consistent with the issue collection."""
        if self.valid == bool(self.issues):
            msg = "O resultado de validação é inconsistente com suas ocorrências"
            raise ValueError(msg)
        return self


class ToolArgumentValidator(Protocol):
    """Validate structured arguments against a provider-neutral schema."""

    def validate(
        self,
        *,
        schema: dict[str, object],
        arguments: dict[str, object],
    ) -> ToolArgumentValidationResult:
        """Return normalized issues instead of raising for invalid arguments."""
        ...


class JsonSchemaToolArgumentValidator:
    """Validate tool arguments with JSON Schema Draft 2020-12."""

    def validate(
        self,
        *,
        schema: dict[str, object],
        arguments: dict[str, object],
    ) -> ToolArgumentValidationResult:
        """Validate all arguments and return issues in deterministic order."""
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError:
            return ToolArgumentValidationResult(
                valid=False,
                issues=(ToolArgumentValidationIssue.invalid_schema(),),
            )
        errors = sorted(
            Draft202012Validator(schema).iter_errors(arguments),
            key=lambda error: (
                tuple(str(item) for item in error.absolute_path),
                error.message,
            ),
        )
        issues = tuple(
            ToolArgumentValidationIssue.from_jsonschema_error(error) for error in errors
        )
        return ToolArgumentValidationResult(valid=not issues, issues=issues)


def _json_pointer(path: Sequence[object]) -> str:
    if not path:
        return "/"
    escaped = (str(item).replace("~", "~0").replace("/", "~1") for item in path)
    return "/" + "/".join(escaped)


def _localized_validation_message(code: str) -> str:
    messages = {
        "additionalProperties": (
            "O objeto contém propriedades não permitidas pelo schema."
        ),
        "required": "Uma propriedade obrigatória não foi informada.",
        "type": "O valor possui um tipo incompatível com o schema.",
    }
    return messages.get(code, "O valor não atende ao schema da ferramenta.")
