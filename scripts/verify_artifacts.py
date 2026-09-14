"""Inspect built Atlas wheels and source distributions without installing them."""

from __future__ import annotations

import email
import re
import tarfile
import zipfile
from email.message import Message
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

REPOSITORY = Path(__file__).resolve().parents[1]
DIST = REPOSITORY / "dist"
DISTRIBUTIONS = {
    "atlas-agent": "atlas_agent",
    "atlas-agent-adapters": "atlas_agent_adapters",
    "atlas-agent-config": "atlas_agent_config",
    "atlas-agent-core": "atlas_agent_core",
    "atlas-agent-evaluation": "atlas_agent_evaluation",
    "atlas-agent-mcp": "atlas_agent_mcp",
    "atlas-agent-providers": "atlas_agent_providers",
}
TYPED_MARKERS = {
    "atlas-agent": "atlas_agent/py.typed",
    "atlas-agent-adapters": "atlas_agents/adapters/py.typed",
    "atlas-agent-config": "atlas_agents/config/py.typed",
    "atlas-agent-core": "atlas_agents/py.typed",
    "atlas-agent-evaluation": "atlas_agents/evaluation/py.typed",
    "atlas-agent-mcp": "atlas_agents/mcp/py.typed",
    "atlas-agent-providers": "atlas_agents/providers/py.typed",
}
FORBIDDEN_ARTIFACT_PARTS = (
    ".env",
    ".idea/",
    ".vscode/",
    ".coverage",
    "coverage.xml",
    "__pycache__/",
    "/tests/",
)
DEV_TOOLS = {"mypy", "pytest", "ruff", "twine", "grpcio-tools"}


def _single(pattern: str) -> Path:
    matches = tuple(DIST.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Esperado um artefato para {pattern}: {matches}")
    return matches[0]


def _metadata(archive: zipfile.ZipFile) -> Message:
    metadata_name = next(
        name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
    )
    return email.message_from_bytes(archive.read(metadata_name))


def _check_wheel(distribution: str, normalized: str, expected: Version) -> None:
    wheel = _single(f"{normalized}-{expected}-py3-none-any.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = _metadata(archive)
        if TYPED_MARKERS[distribution] not in names:
            raise RuntimeError(f"py.typed ausente em {wheel.name}")
        if not any(".dist-info/licenses/LICENSE" in name for name in names):
            raise RuntimeError(f"licença ausente em {wheel.name}")
        if any(part in name for name in names for part in FORBIDDEN_ARTIFACT_PARTS):
            raise RuntimeError(f"arquivo proibido em {wheel.name}")
        if metadata["Version"] != str(expected):
            raise RuntimeError(f"versão divergente em {wheel.name}")
        if metadata["Requires-Python"] != ">=3.12":
            raise RuntimeError(f"Requires-Python divergente em {wheel.name}")
        requirements = tuple(
            Requirement(value) for value in metadata.get_all("Requires-Dist", [])
        )
        for requirement in requirements:
            rendered = str(requirement)
            if "file:" in rendered or "git+" in rendered:
                raise RuntimeError(f"dependência não publicável: {rendered}")
            if requirement.name.casefold() in DEV_TOOLS:
                raise RuntimeError(f"ferramenta dev em runtime: {rendered}")
        if distribution == "atlas-agent-providers":
            entry_points = next(
                name for name in names if name.endswith(".dist-info/entry_points.txt")
            )
            content = archive.read(entry_points).decode("utf-8")
            if "atlas_agents.plugins" not in content or "openai" not in content:
                raise RuntimeError("entry point OpenAI ausente do wheel")


def _check_sdist(normalized: str, expected: Version) -> None:
    sdist = _single(f"{normalized}-{expected}.tar.gz")
    with tarfile.open(sdist, "r:gz") as archive:
        names = archive.getnames()
    if not any(name.endswith("/LICENSE") for name in names):
        raise RuntimeError(f"licença ausente em {sdist.name}")
    if any(part in name for name in names for part in FORBIDDEN_ARTIFACT_PARTS):
        raise RuntimeError(f"arquivo proibido em {sdist.name}")


def main() -> None:
    """Validate versions, metadata, contents, typing and plugin entry points."""
    expected = Version((REPOSITORY / "VERSION").read_text(encoding="utf-8").strip())
    for distribution, normalized in DISTRIBUTIONS.items():
        _check_wheel(distribution, normalized, expected)
        _check_sdist(normalized, expected)
    unexpected = [
        path.name
        for path in DIST.iterdir()
        if path.is_file()
        and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
        and not re.match(r"atlas_agent(?:_[a-z]+)*-", path.name)
    ]
    if unexpected:
        raise RuntimeError(f"artefatos inesperados: {unexpected}")
    print(f"Artefatos validados: {len(DISTRIBUTIONS) * 2}")  # noqa: T201


if __name__ == "__main__":
    main()
