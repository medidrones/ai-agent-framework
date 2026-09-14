"""Validate and assemble the immutable evidence bundle for an Atlas RC."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
DIST = REPOSITORY / "dist"
REPORTS = REPOSITORY / "reports" / "release"
RELEASES = REPOSITORY / "release"
DISTRIBUTIONS = (
    "atlas_agent_framework",
    "atlas_agent_adapters",
    "atlas_agent_config",
    "atlas_agent_core",
    "atlas_agent_evaluation",
    "atlas_agent_mcp",
    "atlas_agent_providers",
)
REQUIRED_REPORTS = (
    "architecture-audit.json",
    "artifact-security.json",
    "bandit.json",
    "coverage.xml",
    "dependency-audit.json",
    "junit.xml",
    "performance-baseline.json",
    "public-api.json",
    "static-security.json",
)


@dataclass(frozen=True)
class TestSummary:
    """Aggregate counters extracted from a JUnit report."""

    total: int
    passed: int
    failed: int
    errors: int
    skipped: int


def _run_git(*arguments: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git não foi encontrado para validar a candidata.")
    result = subprocess.run(  # noqa: S603
        (git, *arguments),
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.rstrip()


def unexpected_source_changes(status: str) -> list[str]:
    """Return source changes that do not belong to generated release evidence."""
    generated_prefixes = ("reports/release/", "release/", "dist/")
    unexpected = []
    for line in status.splitlines():
        path = line[3:].replace("\\", "/")
        if not path.startswith(generated_prefixes):
            unexpected.append(line)
    return unexpected


def parse_junit(path: Path) -> TestSummary:
    """Read test totals from either JUnit root representation."""
    root = ET.parse(path).getroot()  # noqa: S314
    suites = (root,) if root.tag == "testsuite" else tuple(root.findall("testsuite"))
    total = sum(int(suite.attrib.get("tests", 0)) for suite in suites)
    failed = sum(int(suite.attrib.get("failures", 0)) for suite in suites)
    errors = sum(int(suite.attrib.get("errors", 0)) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", 0)) for suite in suites)
    return TestSummary(
        total=total,
        passed=total - failed - errors - skipped,
        failed=failed,
        errors=errors,
        skipped=skipped,
    )


def select_test_cases(path: Path, *, name_prefix: str) -> list[dict[str, object]]:
    """Select successful JUnit cases whose names start with a stable prefix."""
    root = ET.parse(path).getroot()  # noqa: S314
    cases = []
    for case in root.iter("testcase"):
        name = case.attrib.get("name", "")
        if not name.startswith(name_prefix):
            continue
        cases.append(
            {
                "classname": case.attrib.get("classname", ""),
                "name": name,
                "seconds": float(case.attrib.get("time", 0)),
                "status": (
                    "FAIL"
                    if case.find("failure") is not None
                    or case.find("error") is not None
                    else "PASS"
                ),
            }
        )
    return cases


def coverage_rate(path: Path) -> float:
    """Return combined statement and branch coverage from Coverage.py XML."""
    root = ET.parse(path).getroot()  # noqa: S314
    valid = int(root.attrib["lines-valid"]) + int(root.attrib["branches-valid"])
    covered = int(root.attrib["lines-covered"]) + int(root.attrib["branches-covered"])
    if not valid:
        raise RuntimeError("O relatório de coverage não contém pontos medidos.")
    return covered / valid


def verify_checksums(dist: Path) -> dict[str, str]:
    """Validate every entry in ``SHA256SUMS`` and return its inventory."""
    checksum_file = dist / "SHA256SUMS"
    if not checksum_file.is_file():
        raise RuntimeError("SHA256SUMS não foi encontrado.")
    checksums: dict[str, str] = {}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        artifact = dist / name
        if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError(f"Linha inválida em SHA256SUMS: {line!r}")
        if not artifact.is_file():
            raise RuntimeError(f"Artefato listado não encontrado: {name}")
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual != digest:
            raise RuntimeError(f"Checksum divergente: {name}")
        checksums[name] = digest
    return checksums


def _validate_source(version: str, *, require_tag: bool) -> tuple[str, str]:
    revision = _run_git("rev-parse", "HEAD")
    status = _run_git("status", "--porcelain", "--untracked-files=all")
    unexpected = unexpected_source_changes(status)
    if unexpected:
        rendered = ", ".join(unexpected)
        raise RuntimeError(
            f"A fonte da candidata possui alterações não rastreadas: {rendered}"
        )
    tag = f"v{version}"
    if require_tag:
        if _run_git("cat-file", "-t", tag) != "tag":
            raise RuntimeError(f"A tag {tag} deve ser anotada.")
        tagged_revision = _run_git("rev-list", "-n", "1", tag)
        if tagged_revision != revision:
            raise RuntimeError(f"A tag {tag} não identifica o commit atual.")
    return revision, tag


def _validate_reports(revision: str) -> TestSummary:
    missing = [name for name in REQUIRED_REPORTS if not (REPORTS / name).is_file()]
    if missing:
        raise RuntimeError(f"Evidências obrigatórias ausentes: {', '.join(missing)}")
    summary = parse_junit(REPORTS / "junit.xml")
    if summary.failed or summary.errors or not summary.total:
        raise RuntimeError("A suíte obrigatória não está integralmente aprovada.")
    if coverage_rate(REPORTS / "coverage.xml") < 0.90:
        raise RuntimeError("Coverage abaixo do threshold bloqueante de 90%.")
    architecture = json.loads(
        (REPORTS / "architecture-audit.json").read_text(encoding="utf-8")
    )
    if architecture.get("revision") != revision or architecture.get("cycles"):
        raise RuntimeError("A auditoria de arquitetura não corresponde à candidata.")
    artifact_security = json.loads(
        (REPORTS / "artifact-security.json").read_text(encoding="utf-8")
    )
    static_security = json.loads(
        (REPORTS / "static-security.json").read_text(encoding="utf-8")
    )
    bandit = json.loads((REPORTS / "bandit.json").read_text(encoding="utf-8"))
    dependency = json.loads(
        (REPORTS / "dependency-audit.json").read_text(encoding="utf-8")
    )
    vulnerabilities = [
        vulnerability
        for item in dependency.get("dependencies", [])
        for vulnerability in item.get("vulns", [])
    ]
    if (
        artifact_security.get("secret_findings")
        or static_security.get("high_risk_findings")
        or bandit.get("results")
        or vulnerabilities
    ):
        raise RuntimeError("A auditoria de segurança contém finding bloqueante.")
    return summary


def _artifact_inventory(version: str) -> list[dict[str, object]]:
    paths: list[Path] = []
    for distribution in DISTRIBUTIONS:
        wheel = DIST / f"{distribution}-{version}-py3-none-any.whl"
        sdist = DIST / f"{distribution}-{version}.tar.gz"
        if not wheel.is_file() or not sdist.is_file():
            raise RuntimeError(f"Artefatos incompletos para {distribution}.")
        paths.extend((wheel, sdist))
    return [
        {
            "file": path.name,
            "kind": "wheel" if path.suffix == ".whl" else "sdist",
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in paths
    ]


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def assemble(*, require_tag: bool) -> Path:
    """Validate current evidence and create the candidate bundle."""
    version = (REPOSITORY / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+rc\d+", version):
        raise RuntimeError("VERSION não identifica uma release candidate.")
    revision, tag = _validate_source(version, require_tag=require_tag)
    summary = _validate_reports(revision)
    inventory = _artifact_inventory(version)
    checksums = verify_checksums(DIST)

    destination = (RELEASES / version).resolve()
    if destination.parent != RELEASES.resolve():
        raise RuntimeError("Destino do bundle fora do diretório de releases.")
    if destination.exists():
        shutil.rmtree(destination)
    wheels = destination / "wheels"
    sdists = destination / "sdists"
    wheels.mkdir(parents=True)
    sdists.mkdir()
    for item in inventory:
        name = str(item["file"])
        shutil.copy2(
            DIST / name, (wheels if item["kind"] == "wheel" else sdists) / name
        )
    shutil.copy2(DIST / "SHA256SUMS", destination / "SHA256SUMS")
    shutil.copy2(DIST / "atlas-agent-framework.cdx.json", destination / "sbom.cdx.json")
    shutil.copy2(
        REPOSITORY / "docs/release/release-readiness.md",
        destination / "release-readiness.md",
    )
    shutil.copy2(REPORTS / "coverage.xml", destination / "coverage.xml")
    shutil.copy2(
        REPORTS / "architecture-audit.json", destination / "architecture-audit.json"
    )
    shutil.copy2(
        REPORTS / "dependency-audit.json", destination / "dependency-audit.json"
    )
    shutil.copy2(
        REPORTS / "performance-baseline.json", destination / "benchmark-report.json"
    )
    shutil.copy2(
        REPOSITORY / "docs/compatibility.md", destination / "compatibility-matrix.md"
    )
    security = {
        "bandit": json.loads((REPORTS / "bandit.json").read_text(encoding="utf-8")),
        "static": json.loads(
            (REPORTS / "static-security.json").read_text(encoding="utf-8")
        ),
        "artifacts": json.loads(
            (REPORTS / "artifact-security.json").read_text(encoding="utf-8")
        ),
    }
    _write_json(destination / "security-audit.json", security)
    _write_json(destination / "artifact-inventory.json", inventory)
    _write_json(
        destination / "test-summary.json",
        {
            "revision": revision,
            "tag": tag,
            "version": version,
            **summary.__dict__,
        },
    )
    junit = REPORTS / "junit.xml"
    stress_cases = select_test_cases(
        junit, name_prefix="test_one_hundred_concurrent_executions_remain_isolated"
    )
    example_cases = select_test_cases(
        junit, name_prefix="test_offline_python_example_executes"
    )
    if len(stress_cases) != 1 or not example_cases:
        raise RuntimeError("JUnit não contém as evidências de stress e exemplos.")
    _write_json(
        destination / "stress-report.json",
        {"scenario": "100 execuções concorrentes isoladas", "cases": stress_cases},
    )
    _write_json(
        destination / "examples-report.json",
        {
            "offline_examples": len(example_cases),
            "enterprise_reference": any(
                "22_enterprise_reference" in str(item["name"]) for item in example_cases
            ),
            "cases": example_cases,
        },
    )
    _write_json(
        destination / "automated-gates.json",
        {
            "release": version,
            "revision": revision,
            "tag": tag if require_tag else None,
            "technical_status": "PASS",
            "scope": (
                "fonte, qualidade, arquitetura, segurança, runtime, integrações, "
                "artefatos, compatibilidade e documentação"
            ),
            "checksums_verified": len(checksums),
            "owner_sign_offs": "NOT_VERIFIED",
            "final_decision": "NOT_READY",
            "note": (
                "Os gates técnicos passaram. READY_FOR_STABLE exige os cinco "
                "sign-offs explícitos e não é declarado por este script."
            ),
        },
    )
    (destination / "owner-sign-offs.md").write_text(
        "# Sign-offs da candidata\n\n"
        "| Área | Owner | Decisão | Data |\n"
        "| --- | --- | --- | --- |\n"
        "| Architecture | Architecture Owner | NOT_VERIFIED | |\n"
        "| Engineering | Engineering Owner | NOT_VERIFIED | |\n"
        "| QA | QA Owner | NOT_VERIFIED | |\n"
        "| Security | Security Owner | NOT_VERIFIED | |\n"
        "| Release Engineering | Release Owner | NOT_VERIFIED | |\n",
        encoding="utf-8",
    )
    return destination


def main() -> None:
    """Parse arguments and assemble a release candidate evidence bundle."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-untagged",
        action="store_true",
        help="permite diagnóstico local sem tag; proibido para certificação",
    )
    arguments = parser.parse_args()
    destination = assemble(require_tag=not arguments.allow_untagged)
    print(f"Bundle de evidências criado em {destination.relative_to(REPOSITORY)}")  # noqa: T201


if __name__ == "__main__":
    main()
