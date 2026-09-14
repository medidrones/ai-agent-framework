from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

from atlas_agents import AtlasDeprecationWarning, __version__

REPOSITORY = Path(__file__).parents[4]
PACKAGES = REPOSITORY / "packages"
DISTRIBUTIONS = {
    "atlas-agent": "atlas-agent-framework",
    "atlas-agent-adapters": "atlas-agent-adapters",
    "atlas-agent-config": "atlas-agent-config",
    "atlas-agent-core": "atlas-agent-core",
    "atlas-agent-evaluation": "atlas-agent-evaluation",
    "atlas-agent-mcp": "atlas-agent-mcp",
    "atlas-agent-providers": "atlas-agent-providers",
}
OPTIONAL_VENDOR_PACKAGES = {"fastapi", "grpcio", "mcp", "openai", "pyyaml"}
DEV_TOOLS = {"grpcio-tools", "mypy", "pytest", "ruff", "twine"}


def metadata(package_directory: str) -> dict[str, object]:
    path = PACKAGES / package_directory / "pyproject.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def requirements(values: list[str]) -> tuple[Requirement, ...]:
    return tuple(Requirement(value) for value in values)


def test_all_distributions_use_one_pep440_lockstep_version() -> None:
    expected = (REPOSITORY / "VERSION").read_text(encoding="utf-8").strip()
    assert str(Version(expected)) == expected
    assert __version__ == expected
    for package_directory in DISTRIBUTIONS:
        package = metadata(package_directory)
        project = package["project"]
        assert isinstance(project, dict)
        assert project["dynamic"] == ["version"]
        tool = package["tool"]
        assert isinstance(tool, dict)
        hatch = tool["hatch"]
        assert isinstance(hatch, dict)
        version_config = hatch["version"]
        assert isinstance(version_config, dict)
        version_path = version_config["path"]
        source = (PACKAGES / package_directory / str(version_path)).read_text(
            encoding="utf-8"
        )
        assert re.search(rf'__version__ = "{re.escape(expected)}"', source)


def test_distribution_metadata_is_complete_and_consistent() -> None:
    for package_directory, distribution in DISTRIBUTIONS.items():
        project = metadata(package_directory)["project"]
        assert isinstance(project, dict)
        assert project["name"] == distribution
        assert project["requires-python"] == ">=3.12"
        assert project["license"] == "MIT"
        assert project["readme"] == "README.md"
        assert project["authors"]
        assert project["maintainers"]
        assert "Programming Language :: Python :: 3.12" in project["classifiers"]
        assert "Programming Language :: Python :: 3.13" in project["classifiers"]
        assert set(project["urls"]) == {"Documentation", "Issues", "Repository"}


def test_meta_package_does_not_reuse_the_occupied_public_name() -> None:
    project = metadata("atlas-agent")["project"]
    assert isinstance(project, dict)
    assert project["name"] == "atlas-agent-framework"
    assert "atlas-agent" not in DISTRIBUTIONS.values()

    workspace = tomllib.loads((REPOSITORY / "pyproject.toml").read_text("utf-8"))
    sources = workspace["tool"]["uv"]["sources"]
    assert "atlas-agent-framework" in sources
    assert "atlas-agent" not in sources


def test_runtime_dependencies_exclude_dev_tools_and_local_references() -> None:
    for package_directory in DISTRIBUTIONS:
        project = metadata(package_directory)["project"]
        assert isinstance(project, dict)
        declared = list(project.get("dependencies", []))
        optional = project.get("optional-dependencies", {})
        assert isinstance(optional, dict)
        declared.extend(item for values in optional.values() for item in values)
        parsed = requirements(declared)
        assert DEV_TOOLS.isdisjoint(item.name.casefold() for item in parsed)
        assert not any("file:" in str(item) or "git+" in str(item) for item in parsed)


def test_core_is_minimal_and_vendor_dependencies_are_isolated() -> None:
    core_project = metadata("atlas-agent-core")["project"]
    assert isinstance(core_project, dict)
    core_names = {
        item.name.casefold() for item in requirements(core_project["dependencies"])
    }
    assert OPTIONAL_VENDOR_PACKAGES.isdisjoint(core_names)

    providers = metadata("atlas-agent-providers")["project"]
    adapters = metadata("atlas-agent-adapters")["project"]
    assert isinstance(providers, dict)
    assert isinstance(adapters, dict)
    assert "openai" not in {
        item.name.casefold() for item in requirements(providers["dependencies"])
    }
    assert set(providers["optional-dependencies"]) == {"openai"}
    assert {"fastapi", "grpcio"}.isdisjoint(
        item.name.casefold() for item in requirements(adapters["dependencies"])
    )
    assert set(adapters["optional-dependencies"]) == {"grpc", "rest"}


def test_internal_distribution_graph_is_acyclic() -> None:
    graph: dict[str, set[str]] = {}
    for package_directory, distribution in DISTRIBUTIONS.items():
        project = metadata(package_directory)["project"]
        assert isinstance(project, dict)
        values = list(project.get("dependencies", []))
        optional = project.get("optional-dependencies", {})
        assert isinstance(optional, dict)
        values.extend(item for group in optional.values() for item in group)
        graph[distribution] = {
            item.name
            for item in requirements(values)
            if item.name in DISTRIBUTIONS.values()
        }

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise AssertionError(f"Ciclo de dependência detectado em {node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for distribution in DISTRIBUTIONS.values():
        visit(distribution)


def test_optional_import_boundaries_are_not_eager() -> None:
    providers = (
        PACKAGES
        / "atlas-agent-providers"
        / "src"
        / "atlas_agents"
        / "providers"
        / "__init__.py"
    ).read_text(encoding="utf-8")
    adapters = (
        PACKAGES
        / "atlas-agent-adapters"
        / "src"
        / "atlas_agents"
        / "adapters"
        / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "providers.openai" not in providers
    assert "adapters.rest" not in adapters
    assert "adapters.grpc" not in adapters


def test_every_typed_distribution_declares_and_contains_py_typed() -> None:
    markers = {
        "atlas-agent": "src/atlas_agent/py.typed",
        "atlas-agent-adapters": "src/atlas_agents/adapters/py.typed",
        "atlas-agent-config": "src/atlas_agents/config/py.typed",
        "atlas-agent-core": "src/atlas_agents/py.typed",
        "atlas-agent-evaluation": "src/atlas_agents/evaluation/py.typed",
        "atlas-agent-mcp": "src/atlas_agents/mcp/py.typed",
        "atlas-agent-providers": "src/atlas_agents/providers/openai/py.typed",
    }
    for package_directory, marker in markers.items():
        assert (PACKAGES / package_directory / marker).is_file()


def test_deprecation_warning_is_visible_to_application_consumers() -> None:
    assert issubclass(AtlasDeprecationWarning, FutureWarning)
