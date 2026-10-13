"""Cluster-local DS-014 load and concurrency certification client."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4


class CertificationClient:
    """Call only the technical service without logging bearer credentials."""

    def __init__(self, base_url: str) -> None:
        """Use the cluster-local certification service."""
        parsed = urlsplit(base_url)
        hostname = parsed.hostname or ""
        if (
            parsed.scheme != "http"
            or not hostname.endswith(".svc.cluster.local")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("A URL deve apontar para o serviço cluster-local.")
        self._base_url = base_url.rstrip("/")

    def seed(self, *, backend: str, execution_id: str) -> dict[str, object]:
        """Create one real durable suspension."""
        query = urlencode(
            {
                "backend": backend,
                "execution_id": execution_id,
                "tenant_id": "tenant-ds014",
            }
        )
        return self._request("POST", f"/durable-hitl/seed?{query}")

    def decide(
        self,
        seed: dict[str, object],
        *,
        decision: str,
        decision_id: str,
    ) -> dict[str, object]:
        """Submit one trusted decision without exposing its bearer."""
        payload = {
            "decision_id": decision_id,
            "approval_request_id": seed["approval_request_id"],
            "execution_id": seed["execution_id"],
            "tenant_id": seed["tenant_id"],
            "tool_call_id": seed["tool_call_id"],
            "tool_name": seed["tool_name"],
            "decision": decision,
            "subject": "ds014-human-owner",
            "principal_tenant_id": "tenant-ds014",
            "permissions": ["atlas:hitl:decide"],
            "tool_names": ["record_certification_effect"],
            "resume_token": seed["resume_token"],
            "reason": "Decisão explícita da certificação DS-014.",
        }
        return self._request("POST", "/durable-hitl/decide", payload)

    def audit(self, approval_request_id: object) -> dict[str, object]:
        """Read non-secret durable audit evidence."""
        query = urlencode({"approval_request_id": str(approval_request_id)})
        return self._request("GET", f"/durable-hitl/audit?{query}")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        body = None
        headers: dict[str, str] = {}
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(  # noqa: S310 - fixed cluster-local base URL
            f"{self._base_url}{path}",
            method=method,
            data=body,
            headers=headers,
        )
        with urlopen(request, timeout=30) as response:  # noqa: S310  # nosec B310
            decoded = json.loads(response.read())
        if not isinstance(decoded, dict):
            raise ValueError("A resposta do host deve ser um objeto JSON.")
        return decoded


def _percentile(samples: list[float], quantile: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(len(ordered) * quantile))
    return round(ordered[index], 3)


def _sequential(
    client: CertificationClient,
    *,
    decision: str,
    count: int,
) -> dict[str, object]:
    durations: list[float] = []
    outcomes: Counter[str] = Counter()
    for index in range(count):
        started = time.perf_counter()
        execution_id = f"ds014-{decision}-{index}-{uuid4().hex}"
        seed = client.seed(
            backend="postgresql" if index % 2 == 0 else "redis",
            execution_id=execution_id,
        )
        result = client.decide(
            seed,
            decision=decision,
            decision_id=f"decision-{uuid4().hex}",
        )
        durations.append((time.perf_counter() - started) * 1_000)
        outcomes[str(result.get("resume_outcome", "missing"))] += 1
    return {
        "count": count,
        "outcomes": dict(sorted(outcomes.items())),
        "latency_ms_mean": round(statistics.fmean(durations), 3),
        "latency_ms_p95": _percentile(durations, 0.95),
    }


def main() -> None:
    """Run the mandatory DS-014 operational load without exposing tokens."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--pending", type=int, default=50)
    parser.add_argument("--concurrent", type=int, default=100)
    parser.add_argument(
        "--base-url",
        default="http://atlas-worker.atlas-ds013.svc.cluster.local:8080",
    )
    arguments = parser.parse_args()
    for value in (arguments.count, arguments.pending, arguments.concurrent):
        if value <= 0 or value > 1_000:
            parser.error("As cargas devem estar entre 1 e 1.000.")
    client = CertificationClient(arguments.base_url)
    approvals = _sequential(client, decision="approve", count=arguments.count)
    rejections = _sequential(client, decision="reject", count=arguments.count)
    pending = [
        client.seed(
            backend="postgresql" if index % 2 == 0 else "redis",
            execution_id=f"ds014-pending-{index}-{uuid4().hex}",
        )
        for index in range(arguments.pending)
    ]
    shared = client.seed(
        backend="postgresql",
        execution_id=f"ds014-concurrent-{uuid4().hex}",
    )
    decision_id = f"decision-{uuid4().hex}"
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=min(arguments.concurrent, 64)) as executor:
        concurrent_results = tuple(
            executor.map(
                lambda _: client.decide(
                    shared,
                    decision="approve",
                    decision_id=decision_id,
                ),
                range(arguments.concurrent),
            )
        )
    concurrent_ms = (time.perf_counter() - started) * 1_000
    outcomes = Counter(
        str(result.get("resume_outcome", "missing")) for result in concurrent_results
    )
    audit = client.audit(shared["approval_request_id"])
    events = audit.get("events")
    event_types = (
        [str(event.get("event_type")) for event in events]
        if isinstance(events, list)
        else []
    )
    report = {
        "executed_at": datetime.now(UTC).isoformat(),
        "sequential_approvals": approvals,
        "sequential_rejections": rejections,
        "pending_suspensions": len(pending),
        "concurrent_resume": {
            "attempts": arguments.concurrent,
            "duration_ms": round(concurrent_ms, 3),
            "outcomes": dict(sorted(outcomes.items())),
        },
        "concurrent_audit_events": event_types,
    }
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
