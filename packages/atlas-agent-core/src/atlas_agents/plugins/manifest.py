"""Plugin identity, capability, context, and manifest contracts."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Self

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import Field, JsonValue, ValidationInfo, field_validator

from atlas_agents.plugins._models import FrozenPluginModel, json_mapping, non_empty


class PluginCapability(StrEnum):
    """Identify the kinds of extension a plugin can contribute."""

    MODEL_PROVIDER = "model_provider"
    TOOL = "tool"
    MEMORY_STORE = "memory_store"
    KNOWLEDGE_RETRIEVER = "knowledge_retriever"
    GUARDRAIL = "guardrail"
    EVALUATOR = "evaluator"
    OBSERVABILITY = "observability"


class PluginMetadata(FrozenPluginModel):
    """Describe the stable public identity of one plugin."""

    plugin_id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("plugin_id", "name")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        """Normalize required identity strings."""
        return non_empty(value, field_name=info.field_name or "campo")

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        """Require a PEP 440-compatible version string."""
        normalized = non_empty(value, field_name="version")
        try:
            Version(normalized)
        except InvalidVersion as exc:
            raise ValueError("version deve ser uma versão válida") from exc
        return normalized

    @field_validator("description", "author")
    @classmethod
    def trim_optional_text(cls, value: str) -> str:
        """Trim optional textual metadata."""
        return value.strip()

    @field_validator("homepage")
    @classmethod
    def trim_homepage(cls, value: str | None) -> str | None:
        """Normalize an optional homepage."""
        return non_empty(value, field_name="homepage") if value is not None else None

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Keep arbitrary metadata JSON-safe and isolated."""
        return json_mapping(value)


class PluginManifest(FrozenPluginModel):
    """Declare plugin compatibility and possible contribution categories."""

    metadata: PluginMetadata
    capabilities: tuple[PluginCapability, ...]
    required_atlas_version: str
    optional_dependencies: tuple[str, ...] = ()

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(
        cls, value: tuple[PluginCapability, ...]
    ) -> tuple[PluginCapability, ...]:
        """Require a unique, ordered capability declaration."""
        if not value:
            raise ValueError("capabilities não pode ser vazio")
        if len(set(value)) != len(value):
            raise ValueError("capabilities não pode conter duplicatas")
        return value

    @field_validator("required_atlas_version")
    @classmethod
    def validate_specifier(cls, value: str) -> str:
        """Require a valid Atlas version specifier."""
        normalized = non_empty(value, field_name="required_atlas_version")
        try:
            SpecifierSet(normalized)
        except InvalidSpecifier as exc:
            raise ValueError(
                "required_atlas_version deve ser um intervalo válido"
            ) from exc
        return normalized

    @field_validator("optional_dependencies")
    @classmethod
    def validate_optional_dependencies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize informational dependency declarations."""
        normalized = tuple(
            non_empty(item, field_name="optional_dependency") for item in value
        )
        if len(set(normalized)) != len(normalized):
            raise ValueError("optional_dependencies não pode conter duplicatas")
        return normalized


class PluginContext(FrozenPluginModel):
    """Provide only explicit version and isolated configuration to a plugin."""

    atlas_version: str
    configuration: dict[str, JsonValue] = Field(default_factory=dict, repr=False)

    @field_validator("atlas_version")
    @classmethod
    def validate_atlas_version(cls, value: str) -> str:
        """Require a valid host Atlas version."""
        normalized = non_empty(value, field_name="atlas_version")
        try:
            Version(normalized)
        except InvalidVersion as exc:
            raise ValueError("atlas_version deve ser uma versão válida") from exc
        return normalized

    @field_validator("configuration")
    @classmethod
    def validate_configuration(
        cls, value: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        """Copy and validate configuration without exposing it in repr."""
        return json_mapping(value)

    @classmethod
    def create(
        cls,
        *,
        atlas_version: str,
        configuration: Mapping[str, JsonValue] | None = None,
    ) -> Self:
        """Create a context from an arbitrary caller mapping."""
        return cls(
            atlas_version=atlas_version,
            configuration=json_mapping(configuration or {}),
        )


class PluginCompatibilityChecker:
    """Validate a manifest against one explicit Atlas version."""

    def validate(self, manifest: PluginManifest, atlas_version: str) -> None:
        """Raise before plugin code runs when versions are incompatible."""
        try:
            version = Version(atlas_version)
            requirement = SpecifierSet(manifest.required_atlas_version)
        except (InvalidVersion, InvalidSpecifier) as exc:
            from atlas_agents.plugins.errors import PluginManifestError

            raise PluginManifestError(
                "O manifesto contém uma regra de versão inválida.",
                plugin_id=manifest.metadata.plugin_id,
            ) from exc
        if not requirement.contains(version, prereleases=None):
            from atlas_agents.plugins.errors import PluginCompatibilityError

            raise PluginCompatibilityError(
                f"O plugin '{manifest.metadata.plugin_id}' requer Atlas "
                f"'{manifest.required_atlas_version}', mas a versão ativa é "
                f"'{atlas_version}'.",
                plugin_id=manifest.metadata.plugin_id,
            )
