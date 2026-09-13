"""Strict immutable models for Atlas configuration schema version 1."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
)

from atlas_agents.config.secrets import SecretReference
from atlas_agents.memory import MemoryType
from atlas_agents.models import ModelCapability

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type ConfigScalar = str | int | float | bool | None
type ConfigValue = (
    ConfigScalar | SecretReference | list[ConfigValue] | dict[str, ConfigValue]
)


def _parse_secret_references(value: object) -> object:
    if isinstance(value, dict):
        if "secret_ref" in value:
            return SecretReference.model_validate(value)
        return {key: _parse_secret_references(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_parse_secret_references(item) for item in value]
    return value


class FrozenConfigModel(BaseModel):
    """Provide a frozen, strict, and closed configuration boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ExecutionLimitsConfig(FrozenConfigModel):
    """Describe default runtime limits without constructing runtime objects."""

    max_turns: int | None = Field(default=None, gt=0)
    max_tool_calls: int | None = Field(default=None, gt=0)
    max_input_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    max_total_tokens: int | None = Field(default=None, gt=0)
    timeout_seconds: float | None = Field(default=None, gt=0)

    @field_validator(
        "max_turns",
        "max_tool_calls",
        "max_input_tokens",
        "max_output_tokens",
        "max_total_tokens",
        "timeout_seconds",
        mode="before",
    )
    @classmethod
    def reject_boolean_limits(cls, value: object) -> object:
        """Reject booleans at numeric configuration boundaries."""
        if isinstance(value, bool):
            raise ValueError("Limites de execução não podem ser booleanos")
        return value


class ExecutionBudgetConfig(FrozenConfigModel):
    """Describe a default runtime budget."""

    max_estimated_cost: Decimal | None = Field(default=None, ge=Decimal(0))
    currency: NonEmptyString = "USD"

    @field_validator("max_estimated_cost", mode="before")
    @classmethod
    def reject_boolean_cost(cls, value: object) -> object:
        """Reject booleans as estimated monetary costs."""
        if isinstance(value, bool):
            raise ValueError("O custo estimado não pode ser booleano")
        return value


class AtlasRuntimeConfig(FrozenConfigModel):
    """Describe global runtime defaults with no transport behavior."""

    default_limits: ExecutionLimitsConfig = ExecutionLimitsConfig()
    default_budget: ExecutionBudgetConfig = ExecutionBudgetConfig()


class ComponentConfig(FrozenConfigModel):
    """Describe one enabled-by-declaration factory-managed component."""

    type: NonEmptyString
    enabled: bool = True
    config: dict[str, ConfigValue] = Field(default_factory=dict)

    @field_validator("config", mode="before")
    @classmethod
    def parse_secret_references(cls, value: object) -> object:
        """Convert only explicit secret reference objects recursively."""
        return _parse_secret_references(value)


class KnowledgeComponentConfig(ComponentConfig):
    """Declare the source IDs served by one knowledge manager."""

    source_ids: tuple[NonEmptyString, ...] = ()

    @field_validator("source_ids")
    @classmethod
    def validate_unique_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject ambiguous duplicate source declarations."""
        return _unique_references(value)


class MCPToolImportConfig(FrozenConfigModel):
    """Allowlist remote MCP tool names; empty imports nothing."""

    include: tuple[NonEmptyString, ...] = ()

    @field_validator("include")
    @classmethod
    def validate_unique_imports(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject duplicate MCP tool imports."""
        return _unique_references(value)


class MCPComponentConfig(ComponentConfig):
    """Describe one MCP integration without starting it implicitly."""

    enabled: bool = False
    import_tools: MCPToolImportConfig = MCPToolImportConfig()


class AdapterComponentConfig(ComponentConfig):
    """Describe one external adapter disabled unless explicitly enabled."""

    enabled: bool = False


class PluginConfig(FrozenConfigModel):
    """Describe explicit trusted plugin activation configuration."""

    enabled: bool = True
    config: dict[str, ConfigValue] = Field(default_factory=dict)

    @field_validator("config", mode="before")
    @classmethod
    def parse_secret_references(cls, value: object) -> object:
        """Convert only explicit plugin secret reference objects recursively."""
        return _parse_secret_references(value)


class AgentModelConfig(FrozenConfigModel):
    """Describe per-agent model selection references."""

    provider: NonEmptyString | None = None
    model: NonEmptyString | None = None
    required_capabilities: frozenset[ModelCapability] = frozenset()
    preferred_capabilities: frozenset[ModelCapability] = frozenset()
    minimum_context_window: int | None = Field(default=None, gt=0)
    minimum_max_output_tokens: int | None = Field(default=None, gt=0)

    @field_validator(
        "minimum_context_window", "minimum_max_output_tokens", mode="before"
    )
    @classmethod
    def reject_boolean_minimums(cls, value: object) -> object:
        """Reject booleans at model numeric boundaries."""
        if isinstance(value, bool):
            raise ValueError("Mínimos do modelo não podem ser booleanos")
        return value


class AgentMemoryConfig(FrozenConfigModel):
    """Describe explicit per-agent memory behavior."""

    read_types: frozenset[MemoryType] = frozenset()
    write_types: frozenset[MemoryType] = frozenset()
    max_records_per_type: int = Field(default=20, gt=0)
    max_characters: int = Field(default=8_000, gt=0)

    @field_validator("max_records_per_type", "max_characters", mode="before")
    @classmethod
    def reject_boolean_limits(cls, value: object) -> object:
        """Reject booleans at memory numeric boundaries."""
        if isinstance(value, bool):
            raise ValueError("Limites de memória não podem ser booleanos")
        return value


class AgentKnowledgeConfig(FrozenConfigModel):
    """Describe an explicit allowlist of configured knowledge sources."""

    sources: tuple[NonEmptyString, ...] = ()
    max_results: int = Field(default=8, gt=0)
    max_characters: int = Field(default=12_000, gt=0)

    @field_validator("sources")
    @classmethod
    def validate_unique_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject duplicate knowledge references."""
        return _unique_references(value)

    @field_validator("max_results", "max_characters", mode="before")
    @classmethod
    def reject_boolean_limits(cls, value: object) -> object:
        """Reject booleans at knowledge numeric boundaries."""
        if isinstance(value, bool):
            raise ValueError("Limites de conhecimento não podem ser booleanos")
        return value


class AgentGuardrailConfig(FrozenConfigModel):
    """Describe ordered guardrail references for each runtime stage."""

    input: tuple[NonEmptyString, ...] = ()
    model_output: tuple[NonEmptyString, ...] = ()
    tool_call: tuple[NonEmptyString, ...] = ()
    tool_result: tuple[NonEmptyString, ...] = ()
    final_output: tuple[NonEmptyString, ...] = ()

    @field_validator(
        "input", "model_output", "tool_call", "tool_result", "final_output"
    )
    @classmethod
    def validate_unique_guardrails(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject duplicate guardrails inside one ordered stage."""
        return _unique_references(value)


class AgentConfig(FrozenConfigModel):
    """Describe one declarative AgentDefinition keyed by its stable ID."""

    enabled: bool = True
    name: NonEmptyString
    description: str = ""
    instructions: NonEmptyString
    model: AgentModelConfig | None = None
    tools: tuple[NonEmptyString, ...] = ()
    memory: AgentMemoryConfig | None = None
    knowledge: AgentKnowledgeConfig | None = None
    guardrails: AgentGuardrailConfig | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("tools")
    @classmethod
    def validate_unique_tools(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject duplicate tool references."""
        return _unique_references(value)


def _unique_references(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(value) != len(set(value)):
        raise ValueError("Referências repetidas não são permitidas")
    return value


def _validate_component_ids[T](value: dict[str, T]) -> dict[str, T]:
    for component_id in value:
        if not component_id.strip():
            raise ValueError("IDs de componentes não podem ser vazios")
        if component_id != component_id.strip():
            raise ValueError("IDs de componentes não podem ter espaços externos")
    return value


class AtlasConfig(FrozenConfigModel):
    """Root contract for the canonical Atlas configuration schema."""

    schema_version: Literal[1]
    atlas: AtlasRuntimeConfig = AtlasRuntimeConfig()
    providers: dict[str, ComponentConfig] = Field(default_factory=dict)
    tools: dict[str, ComponentConfig] = Field(default_factory=dict)
    memory: dict[str, ComponentConfig] = Field(default_factory=dict)
    knowledge: dict[str, KnowledgeComponentConfig] = Field(default_factory=dict)
    guardrails: dict[str, ComponentConfig] = Field(default_factory=dict)
    observability: dict[str, ComponentConfig] = Field(default_factory=dict)
    plugins: dict[str, PluginConfig] = Field(default_factory=dict)
    plugin_activation: tuple[NonEmptyString, ...] = ()
    mcp: dict[str, MCPComponentConfig] = Field(default_factory=dict)
    adapters: dict[str, AdapterComponentConfig] = Field(default_factory=dict)
    agents: dict[str, AgentConfig] = Field(default_factory=dict)

    _validate_providers = field_validator("providers")(_validate_component_ids)
    _validate_tools = field_validator("tools")(_validate_component_ids)
    _validate_memory = field_validator("memory")(_validate_component_ids)
    _validate_knowledge = field_validator("knowledge")(_validate_component_ids)
    _validate_guardrails = field_validator("guardrails")(_validate_component_ids)
    _validate_observability = field_validator("observability")(_validate_component_ids)
    _validate_plugins = field_validator("plugins")(_validate_component_ids)
    _validate_mcp = field_validator("mcp")(_validate_component_ids)
    _validate_adapters = field_validator("adapters")(_validate_component_ids)
    _validate_agents = field_validator("agents")(_validate_component_ids)

    @field_validator("plugin_activation")
    @classmethod
    def validate_unique_plugin_activation(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Keep explicit plugin activation order unambiguous."""
        return _unique_references(value)
