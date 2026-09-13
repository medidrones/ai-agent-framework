"""Generate the checked-in JSON Schema for declarative configuration."""

from __future__ import annotations

import json
from pathlib import Path

from atlas_agents.config import AtlasConfig


def main() -> None:
    """Write a stable, human-readable schema artifact."""
    repository = Path(__file__).resolve().parents[3]
    destination = repository / "docs" / "config" / "atlas-config.schema.json"
    schema = AtlasConfig.model_json_schema()
    destination.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
