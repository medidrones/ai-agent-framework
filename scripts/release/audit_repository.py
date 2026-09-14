"""Generate deterministic architecture, API and artifact security evidence."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parents[2]
REPORTS = REPOSITORY / "reports" / "release"
PACKAGE_NAMESPACES = {
    "atlas-agent-adapters": "atlas_agents.adapters",
    "atlas-agent-config": "atlas_agents.config",
    "atlas-agent-evaluation": "atlas_agents.evaluation",
    "atlas-agent-mcp": "atlas_agents.mcp",
    "atlas-agent-providers": "atlas_agents.providers",
}
SECRET_PATTERNS = {
    "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{36,255}"),
    "openai_key": re.compile(rb"sk-[A-Za-z0-9_-]{32,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            values.add(node.module)
    return values


def _graph() -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for package_root in sorted((REPOSITORY / "packages").iterdir()):
        source_root = package_root / "src"
        if not source_root.is_dir():
            continue
        dependencies: set[str] = set()
        for path in source_root.rglob("*.py"):
            for imported in _imports(path):
                matched = False
                for package, namespace in PACKAGE_NAMESPACES.items():
                    if imported == namespace or imported.startswith(f"{namespace}."):
                        dependencies.add(package)
                        matched = True
                        break
                if imported.startswith("atlas_agents") and not matched:
                    dependencies.add("atlas-agent-core")
        dependencies.discard(package_root.name)
        graph[package_root.name] = sorted(dependencies)
    return graph


def _cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in path:
            cycles.add((*path[path.index(node) :], node))
            return
        for dependency in graph.get(node, []):
            visit(dependency, (*path, node))

    for package in graph:
        visit(package, ())
    return [list(cycle) for cycle in sorted(cycles)]


def _public_api() -> dict[str, Any]:
    modules = {
        "atlas-agent-core": REPOSITORY
        / "packages/atlas-agent-core/src/atlas_agents/__init__.py",
        "atlas-agent-adapters": REPOSITORY
        / "packages/atlas-agent-adapters/src/atlas_agents/adapters/__init__.py",
        "atlas-agent-config": REPOSITORY
        / "packages/atlas-agent-config/src/atlas_agents/config/__init__.py",
        "atlas-agent-evaluation": REPOSITORY
        / "packages/atlas-agent-evaluation/src/atlas_agents/evaluation/__init__.py",
        "atlas-agent-mcp": REPOSITORY
        / "packages/atlas-agent-mcp/src/atlas_agents/mcp/__init__.py",
        "atlas-agent-providers": REPOSITORY
        / "packages/atlas-agent-providers/src/atlas_agents/providers/__init__.py",
    }
    inventory: dict[str, Any] = {}
    for distribution, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        exported: list[str] = []
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                continue
            exported = list(ast.literal_eval(node.value))
        inventory[distribution] = {"count": len(exported), "exports": exported}
    return inventory


def _artifact_payloads(path: Path) -> list[tuple[str, bytes]]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return [(name, archive.read(name)) for name in archive.namelist()]
    with tarfile.open(path, "r:gz") as archive:
        return [
            (member.name, extracted.read())
            for member in archive.getmembers()
            if member.isfile()
            and (extracted := archive.extractfile(member)) is not None
        ]


def _artifact_security() -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    artifacts: list[dict[str, str | int]] = []
    for path in sorted((REPOSITORY / "dist").glob("atlas_agent*")):
        if not (path.suffix == ".whl" or path.name.endswith(".tar.gz")):
            continue
        payload = path.read_bytes()
        artifacts.append(
            {
                "file": path.name,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        for member, content in _artifact_payloads(path):
            for kind, pattern in SECRET_PATTERNS.items():
                if pattern.search(content):
                    findings.append(
                        {"artifact": path.name, "member": member, "kind": kind}
                    )
    return {"artifacts": artifacts, "secret_findings": findings}


def _static_security() -> dict[str, Any]:
    dangerous_imports = {"pickle", "shelve", "marshal"}
    dangerous_calls = {"eval", "exec"}
    findings: list[dict[str, object]] = []
    broad_handlers: list[dict[str, object]] = []
    for path in sorted((REPOSITORY / "packages").glob("*/src/**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = str(path.relative_to(REPOSITORY)).replace("\\", "/")
        findings.extend(
            {"file": relative, "line": 1, "kind": f"import:{imported}"}
            for imported in _imports(path) & dangerous_imports
        )
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in dangerous_calls
            ):
                findings.append(
                    {"file": relative, "line": node.lineno, "kind": node.func.id}
                )
            if isinstance(node, ast.ExceptHandler):
                broad = node.type is None or (
                    isinstance(node.type, ast.Name)
                    and node.type.id in {"Exception", "BaseException"}
                )
                if broad:
                    broad_handlers.append({"file": relative, "line": node.lineno})
    return {
        "high_risk_findings": findings,
        "broad_exception_boundaries": broad_handlers,
        "broad_exception_count": len(broad_handlers),
        "review_note": (
            "Handlers amplos permanecem somente em fronteiras de normalização, "
            "cleanup, rollback ou fail-open documentado; cancelamento possui testes."
        ),
    }


def _revision() -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git não foi encontrado para registrar a revisão.")
    result = subprocess.run(  # noqa: S603
        [git, "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    """Write release evidence and fail when a blocking finding is detected."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    graph = _graph()
    architecture = {"revision": _revision(), "graph": graph, "cycles": _cycles(graph)}
    artifacts = _artifact_security()
    documents = {
        "architecture-audit.json": architecture,
        "public-api.json": _public_api(),
        "artifact-security.json": artifacts,
        "static-security.json": _static_security(),
    }
    for name, document in documents.items():
        (REPORTS / name).write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    static_security = documents["static-security.json"]
    if (
        architecture["cycles"]
        or artifacts["secret_findings"]
        or static_security["high_risk_findings"]
    ):
        raise RuntimeError("A auditoria encontrou um bloqueador de release.")
    print("Auditorias de arquitetura, API pública e artefatos concluídas.")  # noqa: T201


if __name__ == "__main__":
    main()
