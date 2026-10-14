"""Validate and summarize raw DS-015 benchmark evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples" / "kubernetes-recovery" / "src"))

from atlas_kubernetes_recovery.performance_summary import summarize  # noqa: E402


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("O resultado deve ser um objeto JSON.")
    return value


def main() -> None:
    """Parse raw files and print a deterministic JSON summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    arguments = parser.parse_args()
    summaries = [summarize(_load(path)) for path in arguments.reports]
    print(json.dumps(summaries, ensure_ascii=False, indent=2, sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
