"""Explicit MCP client transport configuration and factories."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol, Self, cast
from urllib.parse import urlparse

import httpx2
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from atlas_agents.mcp.models import MCPTransportType
from mcp import StdioServerParameters
from mcp.client import Client, Transport
from mcp.client.streamable_http import streamable_http_client


class StdioMCPTransportConfig(BaseModel):
    """Configure a subprocess executable without shell interpretation."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    command: str
    args: tuple[str, ...] = ()
    cwd: Path | None = None
    environment: dict[str, str] = Field(default_factory=dict, repr=False)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: str) -> str:
        """Reject empty values and shell-control syntax."""
        command = value.strip()
        if not command or any(char in command for char in "\x00\r\n&|;<>"):
            raise ValueError("command deve identificar um executável sem shell")
        return command

    @field_validator("args")
    @classmethod
    def validate_args(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject arguments that cannot cross a process boundary safely."""
        if any("\x00" in argument for argument in value):
            raise ValueError("args não pode conter byte nulo")
        return value


class StreamableHTTPMCPTransportConfig(BaseModel):
    """Configure a modern Streamable HTTP endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    url: str
    timeout_seconds: float = Field(default=30.0, gt=0)
    headers: dict[str, str] = Field(default_factory=dict, repr=False)

    @model_validator(mode="after")
    def validate_endpoint(self) -> Self:
        """Require HTTPS remotely and allow plain HTTP only on loopback."""
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url deve usar HTTP ou HTTPS e possuir host")
        if parsed.username or parsed.password:
            raise ValueError("credenciais não podem ser incluídas na URL")
        if parsed.scheme == "http" and parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("HTTP sem TLS é permitido somente para host local")
        return self


class MCPTransport(Protocol):
    """Create one official SDK client for an explicit connection lifecycle."""

    @property
    def transport_type(self) -> MCPTransportType:
        """Return the configured transport category."""
        ...

    def create_client(self) -> Client:
        """Create a disconnected official SDK client."""
        ...


class StdioMCPTransport:
    """Launch an MCP subprocess through SDK stdio without a shell."""

    def __init__(self, config: StdioMCPTransportConfig) -> None:
        """Store an immutable, secret-safe process configuration."""
        self.config = config

    @property
    def transport_type(self) -> MCPTransportType:
        """Return the stdio transport identifier."""
        return MCPTransportType.STDIO

    def create_client(self) -> Client:
        """Create a client whose SDK owns the child process lifecycle."""
        params = StdioServerParameters(
            command=self.config.command,
            args=list(self.config.args),
            env=dict(self.config.environment),
            cwd=self.config.cwd,
        )
        return Client(params)


class StreamableHTTPMCPTransport:
    """Connect through modern Streamable HTTP with isolated headers."""

    def __init__(
        self,
        config: StreamableHTTPMCPTransportConfig,
        *,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        """Store configuration and an optional caller-owned HTTP client."""
        self.config = config
        self._http_client = http_client

    @property
    def transport_type(self) -> MCPTransportType:
        """Return the modern HTTP transport identifier."""
        return MCPTransportType.STREAMABLE_HTTP

    def create_client(self) -> Client:
        """Create a client over an isolated HTTP client lifecycle."""
        return Client(cast("Transport", self._transport()))

    @asynccontextmanager
    async def _transport(self) -> AsyncIterator[object]:
        if self._http_client is not None:
            async with streamable_http_client(
                self.config.url,
                http_client=self._http_client,
            ) as streams:
                yield streams
            return
        async with (
            httpx2.AsyncClient(
                headers=self.config.headers,
                timeout=self.config.timeout_seconds,
            ) as http_client,
            streamable_http_client(
                self.config.url,
                http_client=http_client,
            ) as streams,
        ):
            yield streams
