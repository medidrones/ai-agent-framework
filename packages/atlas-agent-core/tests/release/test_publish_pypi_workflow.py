from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[4] / ".github" / "workflows" / "publish-pypi.yml"
)
CERTIFIED_COMMIT = "43fd7008f8573f2b2a9906ee8c257986777f04e9"
CERTIFIED_MANIFEST = "5931aa6a6a66c923831cae1dfeba96571eb10fb812c1cd8816fd0d707aa1094d"


def _validate_publication_controls(source: str) -> None:
    document: dict[object, Any] = yaml.safe_load(source)
    events = document.get("on", document.get(True))
    assert isinstance(events, dict)
    assert set(events) == {"workflow_dispatch"}
    assert not events["workflow_dispatch"]
    assert document["permissions"] == {}
    jobs = document["jobs"]
    assert set(jobs) == {"verificar-bundle", "publicar"}

    verify = jobs["verificar-bundle"]
    publish = jobs["publicar"]
    assert verify["permissions"] == {"contents": "read", "actions": "read"}
    assert publish["needs"] == "verificar-bundle"
    assert publish["environment"]["name"] == "pypi"
    assert publish["permissions"] == {"id-token": "write", "actions": "read"}

    verify_steps = "\n".join(str(step) for step in verify["steps"])
    publish_steps = "\n".join(str(step) for step in publish["steps"])
    assert CERTIFIED_COMMIT in verify_steps
    assert "35017413644" in verify_steps
    assert "10416406388" in verify_steps
    assert CERTIFIED_MANIFEST in verify_steps
    assert CERTIFIED_MANIFEST in publish_steps
    assert "sha256sum --check SHA256SUMS" in verify_steps
    assert "sha256sum --check SHA256SUMS" in publish_steps
    assert "--trusted-publishing always" in publish_steps
    assert "dist/*.whl dist/*.tar.gz" in publish_steps
    assert "https://pypi.org/pypi/${project}/1.0.1/json" in publish_steps
    assert "actions/checkout@" not in publish_steps
    assert "uv build" not in publish_steps
    assert "--no-attestations" not in publish_steps


def test_publication_workflow_has_manual_immutable_oidc_gate() -> None:
    _validate_publication_controls(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ("workflow_dispatch:", "push:"),
        (CERTIFIED_COMMIT, "0" * 40),
        (CERTIFIED_MANIFEST, "0" * 64),
        ("id-token: write", "contents: write"),
        ("name: pypi", "name: unprotected"),
    ],
)
def test_publication_controls_reject_unsafe_changes(
    original: str, replacement: str
) -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert original in source

    with pytest.raises(AssertionError):
        _validate_publication_controls(source.replace(original, replacement))
