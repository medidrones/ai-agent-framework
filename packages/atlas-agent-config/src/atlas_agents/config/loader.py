"""Safe synchronous YAML, JSON, and local file loading."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml
from pydantic import ValidationError
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from atlas_agents.config.errors import (
    ConfigParseError,
    ConfigValidationError,
    DuplicateComponentConfigError,
    UnsupportedConfigVersionError,
)
from atlas_agents.config.models import AtlasConfig
from atlas_agents.config.overrides import merge_config_overrides
from atlas_agents.config.versioning import SUPPORTED_CONFIG_SCHEMA_VERSIONS


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Use SafeLoader while rejecting duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "foi encontrada uma chave não escalar",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise DuplicateComponentConfigError(
                f"A chave de configuração '{key}' foi declarada mais de uma vez."
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _validation_path(error: ValidationError) -> str:
    first = error.errors(include_url=False)[0]
    location = first.get("loc", ())
    path = "$"
    for part in location:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _build_config(
    value: object, overrides: Mapping[str, object] | None = None
) -> AtlasConfig:
    if not isinstance(value, Mapping):
        raise ConfigValidationError("A configuração raiz deve ser um objeto.", path="$")
    merged = merge_config_overrides(cast("Mapping[str, object]", value), overrides)
    version = merged.get("schema_version")
    if version not in SUPPORTED_CONFIG_SCHEMA_VERSIONS:
        raise UnsupportedConfigVersionError(
            f"A versão de configuração '{version}' não é suportada.",
            path="$.schema_version",
        )
    try:
        return AtlasConfig.model_validate(merged)
    except ValidationError as error:
        raise ConfigValidationError(
            "A configuração não corresponde ao schema declarado.",
            path=_validation_path(error),
        ) from error


def load_yaml(
    text: str, *, overrides: Mapping[str, object] | None = None
) -> AtlasConfig:
    """Parse safe YAML text and return strict versioned configuration."""
    try:
        value = yaml.load(text, Loader=_UniqueKeySafeLoader)  # noqa: S506
    except DuplicateComponentConfigError:
        raise
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        location = (
            "$" if mark is None else f"linha {mark.line + 1}, coluna {mark.column + 1}"
        )
        raise ConfigParseError(
            "O YAML é inválido ou contém uma construção não permitida.",
            path=location,
        ) from error
    return _build_config(value, overrides)


def load_json(
    text: str, *, overrides: Mapping[str, object] | None = None
) -> AtlasConfig:
    """Parse JSON text and return strict versioned configuration."""

    def reject_duplicate(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateComponentConfigError(
                    f"A chave de configuração '{key}' foi declarada mais de uma vez."
                )
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=reject_duplicate)
    except DuplicateComponentConfigError:
        raise
    except json.JSONDecodeError as error:
        raise ConfigParseError(
            "O JSON é inválido.", path=f"linha {error.lineno}, coluna {error.colno}"
        ) from error
    return _build_config(value, overrides)


def load_config(
    path: str | Path, *, overrides: Mapping[str, object] | None = None
) -> AtlasConfig:
    """Load one explicitly supplied local YAML or JSON file."""
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in {".yaml", ".yml", ".json"}:
        raise ConfigParseError(
            "A extensão do arquivo deve ser .yaml, .yml ou .json.",
            path=str(source),
        )
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigParseError(
            "Não foi possível ler o arquivo de configuração.", path=str(source)
        ) from error
    if suffix == ".json":
        return load_json(text, overrides=overrides)
    return load_yaml(text, overrides=overrides)
