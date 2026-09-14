from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_module() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[4]
        / "scripts"
        / "release"
        / "assemble_rc_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("assemble_rc_evidence", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_junit_aggregates_suite_counters(tmp_path: Path) -> None:
    module = _load_module()
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuites><testsuite tests="5" failures="1" errors="1" '
        'skipped="1" /></testsuites>',
        encoding="utf-8",
    )

    summary = module.parse_junit(report)

    assert summary.total == 5
    assert summary.passed == 2
    assert summary.failed == 1
    assert summary.errors == 1
    assert summary.skipped == 1


def test_verify_checksums_accepts_valid_inventory(tmp_path: Path) -> None:
    module = _load_module()
    artifact = tmp_path / "artifact.whl"
    artifact.write_bytes(b"atlas")
    digest = hashlib.sha256(b"atlas").hexdigest()
    (tmp_path / "SHA256SUMS").write_text(f"{digest}  artifact.whl\n", encoding="utf-8")

    assert module.verify_checksums(tmp_path) == {"artifact.whl": digest}


def test_verify_checksums_rejects_modified_artifact(tmp_path: Path) -> None:
    module = _load_module()
    artifact = tmp_path / "artifact.whl"
    artifact.write_bytes(b"alterado")
    (tmp_path / "SHA256SUMS").write_text(
        f"{'0' * 64}  artifact.whl\n", encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="Checksum divergente"):
        module.verify_checksums(tmp_path)


def test_select_test_cases_reports_matching_successes(tmp_path: Path) -> None:
    module = _load_module()
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuites><testsuite tests="2"><testcase classname="runtime" '
        'name="test_stress[100]" time="0.25"/><testcase classname="other" '
        'name="test_unrelated" time="0.01"/></testsuite></testsuites>',
        encoding="utf-8",
    )

    assert module.select_test_cases(report, name_prefix="test_stress") == [
        {
            "classname": "runtime",
            "name": "test_stress[100]",
            "seconds": 0.25,
            "status": "PASS",
        }
    ]


def test_coverage_rate_combines_lines_and_branches(tmp_path: Path) -> None:
    module = _load_module()
    report = tmp_path / "coverage.xml"
    report.write_text(
        '<coverage lines-valid="80" lines-covered="72" branches-valid="20" '
        'branches-covered="18"/>',
        encoding="utf-8",
    )

    assert module.coverage_rate(report) == 0.90


def test_generated_reports_do_not_invalidate_clean_source() -> None:
    module = _load_module()
    status = (
        " M reports/release/architecture-audit.json\n"
        "?? release/1.0.0rc2/test-summary.json\n"
        " M packages/atlas-agent-core/pyproject.toml\n"
    )

    assert module.unexpected_source_changes(status) == [
        " M packages/atlas-agent-core/pyproject.toml"
    ]
