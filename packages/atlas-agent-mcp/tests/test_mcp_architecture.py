from __future__ import annotations

import re
from pathlib import Path

import atlas_agents.mcp.models as public_models

ROOT = Path(__file__).parents[3]
MCP_SOURCE = ROOT / "packages" / "atlas-agent-mcp" / "src"
CORE = ROOT / "packages" / "atlas-agent-core"
PROVIDERS = ROOT / "packages" / "atlas-agent-providers"


def source_text(root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))


def test_mcp_sdk_dependency_is_one_way_and_package_local() -> None:
    import_pattern = re.compile(r"(^|\n)\s*(from|import)\s+mcp(?:\.|\s)")
    assert import_pattern.search(source_text(MCP_SOURCE))
    assert not import_pattern.search(source_text(CORE))
    assert not import_pattern.search(source_text(PROVIDERS))
    assert "mcp" not in (CORE / "pyproject.toml").read_text(encoding="utf-8").lower()


def test_mcp_source_has_no_hidden_security_or_legacy_mechanisms() -> None:
    text = source_text(MCP_SOURCE)
    forbidden = (
        "shell=True",
        "os.system",
        "os.getenv",
        "os.environ",
        "dotenv",
        "get_service(",
        "resolve_service(",
        "require_service(",
        "sse_client",
        "sse_server",
        "print(",
    )
    assert all(value not in text for value in forbidden)


def test_public_value_objects_do_not_expose_sdk_types() -> None:
    classes = (
        public_models.MCPServerInfo,
        public_models.MCPToolDescriptor,
        public_models.MCPToolResult,
        public_models.MCPResourceDescriptor,
        public_models.MCPResourceContent,
        public_models.MCPPromptDescriptor,
        public_models.MCPPromptResult,
    )
    for model in classes:
        assert "mcp.types" not in repr(model.model_fields)
