"""Architecture tests for forbidden dependencies in the core package."""

import ast
from pathlib import Path

FORBIDDEN_IMPORTS = frozenset(
    {
        "anthropic",
        "fastapi",
        "openai",
        "opensearch",
        "qdrant",
        "redis",
        "sqlalchemy",
    }
)


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.partition(".")[0])
    return roots


def test_core_does_not_import_forbidden_dependencies() -> None:
    source_root = Path(__file__).parents[2] / "src" / "atlas_agents"
    violations: dict[str, list[str]] = {}
    for path in source_root.rglob("*.py"):
        forbidden = _import_roots(path) & FORBIDDEN_IMPORTS
        if forbidden:
            violations[str(path.relative_to(source_root))] = sorted(forbidden)

    assert violations == {}
