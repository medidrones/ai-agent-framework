import ast
from pathlib import Path

import atlas_agents

CORE = Path(__file__).parents[2] / "src" / "atlas_agents"
ORCHESTRATION = CORE / "orchestration"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_or001_t26_t27_orchestration_has_no_infrastructure_imports() -> None:
    forbidden = {
        "asyncpg",
        "celery",
        "fastapi",
        "kubernetes",
        "psycopg",
        "ray",
        "redis",
        "sqlalchemy",
        "temporalio",
        "atlas_agents.adapters",
        "atlas_agents.providers",
    }
    imported = {name for path in ORCHESTRATION.rglob("*.py") for name in _imports(path)}
    assert not any(
        name == item or name.startswith(f"{item}.")
        for name in imported
        for item in forbidden
    )


def test_or001_t28_orchestration_imports_without_cycle() -> None:
    assert atlas_agents.WorkflowDefinition.__module__.startswith(
        "atlas_agents.orchestration"
    )


def test_or001_t29_agent_runtime_does_not_depend_on_orchestration() -> None:
    runtime_source = (CORE / "runtime" / "runtime.py").read_text(encoding="utf-8")
    assert "WorkflowOrchestrator" not in runtime_source
    assert "atlas_agents.orchestration" not in runtime_source


def test_or001_does_not_implement_scheduler_or_engine() -> None:
    forbidden_classes = {
        "Scheduler",
        "WorkflowEngine",
        "DistributedWorker",
        "MessageBroker",
    }
    declared = {
        node.name
        for path in ORCHESTRATION.rglob("*.py")
        for node in ast.walk(
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        )
        if isinstance(node, ast.ClassDef)
    }
    assert declared.isdisjoint(forbidden_classes)


def test_or001_has_no_dynamic_execution_or_unsafe_serialization() -> None:
    forbidden_calls = {"eval", "exec", "__import__"}
    forbidden_imports = {"pickle", "shelve", "subprocess"}
    for path in ORCHESTRATION.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert forbidden_calls.isdisjoint(calls)
        assert forbidden_imports.isdisjoint(_imports(path))
