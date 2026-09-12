import ast
from pathlib import Path

import atlas_agents.evaluation as evaluation


def import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.partition(".")[0])
    return roots


def test_evaluation_distribution_depends_on_core_without_inverse_dependency() -> None:
    package_root = Path(__file__).parents[1]
    repository_root = package_root.parents[1]
    evaluation_project = (package_root / "pyproject.toml").read_text(encoding="utf-8")
    core_root = repository_root / "packages" / "atlas-agent-core"
    core_project = (core_root / "pyproject.toml").read_text(encoding="utf-8")
    core_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (core_root / "src" / "atlas_agents").rglob("*.py")
    )

    assert "atlas-agent-core" in evaluation_project
    assert "atlas-agent-evaluation" not in core_project
    assert "atlas_agents.evaluation" not in core_sources


def test_evaluation_has_no_vendor_or_infrastructure_dependency() -> None:
    source_root = Path(__file__).parents[1] / "src" / "atlas_agents" / "evaluation"
    forbidden = {
        "anthropic",
        "azure",
        "chromadb",
        "datadog",
        "openai",
        "opentelemetry",
        "prometheus_client",
        "redis",
        "sqlalchemy",
    }

    for path in source_root.rglob("*.py"):
        assert import_roots(path).isdisjoint(forbidden)


def test_public_api_exposes_required_framework_contracts() -> None:
    expected = {
        "EvaluationCase",
        "EvaluationDataset",
        "EvaluationExpectation",
        "EvaluationObservation",
        "Evaluator",
        "EvaluationContext",
        "EvaluationMetric",
        "EvaluationScore",
        "EvaluationResult",
        "EvaluationReport",
        "EvaluationRunner",
        "EvaluationSummary",
    }

    assert expected <= set(evaluation.__all__)
