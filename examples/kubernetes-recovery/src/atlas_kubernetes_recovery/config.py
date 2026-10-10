"""Validated configuration for the Kubernetes certification host."""

from __future__ import annotations

import os
import socket
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class HostConfiguration(BaseModel):
    """Configuration injected by the Kubernetes workload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pod_name: str = Field(min_length=1, max_length=253)
    namespace: str = Field(min_length=1, max_length=63)
    port: int = Field(default=8080, ge=1024, le=65535)
    postgresql_dsn: SecretStr
    redis_url: SecretStr
    token_hmac_key: SecretStr = Field(min_length=32)
    approval_directory: Path = Path("/var/lib/atlas/approvals")
    recovery_interval_seconds: float = Field(default=0.5, gt=0, le=30)
    lease_seconds: int = Field(default=5, ge=1, le=300)

    @field_validator("pod_name", "namespace")
    @classmethod
    def reject_surrounding_whitespace(cls, value: str) -> str:
        """Reject ambiguous Kubernetes identities."""
        if value != value.strip():
            raise ValueError("A identidade Kubernetes não pode conter espaços externos")
        return value

    @classmethod
    def from_environment(cls) -> HostConfiguration:
        """Load infrastructure-owned configuration at the host boundary."""
        return cls(
            pod_name=os.getenv("POD_NAME", socket.gethostname()),
            namespace=os.getenv("POD_NAMESPACE", "atlas-ds013"),
            port=int(os.getenv("ATLAS_HOST_PORT", "8080")),
            postgresql_dsn=SecretStr(os.environ["ATLAS_POSTGRESQL_DSN"]),
            redis_url=SecretStr(os.environ["ATLAS_REDIS_URL"]),
            token_hmac_key=SecretStr(os.environ["ATLAS_TOKEN_HMAC_KEY"]),
            approval_directory=Path(
                os.getenv("ATLAS_APPROVAL_DIRECTORY", "/var/lib/atlas/approvals")
            ),
            recovery_interval_seconds=float(
                os.getenv("ATLAS_RECOVERY_INTERVAL_SECONDS", "0.5")
            ),
            lease_seconds=int(os.getenv("ATLAS_LEASE_SECONDS", "5")),
        )
