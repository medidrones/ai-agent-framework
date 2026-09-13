from __future__ import annotations

import re
from pathlib import Path

import atlas_agents.adapters as adapters
from atlas_agents.adapters.rest.v1.models import ExecuteRequestV1
from atlas_agents.agents import AgentInput

ROOT = Path(__file__).parents[3]
CORE = ROOT / "packages" / "atlas-agent-core"
ADAPTERS = ROOT / "packages" / "atlas-agent-adapters"
ADAPTER_SOURCE = ADAPTERS / "src"


def source_text(root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))


def test_core_has_no_adapter_or_transport_dependencies() -> None:
    text = source_text(CORE).lower()
    pyproject = (CORE / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert "atlas_agents.adapters" not in text
    assert all(name not in pyproject for name in ("fastapi", "grpcio", "kafka", "pika"))


def test_adapter_source_has_no_automatic_start_or_environment_magic() -> None:
    text = source_text(ADAPTER_SOURCE)
    forbidden = (
        "uvicorn.run(",
        "add_insecure_port(",
        "add_secure_port(",
        "os.getenv",
        "os.environ",
        "dotenv",
        "KafkaConsumer(",
        "pika.BlockingConnection(",
    )
    assert all(value not in text for value in forbidden)
    assert re.search(r"(?m)^app\s*=\s*FastAPI", text) is None


def test_wire_models_are_distinct_from_core_models() -> None:
    assert not issubclass(ExecuteRequestV1, AgentInput)
    assert adapters.AgentExecutionService.__module__.startswith("atlas_agents.adapters")


def test_proto_source_is_checked_in_and_versioned() -> None:
    proto = (
        ADAPTERS
        / "proto"
        / "atlas_agents"
        / "adapters"
        / "grpc"
        / "v1"
        / "agent_execution.proto"
    ).read_text(encoding="utf-8")
    assert "package atlas.agent.v1;" in proto
    assert "rpc Execute" in proto
    assert "rpc Stream" in proto
    assert "rpc Resume" in proto
    assert "rpc ResumeStream" in proto
