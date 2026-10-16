from __future__ import annotations

from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[4]


def test_artifact_certification_runs_with_real_state_backends() -> None:
    workflow = (
        REPOSITORY / ".github" / "workflows" / "release-candidate.yml"
    ).read_text(encoding="utf-8")
    certification_job = workflow.split("  certificar-artefatos:\n", maxsplit=1)[1]

    assert "image: postgres:16-alpine" in certification_job
    assert "image: redis:7.4-alpine" in certification_job
    assert "ATLAS_TEST_POSTGRES_DSN:" in certification_job
    assert "ATLAS_TEST_REDIS_URL:" in certification_job
    assert "Registrar JUnit e coverage da fonte imutável" in certification_job
