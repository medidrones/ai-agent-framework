"""Compare release metadata and file manifests across independent builds."""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
DIST = REPOSITORY / "dist"
VERSION = (REPOSITORY / "VERSION").read_text(encoding="utf-8").strip()
UV = shutil.which("uv")
DISTRIBUTIONS = {
    "atlas-agent": "atlas_agent",
    "atlas-agent-adapters": "atlas_agent_adapters",
    "atlas-agent-config": "atlas_agent_config",
    "atlas-agent-core": "atlas_agent_core",
    "atlas-agent-evaluation": "atlas_agent_evaluation",
    "atlas-agent-mcp": "atlas_agent_mcp",
    "atlas-agent-providers": "atlas_agent_providers",
}


def _wheel_signature(path: Path) -> tuple[tuple[str, ...], bytes]:
    with zipfile.ZipFile(path) as archive:
        names = tuple(sorted(archive.namelist()))
        metadata_name = next(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        return names, archive.read(metadata_name)


def _sdist_manifest(path: Path) -> tuple[str, ...]:
    with tarfile.open(path, "r:gz") as archive:
        return tuple(sorted(archive.getnames()))


def main() -> None:
    """Rebuild every distribution and compare its release-relevant contents."""
    if UV is None:
        raise RuntimeError("Executável uv não encontrado")
    with tempfile.TemporaryDirectory(prefix="atlas-rebuild-") as temporary:
        rebuilt = Path(temporary)
        for distribution, normalized in DISTRIBUTIONS.items():
            subprocess.run(  # noqa: S603
                (
                    UV,
                    "build",
                    "--package",
                    distribution,
                    "--out-dir",
                    str(rebuilt),
                ),
                cwd=REPOSITORY,
                check=True,
            )
            original_wheel = DIST / f"{normalized}-{VERSION}-py3-none-any.whl"
            rebuilt_wheel = rebuilt / original_wheel.name
            if _wheel_signature(original_wheel) != _wheel_signature(rebuilt_wheel):
                raise RuntimeError(f"wheel não reproduzível: {distribution}")

            original_sdist = DIST / f"{normalized}-{VERSION}.tar.gz"
            rebuilt_sdist = rebuilt / original_sdist.name
            if _sdist_manifest(original_sdist) != _sdist_manifest(rebuilt_sdist):
                raise RuntimeError(f"sdist não reproduzível: {distribution}")
    print("Metadados e manifestos reproduzíveis validados")  # noqa: T201


if __name__ == "__main__":
    main()
