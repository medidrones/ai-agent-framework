"""Async process entry point for Kubernetes lifecycle certification."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from contextlib import suppress
from datetime import UTC, datetime
from http import HTTPStatus
from urllib.parse import parse_qs, urlsplit

from atlas_agents import ApprovalDecisionType
from atlas_kubernetes_recovery.config import HostConfiguration
from atlas_kubernetes_recovery.durable_hitl import (
    ApprovalAuthorizationError,
    ApprovalConflictError,
    ApprovalExpiredError,
    ApprovalNotFoundError,
    ApprovalPersistenceError,
    ApprovalSubmission,
    TrustedApprovalPrincipal,
)
from atlas_kubernetes_recovery.host import (
    ApprovalState,
    CertificationHost,
    CheckpointBackend,
)


class CertificationHttpServer:
    """Expose only technical health and deterministic scenario endpoints."""

    def __init__(self, host: CertificationHost) -> None:
        """Route requests to one pod-scoped certification host."""
        self._host = host

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle one bounded HTTP/1.1 request without a web dependency."""
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=2)
            if len(line) > 4096:
                await self._respond(writer, HTTPStatus.REQUEST_URI_TOO_LONG, {})
                return
            parts = line.decode("ascii", errors="strict").strip().split()
            if len(parts) != 3:
                await self._respond(writer, HTTPStatus.BAD_REQUEST, {})
                return
            method, target, _version = parts
            headers: dict[str, str] = {}
            while True:
                header = await asyncio.wait_for(reader.readline(), timeout=2)
                if header in {b"\r\n", b"\n", b""}:
                    break
                if len(header) > 8192:
                    await self._respond(
                        writer, HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, {}
                    )
                    return
                name, separator, value = header.decode(
                    "ascii", errors="strict"
                ).partition(":")
                if not separator:
                    raise ValueError("O cabeçalho HTTP é inválido.")
                headers[name.strip().lower()] = value.strip()
            content_length = int(headers.get("content-length", "0"))
            if content_length < 0 or content_length > 16_384:
                await self._respond(writer, HTTPStatus.CONTENT_TOO_LARGE, {})
                return
            body: dict[str, object] = {}
            if content_length:
                raw_body = await asyncio.wait_for(
                    reader.readexactly(content_length), timeout=2
                )
                decoded = json.loads(raw_body)
                if not isinstance(decoded, dict):
                    raise ValueError("O corpo JSON deve ser um objeto.")
                body = decoded
            status, payload = await self._route(method, target, body)
            await self._respond(writer, status, payload)
        except ApprovalAuthorizationError as error:
            await self._respond(
                writer,
                HTTPStatus.FORBIDDEN,
                {"error": type(error).__name__},
            )
        except ApprovalExpiredError as error:
            await self._respond(
                writer,
                HTTPStatus.GONE,
                {"error": type(error).__name__},
            )
        except ApprovalConflictError as error:
            await self._respond(
                writer,
                HTTPStatus.CONFLICT,
                {"error": type(error).__name__},
            )
        except ApprovalNotFoundError as error:
            await self._respond(
                writer,
                HTTPStatus.NOT_FOUND,
                {"error": type(error).__name__},
            )
        except ApprovalPersistenceError as error:
            await self._respond(
                writer,
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": type(error).__name__},
            )
        except (UnicodeDecodeError, ValueError, KeyError, LookupError) as error:
            await self._respond(
                writer,
                HTTPStatus.BAD_REQUEST,
                {"error": type(error).__name__},
            )
        except Exception as error:
            await self._respond(
                writer,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": type(error).__name__},
            )
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()

    async def _route(
        self,
        method: str,
        target: str,
        body: dict[str, object] | None = None,
    ) -> tuple[HTTPStatus, dict[str, object]]:
        body = body or {}
        parsed = urlsplit(target)
        query = parse_qs(parsed.query, strict_parsing=True)
        if method == "GET" and parsed.path == "/live":
            return HTTPStatus.OK, {"status": "live"}
        if method == "GET" and parsed.path == "/ready":
            ready = await self._host.dependencies_ready()
            return (
                HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
                {"status": "ready" if ready else "not_ready"},
            )
        if method == "GET" and parsed.path == "/status":
            return HTTPStatus.OK, await self._host.status()
        if method == "POST" and parsed.path == "/seed":
            result = await self._host.seed(
                backend=CheckpointBackend(self._one(query, "backend")),
                execution_id=self._execution_id(self._one(query, "execution_id")),
                state=ApprovalState(self._one(query, "decision", "pending")),
                tenant_id=self._tenant_id(
                    self._one(query, "tenant_id", "tenant-ds013")
                ),
            )
            return HTTPStatus.CREATED, result
        if method == "POST" and parsed.path == "/decide":
            result = await self._host.decide(
                execution_id=self._execution_id(self._one(query, "execution_id")),
                state=ApprovalState(self._one(query, "decision")),
            )
            return HTTPStatus.OK, result
        if method == "POST" and parsed.path == "/durable-hitl/seed":
            result = await self._host.seed_durable_hitl(
                backend=CheckpointBackend(self._one(query, "backend")),
                execution_id=self._execution_id(self._one(query, "execution_id")),
                tenant_id=self._tenant_id(
                    self._one(query, "tenant_id", "tenant-ds014")
                ),
            )
            return HTTPStatus.CREATED, result
        if method == "POST" and parsed.path == "/durable-hitl/decide":
            command = ApprovalSubmission(
                decision_id=self._body_text(body, "decision_id"),
                approval_request_id=self._body_text(body, "approval_request_id"),
                execution_id=self._execution_id(self._body_text(body, "execution_id")),
                tenant_id=self._tenant_id(self._body_text(body, "tenant_id")),
                tool_call_id=self._body_text(body, "tool_call_id"),
                tool_name=self._body_text(body, "tool_name"),
                decision=ApprovalDecisionType(self._body_text(body, "decision")),
                principal=TrustedApprovalPrincipal(
                    subject=self._body_text(body, "subject"),
                    tenant_id=self._tenant_id(
                        self._body_text(body, "principal_tenant_id")
                    ),
                    permissions=frozenset(self._body_text_list(body, "permissions")),
                    tool_names=frozenset(self._body_text_list(body, "tool_names")),
                ),
                decided_at=datetime.now(UTC),
                reason=self._body_optional_text(body, "reason"),
            )
            return HTTPStatus.OK, await self._host.decide_durable_hitl(
                resume_token=self._body_text(body, "resume_token"),
                submission=command,
            )
        if method == "GET" and parsed.path == "/durable-hitl/audit":
            return HTTPStatus.OK, await self._host.durable_hitl_audit(
                self._one(query, "approval_request_id")
            )
        if method == "POST" and parsed.path == "/runtime-control":
            mode = self._one(query, "mode")
            if mode not in {"deadline", "cancellation"}:
                raise ValueError("O modo de controle do runtime é inválido.")
            return HTTPStatus.OK, await self._host.runtime_control(
                cancellation=mode == "cancellation"
            )
        if method == "POST" and parsed.path == "/arm-crash-after-effect":
            execution_id = self._execution_id(self._one(query, "execution_id"))
            return HTTPStatus.OK, await self._host.arm_crash_after_effect(execution_id)
        if method == "POST" and parsed.path == "/arm-delay-after-effect":
            execution_id = self._execution_id(self._one(query, "execution_id"))
            seconds = float(self._one(query, "seconds"))
            return HTTPStatus.OK, await self._host.arm_delay_after_effect(
                execution_id,
                seconds,
            )
        return HTTPStatus.NOT_FOUND, {"error": "not_found"}

    @staticmethod
    def _one(query: dict[str, list[str]], name: str, default: str | None = None) -> str:
        values = query.get(name)
        if values is None:
            if default is None:
                raise KeyError(name)
            return default
        if len(values) != 1:
            raise ValueError(f"O parâmetro {name} deve ocorrer uma vez.")
        return values[0]

    @staticmethod
    def _execution_id(value: str) -> str:
        if (
            not value
            or len(value) > 128
            or any(
                not (
                    character.isascii() and (character.isalnum() or character in "-_.")
                )
                for character in value
            )
        ):
            raise ValueError("O execution_id é inválido.")
        return value

    @staticmethod
    def _tenant_id(value: str) -> str:
        if (
            not value
            or len(value) > 64
            or any(
                not (
                    character.isascii() and (character.isalnum() or character in "-_.")
                )
                for character in value
            )
        ):
            raise ValueError("O tenant_id é inválido.")
        return value

    @staticmethod
    def _body_text(body: dict[str, object], name: str) -> str:
        value = body.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > 4096:
            raise ValueError(f"O campo {name} é inválido.")
        return value

    @staticmethod
    def _body_optional_text(body: dict[str, object], name: str) -> str | None:
        value = body.get(name)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip() or len(value) > 4096:
            raise ValueError(f"O campo {name} é inválido.")
        return value

    @staticmethod
    def _body_text_list(body: dict[str, object], name: str) -> tuple[str, ...]:
        value = body.get(name)
        if not isinstance(value, list) or len(value) > 32:
            raise ValueError(f"O campo {name} é inválido.")
        if any(
            not isinstance(item, str) or not item.strip() or len(item) > 256
            for item in value
        ):
            raise ValueError(f"O campo {name} é inválido.")
        return tuple(value)

    @staticmethod
    async def _respond(
        writer: asyncio.StreamWriter,
        status: HTTPStatus,
        payload: dict[str, object],
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        writer.write(
            (
                f"HTTP/1.1 {status.value} {status.phrase}\r\n"
                "Content-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            + body
        )
        await writer.drain()


async def _recovery_loop(host: CertificationHost) -> None:
    while not host.shutting_down:
        await host.recover_once()
        await asyncio.sleep(host.configuration.recovery_interval_seconds)


async def _run() -> None:
    configuration = HostConfiguration.from_environment()
    host = CertificationHost(configuration)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for watched_signal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(watched_signal, stop.set)

    await host.start()
    http = CertificationHttpServer(host)
    server = await asyncio.start_server(
        http.handle,
        host="0.0.0.0",  # noqa: S104  # nosec B104
        port=configuration.port,
        limit=16384,
    )
    recovery_task = asyncio.create_task(_recovery_loop(host))
    try:
        await stop.wait()
    finally:
        server.close()
        await server.wait_closed()
        recovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await recovery_task
        await host.close()


def main() -> None:
    """Run the certification host until Kubernetes sends a termination signal."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
