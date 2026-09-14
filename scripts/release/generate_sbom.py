"""Generate a deterministic CycloneDX SBOM from the locked workspace."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parents[2]


def _component(package: dict[str, Any]) -> dict[str, object]:
    name = str(package["name"])
    version = str(package.get("version", "workspace"))
    component: dict[str, object] = {
        "type": "library",
        "name": name,
        "version": version,
        "bom-ref": f"pkg:pypi/{name}@{version}",
        "purl": f"pkg:pypi/{name}@{version}",
    }
    source = package.get("source")
    if isinstance(source, dict):
        component["properties"] = [
            {
                "name": f"atlas:source:{key}",
                "value": str(value),
            }
            for key, value in sorted(source.items())
        ]
    return component


def main() -> None:
    """Write all locked runtime and development components as CycloneDX JSON."""
    lock = tomllib.loads((REPOSITORY / "uv.lock").read_text(encoding="utf-8"))
    components = sorted(
        (_component(package) for package in lock["package"]),
        key=lambda item: (str(item["name"]), str(item["version"])),
    )
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": "urn:uuid:00000000-0000-0000-0000-000000000025",
        "version": 1,
        "metadata": {
            "component": {
                "type": "framework",
                "name": "atlas-agent-framework",
                "version": (REPOSITORY / "VERSION").read_text(encoding="utf-8").strip(),
            },
            "properties": [
                {
                    "name": "atlas:scope",
                    "value": "workspace lock; inclui dependências de desenvolvimento",
                }
            ],
        },
        "components": components,
    }
    destination = REPOSITORY / "dist/atlas-agent-framework.cdx.json"
    destination.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"SBOM CycloneDX gerado com {len(components)} componentes.")  # noqa: T201


if __name__ == "__main__":
    main()
