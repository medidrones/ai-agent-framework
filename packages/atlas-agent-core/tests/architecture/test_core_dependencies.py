"""Architecture tests for forbidden dependencies in the core package."""

import ast
from pathlib import Path

FORBIDDEN_IMPORTS = frozenset(
    {
        "aio_pika",
        "aiohttp",
        "anthropic",
        "asyncpg",
        "autogen",
        "azure",
        "confluent_kafka",
        "crewai",
        "chromadb",
        "django",
        "fastapi",
        "faiss",
        "flask",
        "google",
        "grpc",
        "httpx",
        "kafka",
        "langchain",
        "langgraph",
        "openai",
        "opensearch",
        "pinecone",
        "pika",
        "psycopg",
        "qdrant",
        "redis",
        "requests",
        "sqlalchemy",
        "weaviate",
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


def test_core_runtime_dependencies_exclude_provider_sdks() -> None:
    package_root = Path(__file__).parents[2]
    pyproject = (package_root / "pyproject.toml").read_text(encoding="utf-8")
    dependencies = (
        pyproject.partition("dependencies = [")[2].partition("]")[0].casefold()
    )
    forbidden_fragments = (
        "anthropic",
        "autogen",
        "azure",
        "crewai",
        "gemini",
        "google-ai",
        "google-genai",
        "langchain",
        "langgraph",
        "openai",
    )

    assert not any(name in dependencies for name in forbidden_fragments)


def test_execution_state_does_not_own_infrastructure_or_execute_providers() -> None:
    source_root = Path(__file__).parents[2] / "src" / "atlas_agents"
    state_path = source_root / "runtime" / "state.py"
    source = state_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(state_path))
    forbidden_names = {
        "ModelProvider",
        "ModelProviderRegistry",
        "get_service",
        "services",
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert _import_roots(state_path) & FORBIDDEN_IMPORTS == set()
    assert forbidden_names.isdisjoint(source.split())
    assert {"generate", "stream", "list_models"}.isdisjoint(called_attributes)


def test_agent_runtime_keeps_provider_execution_modes_separate() -> None:
    source_root = Path(__file__).parents[2] / "src" / "atlas_agents"
    runtime_path = source_root / "runtime" / "runtime.py"
    source = runtime_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(runtime_path))
    called_attributes = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    forbidden_concrete_providers = {
        "AnthropicProvider",
        "AzureProvider",
        "GeminiProvider",
        "GoogleProvider",
        "OpenAIProvider",
    }

    assert _import_roots(runtime_path) & FORBIDDEN_IMPORTS == set()
    assert forbidden_concrete_providers.isdisjoint(source.split())
    assert called_attributes.count("generate") == 1
    assert called_attributes.count("stream") == 2
    assert "get_service" not in source


def test_execution_policies_are_provider_and_infrastructure_agnostic() -> None:
    runtime_root = Path(__file__).parents[2] / "src" / "atlas_agents" / "runtime"
    policy_paths = (
        runtime_root / "budget.py",
        runtime_root / "deadline.py",
        runtime_root / "enforcement.py",
        runtime_root / "limits.py",
    )
    forbidden_names = {
        "ModelProvider",
        "ModelRequest",
        "ExecutionLifecycle",
        "Redis",
        "Database",
    }

    for path in policy_paths:
        source = path.read_text(encoding="utf-8")
        assert _import_roots(path) & FORBIDDEN_IMPORTS == set()
        assert forbidden_names.isdisjoint(source.split())


def test_tools_have_no_service_locator_or_arbitrary_code_execution() -> None:
    tools_root = Path(__file__).parents[2] / "src" / "atlas_agents" / "tools"
    forbidden_names = {
        "ServiceContainer",
        "get_service",
        "require_service",
        "services",
    }
    forbidden_calls = {"eval", "exec", "__import__"}
    forbidden_attributes = {"system", "popen", "Popen"}

    for path in tools_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert _import_roots(path) & FORBIDDEN_IMPORTS == set()
        assert {"subprocess", "importlib"}.isdisjoint(_import_roots(path))
        assert forbidden_names.isdisjoint(names | attributes)
        assert forbidden_calls.isdisjoint(called_names)
        assert forbidden_attributes.isdisjoint(attributes)


def test_agent_runtime_owns_tool_loop_without_infrastructure_dependencies() -> None:
    runtime_path = (
        Path(__file__).parents[2] / "src" / "atlas_agents" / "runtime" / "runtime.py"
    )
    source = runtime_path.read_text(encoding="utf-8")

    assert "ToolExecutor" in source
    assert "ToolRegistry" in source
    assert _import_roots(runtime_path) & FORBIDDEN_IMPORTS == set()
    assert "get_service" not in source


def test_human_approval_has_no_ui_or_concrete_persistence() -> None:
    source_root = Path(__file__).parents[2] / "src" / "atlas_agents"
    paths = tuple((source_root / "approvals").rglob("*.py")) + tuple(
        (source_root / "runtime").glob("*.py")
    )
    forbidden_imports = {
        "pickle",
        "shelve",
        "sqlite3",
        "subprocess",
        "tkinter",
    }
    forbidden_calls = {"input", "eval", "exec", "__import__"}

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert forbidden_imports.isdisjoint(_import_roots(path))
        assert forbidden_calls.isdisjoint(called_names)


def test_memory_contracts_have_no_knowledge_or_infrastructure_coupling() -> None:
    source_root = Path(__file__).parents[2] / "src" / "atlas_agents"
    memory_root = source_root / "memory"
    forbidden_names = {
        "EmbeddingProvider",
        "KnowledgeBase",
        "Retriever",
        "ServiceContainer",
        "VectorStore",
        "get_service",
        "require_service",
    }

    for path in memory_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }

        assert _import_roots(path) & FORBIDDEN_IMPORTS == set()
        assert forbidden_names.isdisjoint(names | attributes)

    tool_context = (source_root / "tools" / "context.py").read_text(encoding="utf-8")
    assert "MemoryManager" not in tool_context
