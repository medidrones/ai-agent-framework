"""Synchronize generated package versions from the repository VERSION file."""

from __future__ import annotations

import re
from pathlib import Path

from packaging.version import Version

REPOSITORY = Path(__file__).resolve().parents[1]
VERSION_FILE = REPOSITORY / "VERSION"
VERSION_MODULES = (
    REPOSITORY
    / "packages"
    / "atlas-agent-core"
    / "src"
    / "atlas_agents"
    / "version.py",
    REPOSITORY
    / "packages"
    / "atlas-agent-adapters"
    / "src"
    / "atlas_agents"
    / "adapters"
    / "_version.py",
    REPOSITORY
    / "packages"
    / "atlas-agent-config"
    / "src"
    / "atlas_agents"
    / "config"
    / "_version.py",
    REPOSITORY
    / "packages"
    / "atlas-agent-evaluation"
    / "src"
    / "atlas_agents"
    / "evaluation"
    / "_version.py",
    REPOSITORY
    / "packages"
    / "atlas-agent-mcp"
    / "src"
    / "atlas_agents"
    / "mcp"
    / "_version.py",
    REPOSITORY
    / "packages"
    / "atlas-agent-providers"
    / "src"
    / "atlas_agents"
    / "providers"
    / "_version.py",
    REPOSITORY / "packages" / "atlas-agent" / "src" / "atlas_agent" / "_version.py",
)


def _write_text(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def main() -> None:
    """Validate the PEP 440 version and refresh generated package modules."""
    raw_version = VERSION_FILE.read_text(encoding="utf-8").strip()
    version = str(Version(raw_version))
    if version != raw_version:
        raise ValueError("VERSION deve usar a forma canônica da PEP 440")
    for path in VERSION_MODULES:
        title = (
            "Atlas release version" if path.name == "version.py" else "Package version"
        )
        _write_text(
            path,
            f'"""{title} generated from the repository VERSION file."""\n\n'
            f'__version__ = "{version}"\n',
        )
    _synchronize_internal_constraints(version)


def _synchronize_internal_constraints(version: str) -> None:
    pattern = re.compile(r'(atlas-agent-[a-z-]+(?:\[[a-z,]+\])?~=)[^"\]]+')
    for path in (REPOSITORY / "packages").glob("*/pyproject.toml"):
        source = path.read_text(encoding="utf-8")
        updated = pattern.sub(rf"\g<1>{version}", source)
        _write_text(path, updated)


if __name__ == "__main__":
    main()
