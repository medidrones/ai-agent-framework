"""Shared model configuration and validation helpers."""

import json
from copy import deepcopy

from pydantic import BaseModel, ConfigDict


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _non_empty(value: str) -> str:
    if not value.strip():
        msg = "O valor não pode estar vazio nem conter apenas espaços"
        raise ValueError(msg)
    return value


def _json_mapping(value: dict[str, object]) -> dict[str, object]:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        msg = "O valor deve conter somente dados serializáveis em JSON"
        raise ValueError(msg) from exc
    return deepcopy(value)
