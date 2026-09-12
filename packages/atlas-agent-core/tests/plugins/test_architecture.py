"""Security and dependency guards for the plugin subsystem."""

import ast
from pathlib import Path


def test_plugins_use_standard_entry_points_without_unsafe_execution() -> None:
    root = Path(__file__).parents[2] / "src" / "atlas_agents" / "plugins"
    sources = {
        path.name: path.read_text(encoding="utf-8") for path in root.glob("*.py")
    }
    combined = "\n".join(sources.values())

    assert "importlib.metadata" in combined
    assert "pkg_resources" not in combined
    assert "pluggy" not in combined
    assert "stevedore" not in combined
    assert "dependency_injector" not in combined
    assert "activate_all" not in combined
    assert "subprocess" not in combined
    assert "os.environ" not in combined
    assert "os.getenv" not in combined
    assert "dotenv" not in combined
    assert "get_service" not in combined
    assert "require_service" not in combined

    forbidden_calls = {"eval", "exec", "__import__"}
    for name, source in sources.items():
        tree = ast.parse(source, filename=name)
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert forbidden_calls.isdisjoint(called)


def test_plugin_manager_does_not_depend_on_agent_runtime_or_evaluation() -> None:
    path = Path(__file__).parents[2] / "src" / "atlas_agents" / "plugins" / "manager.py"
    source = path.read_text(encoding="utf-8")
    assert "AgentRuntime" not in source
    assert "atlas_agents.evaluation" not in source
