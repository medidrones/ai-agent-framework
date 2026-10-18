from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[4] / ".github" / "workflows" / "publish-pypi.yml"
)
CERTIFIED_VERSION = "1.1.0"
CERTIFIED_COMMIT = "116e886e95c8785920ca1f18e6d88b01a3c1e3ed"
CERTIFIED_RUN = "39056283924"
CERTIFIED_ARTIFACT = "12109697194"
CERTIFIED_MANIFEST = "688dbcb587d654defeb893b03dbd48ac7aaec835e577e9d3473dbc770778b1eb"
EXPECTED_BATCHES = {
    "fundacao": [
        ("atlas-agent-core", "atlas_agent_core", "pypi"),
        ("atlas-agent-adapters", "atlas_agent_adapters", "pypi-adapters"),
        ("atlas-agent-config", "atlas_agent_config", "pypi-config"),
    ],
    "integracoes": [
        ("atlas-agent-evaluation", "atlas_agent_evaluation", "pypi-evaluation"),
        ("atlas-agent-framework", "atlas_agent_framework", "pypi-framework"),
        ("atlas-agent-mcp", "atlas_agent_mcp", "pypi-mcp"),
    ],
    "final": [("atlas-agent-providers", "atlas_agent_providers", "pypi-providers")],
}


def _validate_publication_controls(source: str) -> None:
    document: dict[object, Any] = yaml.safe_load(source)
    events = document.get("on", document.get(True))
    assert isinstance(events, dict)
    assert set(events) == {"workflow_dispatch"}
    dispatch = events["workflow_dispatch"]
    assert set(dispatch["inputs"]) == {"lote"}
    assert dispatch["inputs"]["lote"] == {
        "description": "Lote autorizado para publicação",
        "required": True,
        "type": "choice",
        "options": list(EXPECTED_BATCHES),
    }
    assert document["permissions"] == {}
    jobs = document["jobs"]
    assert set(jobs) == {"verificar-bundle", "publicar"}

    verify = jobs["verificar-bundle"]
    publish = jobs["publicar"]
    assert verify["permissions"] == {"contents": "read", "actions": "read"}
    assert verify["outputs"]["matrix"] == "${{ steps.selecionar-lote.outputs.matrix }}"
    assert publish["needs"] == "verificar-bundle"
    assert publish["environment"]["name"] == "${{ matrix.environment }}"
    assert publish["permissions"] == {"id-token": "write", "actions": "read"}
    strategy = publish["strategy"]
    assert strategy["fail-fast"] is True
    assert strategy["max-parallel"] == 1
    assert (
        strategy["matrix"] == "${{ fromJSON(needs.verificar-bundle.outputs.matrix) }}"
    )

    selector = next(
        step for step in verify["steps"] if step.get("id") == "selecionar-lote"
    )
    assert selector["env"]["LOTE"] == "${{ inputs.lote }}"
    assert "*) exit 1 ;;" in selector["run"]
    assert 'printf \'matrix=%s\\n\' "$matrix" >> "$GITHUB_OUTPUT"' in selector["run"]
    selected_projects = []
    for batch, entries in EXPECTED_BATCHES.items():
        matrix = json.loads(selector["env"][f"MATRIZ_{batch.upper()}"])
        assert set(matrix) == {"include"}
        actual = [
            (entry["project"], entry["distribution"], entry["environment"])
            for entry in matrix["include"]
        ]
        assert actual == entries
        selected_projects.extend(actual)
    assert len(selected_projects) == 7
    assert len({entry[2] for entry in selected_projects}) == 7

    predecessor_gate = next(
        step
        for step in verify["steps"]
        if step["name"] == "Exigir publicação e hashes dos lotes anteriores"
    )
    assert predecessor_gate["env"]["LOTE"] == "${{ inputs.lote }}"
    gate_script = predecessor_gate["run"]
    gate_cases = {
        batch: re.search(rf"{batch}\)\s+predecessors=\((.*?)\)\s*;;", gate_script, re.S)
        for batch in ("integracoes", "final")
    }
    assert all(match is not None for match in gate_cases.values())
    for batch, match in gate_cases.items():
        assert match is not None
        predecessor_entries = re.findall(
            r"atlas-agent-[\w-]+:atlas_agent_\w+", match.group(1)
        )
        expected = [
            f"{project}:{distribution}"
            for previous in (
                ("fundacao",) if batch == "integracoes" else ("fundacao", "integracoes")
            )
            for project, distribution, _ in EXPECTED_BATCHES[previous]
        ]
        assert predecessor_entries == expected
    assert "fundacao) predecessors=() ;;" in gate_script
    assert f"${{project}}/{CERTIFIED_VERSION}/json" in gate_script
    assert "'.urls[] | select(.filename == $filename) | .digests.sha256'" in gate_script
    assert verify["steps"].index(predecessor_gate) < verify["steps"].index(selector)

    verify_steps = "\n".join(str(step) for step in verify["steps"])
    publish_steps = "\n".join(str(step) for step in publish["steps"])
    assert CERTIFIED_COMMIT in verify_steps
    assert CERTIFIED_RUN in verify_steps
    assert CERTIFIED_ARTIFACT in verify_steps
    assert CERTIFIED_MANIFEST in verify_steps
    assert "releases/" not in verify_steps
    assert CERTIFIED_MANIFEST in publish_steps
    assert "sha256sum --check SHA256SUMS" in verify_steps
    assert "sha256sum --check SHA256SUMS" in publish_steps
    assert "--trusted-publishing always" in publish_steps
    assert (
        f'"dist/${{DISTRIBUTION}}-{CERTIFIED_VERSION}-py3-none-any.whl"'
        in publish_steps
    )
    assert f'"dist/${{DISTRIBUTION}}-{CERTIFIED_VERSION}.tar.gz"' in publish_steps
    assert (
        f"https://pypi.org/pypi/${{PROJECT}}/{CERTIFIED_VERSION}/json" in publish_steps
    )
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
        ('"environment":"pypi-adapters"', '"environment":"pypi"'),
        ('"distribution":"atlas_agent_adapters"', '"distribution":"atlas_agent_core"'),
        ("atlas-agent-core:atlas_agent_core", "atlas-agent-core:atlas_agent_mcp"),
        ("- integracoes", "- final"),
        (
            "fundacao) predecessors=() ;;",
            "fundacao) predecessors=(atlas-agent-core) ;;",
        ),
    ],
)
def test_publication_controls_reject_unsafe_changes(
    original: str, replacement: str
) -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert original in source

    with pytest.raises(AssertionError):
        _validate_publication_controls(source.replace(original, replacement))
