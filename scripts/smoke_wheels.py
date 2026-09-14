"""Install locally built wheels into isolated environments and smoke-test them."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
DIST = REPOSITORY / "dist"
VERSION = (REPOSITORY / "VERSION").read_text(encoding="utf-8").strip()


def _run(*arguments: str) -> None:
    subprocess.run(arguments, cwd=REPOSITORY, check=True)  # noqa: S603


def _python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if shutil.which("cmd") else "bin/python")


def _create_environment(root: Path, name: str) -> tuple[Path, Path]:
    environment = root / name
    _run("uv", "venv", "--python", "3.12", str(environment))
    return environment, _python(environment)


def _install_external(python: Path, *requirements: str) -> None:
    _run("uv", "pip", "install", "--python", str(python), *requirements)


def _install_wheels(python: Path, *distribution_names: str) -> None:
    wheels = [
        str(next(DIST.glob(f"{name}-{VERSION}-py3-none-any.whl")))
        for name in distribution_names
    ]
    _run("uv", "pip", "install", "--python", str(python), "--no-deps", *wheels)


def _execute(python: Path, source: str) -> None:
    _run(str(python), "-I", "-c", source)


def main() -> None:
    """Validate minimal, extension-base and complete wheel installations."""
    with tempfile.TemporaryDirectory(prefix="atlas-wheel-smoke-") as temporary:
        root = Path(temporary)
        _, core_python = _create_environment(root, "core")
        _install_external(
            core_python,
            "jsonschema>=4.26,<5",
            "packaging>=26,<27",
            "pydantic>=2.13,<3",
            "typing-extensions>=4.16,<5",
        )
        _install_wheels(core_python, "atlas_agent_core")
        _execute(
            core_python,
            "import sys; import atlas_agents; "
            "from atlas_agents import AgentRuntime, ModelProviderRegistry; "
            "AgentRuntime(model_registry=ModelProviderRegistry()); "
            "assert not {'openai','mcp','fastapi','grpc'} & set(sys.modules)",
        )
        _run("uv", "pip", "check", "--python", str(core_python))

        _, base_python = _create_environment(root, "extensions-base")
        _install_external(
            base_python,
            "jsonschema>=4.26,<5",
            "packaging>=26,<27",
            "pydantic>=2.13,<3",
            "typing-extensions>=4.16,<5",
        )
        _install_wheels(
            base_python,
            "atlas_agent_core",
            "atlas_agent_adapters",
            "atlas_agent_providers",
        )
        _execute(
            base_python,
            "import atlas_agents.adapters, atlas_agents.providers; "
            "assert 'fastapi' not in __import__('sys').modules; "
            "assert 'grpc' not in __import__('sys').modules; "
            "assert 'openai' not in __import__('sys').modules",
        )
        _execute(
            base_python,
            """from atlas_agents.adapters import MissingAdapterDependencyError
from atlas_agents.providers import MissingProviderDependencyError


def check(module, expected, extra):
    try:
        __import__(module)
    except expected as error:
        assert extra in str(error)
    else:
        raise AssertionError(module)


check("atlas_agents.adapters.rest", MissingAdapterDependencyError, "[rest]")
check("atlas_agents.adapters.grpc", MissingAdapterDependencyError, "[grpc]")
check("atlas_agents.providers.openai", MissingProviderDependencyError, "[openai]")
""",
        )
        _run("uv", "pip", "check", "--python", str(base_python))

        _, full_python = _create_environment(root, "full")
        _install_external(
            full_python,
            "fastapi>=0.141,<1",
            "grpcio>=1.81.1,<2",
            "jsonschema>=4.26,<5",
            "mcp>=2.2,<3",
            "openai>=3.13,<4",
            "packaging>=26,<27",
            "protobuf>=6.33.5,<7",
            "pydantic>=2.13,<3",
            "pyyaml>=6,<7",
            "typing-extensions>=4.16,<5",
        )
        _install_wheels(
            full_python,
            "atlas_agent",
            "atlas_agent_adapters",
            "atlas_agent_config",
            "atlas_agent_core",
            "atlas_agent_evaluation",
            "atlas_agent_mcp",
            "atlas_agent_providers",
        )
        _execute(
            full_python,
            "from importlib.metadata import entry_points; "
            "import atlas_agent, atlas_agents, atlas_agents.adapters; "
            "import atlas_agents.adapters.grpc, atlas_agents.adapters.rest; "
            "import atlas_agents.config, atlas_agents.evaluation, atlas_agents.mcp; "
            "import atlas_agents.providers, atlas_agents.providers.openai; "
            "assert all(module.__version__ == atlas_agent.__version__ for module in "
            "(atlas_agents, atlas_agents.adapters, atlas_agents.config, "
            "atlas_agents.evaluation, atlas_agents.mcp, atlas_agents.providers)); "
            "assert any(e.name == 'openai' for e in "
            "entry_points(group='atlas_agents.plugins'))",
        )
        _run("uv", "pip", "check", "--python", str(full_python))
    print("Smoke tests dos wheels concluídos em ambientes isolados")  # noqa: T201


if __name__ == "__main__":
    main()
