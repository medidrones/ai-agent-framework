"""Executable contracts for the official examples."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[4]
EXAMPLES = ROOT / "examples"
DIRECTORIES = tuple(
    f"{index:02d}_{name}"
    for index, name in enumerate(
        (
            "minimal_agent",
            "openai_agent",
            "streaming",
            "structured_output",
            "tools",
            "multi_turn",
            "human_in_the_loop",
            "memory",
            "knowledge_rag",
            "guardrails",
            "observability",
            "evaluation",
            "plugins",
            "mcp_client",
            "mcp_server",
            "rest",
            "grpc",
            "event_driven",
            "declarative_config",
            "dotnet_rest",
            "dotnet_grpc",
            "enterprise_reference",
        ),
        start=1,
    )
)
OFFLINE_PYTHON_EXAMPLES = tuple(
    directory
    for directory in DIRECTORIES
    if directory
    not in {
        "02_openai_agent",
        "20_dotnet_rest",
        "21_dotnet_grpc",
    }
)
REQUIRED_SECTIONS = (
    "## Propósito",
    "## Conceitos demonstrados",
    "## Arquitetura",
    "## Pré-requisitos",
    "## Instalação",
    "## Como executar",
    "## Saída esperada",
    "## Segurança",
    "## Considerações para produção",
    "## Pacotes Atlas relacionados",
)


def test_all_official_example_directories_have_complete_portuguese_readme() -> None:
    found = tuple(
        sorted(
            path.name
            for path in EXAMPLES.iterdir()
            if path.is_dir() and path.name[:2].isdigit()
        )
    )
    assert found == DIRECTORIES
    for directory in DIRECTORIES:
        content = (EXAMPLES / directory / "README.md").read_text(encoding="utf-8")
        assert all(section in content for section in REQUIRED_SECTIONS)


def test_framework_packages_never_import_examples() -> None:
    for source in (ROOT / "packages").glob("*/src/**/*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        imported = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]
        imported.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(
            module == "examples" or module.startswith("examples.")
            for module in imported
        )


def test_examples_do_not_import_private_atlas_modules() -> None:
    for source in EXAMPLES.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        modules = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]
        assert not any(
            module.startswith("atlas_agents.")
            and any(part.startswith("_") for part in module.split("."))
            for module in modules
        )


@pytest.mark.parametrize("directory", OFFLINE_PYTHON_EXAMPLES)
def test_offline_python_example_executes(directory: str) -> None:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(EXAMPLES / directory / "main.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
