"""Safe validation helpers for public orchestration contracts."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from types import MappingProxyType

MAX_IDENTIFIER_LENGTH = 255
MAX_JSON_DEPTH = 32
MAX_JSON_ITEMS = 10_000
MAX_JSON_STRING_LENGTH = 65_536

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_SYMBOLIC_REFERENCE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]*$")


def validate_identifier(value: str, *, label: str) -> str:
    """Validate one bounded, unambiguous public identifier."""
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"O identificador {label} não pode estar vazio")
    if len(normalized) > MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"O identificador {label} excede o limite permitido")
    if _IDENTIFIER_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"O identificador {label} possui formato inválido")
    return normalized


def validate_symbolic_reference(value: str) -> str:
    """Accept a symbolic condition name, never executable source code."""
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > MAX_IDENTIFIER_LENGTH
        or _SYMBOLIC_REFERENCE_PATTERN.fullmatch(normalized) is None
    ):
        raise ValueError("A condição deve ser uma referência simbólica válida")
    return normalized


def freeze_json(value: object) -> object:
    """Validate bounded JSON data and return a deeply immutable copy."""
    return _freeze_json(value, depth=0, ancestors=set(), counter=[0])


def freeze_json_mapping(value: object) -> Mapping[str, object]:
    """Validate a JSON object and return a deeply immutable mapping."""
    frozen = freeze_json(value)
    if not isinstance(frozen, Mapping):
        raise ValueError("O valor deve ser um objeto JSON")
    return frozen


def empty_json_mapping() -> Mapping[str, object]:
    """Create an immutable empty JSON object for model defaults."""
    return MappingProxyType({})


def thaw_json(value: object) -> object:
    """Convert immutable JSON containers into standard serializable values."""
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def _freeze_json(
    value: object,
    *,
    depth: int,
    ancestors: set[int],
    counter: list[int],
) -> object:
    if depth > MAX_JSON_DEPTH:
        raise ValueError("A estrutura JSON excede a profundidade permitida")
    counter[0] += 1
    if counter[0] > MAX_JSON_ITEMS:
        raise ValueError("A estrutura JSON excede a quantidade de itens permitida")
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Números JSON devem ser finitos")
        return value
    if isinstance(value, str):
        if len(value) > MAX_JSON_STRING_LENGTH:
            raise ValueError("Uma string JSON excede o limite permitido")
        return value
    if not isinstance(value, Mapping | list | tuple):
        raise ValueError("O valor deve conter somente dados serializáveis em JSON")
    marker = id(value)
    if marker in ancestors:
        raise ValueError("Estruturas JSON recursivas não são permitidas")
    nested_ancestors = {*ancestors, marker}
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Chaves de objetos JSON devem ser strings")
            if len(key) > MAX_IDENTIFIER_LENGTH:
                raise ValueError("Uma chave JSON excede o limite permitido")
            frozen[key] = _freeze_json(
                item,
                depth=depth + 1,
                ancestors=nested_ancestors,
                counter=counter,
            )
        return MappingProxyType(frozen)
    return tuple(
        _freeze_json(
            item,
            depth=depth + 1,
            ancestors=nested_ancestors,
            counter=counter,
        )
        for item in value
    )
