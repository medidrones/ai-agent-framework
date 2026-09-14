"""Create SHA-256 checksums for the candidate release artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
DIST = REPOSITORY / "dist"


def main() -> None:
    """Write checksums in a portable two-column format."""
    artifacts = sorted(
        path
        for path in DIST.iterdir()
        if path.suffix in {".json", ".whl"} or path.name.endswith(".tar.gz")
    )
    if not artifacts:
        raise RuntimeError("Nenhum artefato de distribuição foi encontrado.")
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in artifacts
    ]
    (DIST / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Checksums gerados para {len(artifacts)} artefatos.")  # noqa: T201


if __name__ == "__main__":
    main()
