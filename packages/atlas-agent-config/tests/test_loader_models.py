from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from atlas_agents.config import (
    AtlasConfig,
    ConfigParseError,
    ConfigValidationError,
    DuplicateComponentConfigError,
    UnsupportedConfigVersionError,
    load_config,
    load_json,
    load_yaml,
    validate_config_file,
)

YAML_CONFIG = """
schema_version: 1
atlas:
  default_limits:
    max_turns: 5
providers:
  fake:
    type: fake_provider
agents:
  assistant:
    name: Assistente
    instructions: Responda com clareza.
    model:
      provider: fake
      required_capabilities:
        - text_generation
"""


def test_yaml_and_json_have_equivalent_semantics() -> None:
    yaml_config = load_yaml(YAML_CONFIG)
    json_config = load_json(json.dumps(yaml_config.model_dump(mode="json")))
    assert yaml_config == json_config
    assert yaml_config.schema_version == 1
    assert yaml_config.agents["assistant"].model is not None


def test_unknown_field_is_rejected_with_safe_path() -> None:
    with pytest.raises(ConfigValidationError) as captured:
        load_yaml("schema_version: 1\nunknown: true\n")
    assert captured.value.path == "$.unknown"


@pytest.mark.parametrize("version", [2, 99, "1", None])
def test_unknown_schema_version_is_rejected(version: object) -> None:
    source = json.dumps({"schema_version": version})
    with pytest.raises(UnsupportedConfigVersionError) as captured:
        load_json(source)
    assert captured.value.path == "$.schema_version"


def test_yaml_unsafe_python_tag_is_rejected() -> None:
    with pytest.raises(ConfigParseError):
        load_yaml("schema_version: 1\nvalue: !!python/object:builtins.object {}\n")


@pytest.mark.parametrize(
    "source",
    [
        "schema_version: 1\nagents: [",
        "- schema_version\n- 1",
    ],
)
def test_invalid_yaml_or_root_type_is_rejected(source: str) -> None:
    with pytest.raises((ConfigParseError, ConfigValidationError)):
        load_yaml(source)


def test_invalid_json_reports_location() -> None:
    with pytest.raises(ConfigParseError) as captured:
        load_json('{"schema_version": 1,}')
    assert "linha" in captured.value.path


@pytest.mark.parametrize(
    "source",
    [
        "schema_version: 1\nagents: {}\nagents: {}\n",
        '{"schema_version":1,"agents":{},"agents":{}}',
    ],
)
def test_duplicate_mapping_key_is_rejected(source: str) -> None:
    loader = load_json if source.startswith("{") else load_yaml
    with pytest.raises(DuplicateComponentConfigError):
        loader(source)


def test_file_loader_supports_yaml_yml_and_json(tmp_path: Path) -> None:
    yaml_path = tmp_path / "atlas.yaml"
    yml_path = tmp_path / "atlas.yml"
    json_path = tmp_path / "atlas.json"
    yaml_path.write_text(YAML_CONFIG, encoding="utf-8")
    yml_path.write_text(YAML_CONFIG, encoding="utf-8")
    config = load_yaml(YAML_CONFIG)
    json_path.write_text(json.dumps(config.model_dump(mode="json")), encoding="utf-8")
    assert load_config(yaml_path) == config
    assert load_config(yml_path) == config
    assert load_config(json_path) == config


def test_file_loader_rejects_unknown_extension_and_missing_file(tmp_path: Path) -> None:
    unknown = tmp_path / "atlas.toml"
    missing = tmp_path / "missing.yaml"
    with pytest.raises(ConfigParseError):
        load_config(unknown)
    with pytest.raises(ConfigParseError):
        load_config(missing)


def test_validate_config_file_returns_structural_issue(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("schema_version: 1\nextra: true\n", encoding="utf-8")
    result = validate_config_file(str(path))
    assert result.valid is False
    assert result.errors[0].code == "config_validation_error"


def test_root_model_is_frozen_and_defaults_are_secure() -> None:
    config = load_yaml("schema_version: 1\n")
    with pytest.raises(ConfigValidationError):
        load_yaml("schema_version: 1\nagents:\n  ' ': {}\n")
    assert config.tools == {}
    assert config.knowledge == {}
    assert config.plugins == {}
    assert config.mcp == {}
    assert config.adapters == {}
    with pytest.raises(ValidationError, match="frozen"):
        config.schema_version = 1


def test_json_schema_describes_versioned_typed_root() -> None:
    schema = AtlasConfig.model_json_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == 1
    assert "agents" in schema["properties"]


def test_checked_in_schema_matches_public_model() -> None:
    repository = Path(__file__).parents[3]
    schema_path = repository / "docs" / "config" / "atlas-config.schema.json"
    assert json.loads(schema_path.read_text(encoding="utf-8")) == (
        AtlasConfig.model_json_schema()
    )


@pytest.mark.parametrize(
    "relative_path",
    ["examples/config/minimal.json", "examples/config/full.yaml"],
)
def test_documented_examples_follow_current_schema(relative_path: str) -> None:
    repository = Path(__file__).parents[3]
    assert load_config(repository / relative_path).schema_version == 1


def test_unknown_component_field_is_rejected() -> None:
    with pytest.raises(ConfigValidationError) as captured:
        load_yaml(
            """
schema_version: 1
providers:
  fake:
    type: fake_provider
    class: arbitrary.module.Provider
"""
        )
    assert captured.value.path.endswith("providers.fake.class")


@pytest.mark.parametrize(
    "fragment",
    [
        "atlas:\n  default_limits:\n    max_turns: true",
        "agents:\n  a:\n    name: A\n    instructions: Ajude.\n    tools: [one, one]",
        "plugin_activation: [one, one]",
        "mcp:\n  server:\n    type: fake\n    import_tools:\n      include: [one, one]",
    ],
)
def test_ambiguous_numeric_or_duplicate_values_are_rejected(fragment: str) -> None:
    with pytest.raises(ConfigValidationError):
        load_yaml(f"schema_version: 1\n{fragment}\n")
