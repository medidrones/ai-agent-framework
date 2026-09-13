from __future__ import annotations

import ast
from pathlib import Path


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_config_package_does_not_import_provider_or_mcp_implementations() -> None:
    source_root = Path(__file__).parents[1] / "src" / "atlas_agents" / "config"
    forbidden = (
        "atlas_agents.mcp",
        "atlas_agents.providers",
        "openai",
        "mcp",
        "httpx",
        "fastapi",
        "grpc",
    )
    violations: dict[str, list[str]] = {}
    for path in source_root.glob("*.py"):
        matches = sorted(
            module
            for module in imported_modules(path)
            if any(
                module == item or module.startswith(f"{item}.") for item in forbidden
            )
        )
        if matches:
            violations[path.name] = matches
    assert violations == {}


def test_loaders_do_not_execute_or_import_configuration_content() -> None:
    path = Path(__file__).parents[1] / "src" / "atlas_agents" / "config" / "loader.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"eval", "exec", "__import__"}.isdisjoint(called_names)
    assert {"import_module", "getenv", "urlopen"}.isdisjoint(attributes)


def test_core_does_not_depend_on_config_package() -> None:
    core_root = Path(__file__).parents[2] / "atlas-agent-core" / "src" / "atlas_agents"
    violations = [
        str(path.relative_to(core_root))
        for path in core_root.rglob("*.py")
        if "atlas_agents.config" in path.read_text(encoding="utf-8")
    ]
    assert violations == []
