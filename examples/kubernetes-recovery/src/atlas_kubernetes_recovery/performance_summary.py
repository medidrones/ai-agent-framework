"""Validation and summary helpers for raw DS-015 benchmark evidence."""

from __future__ import annotations

from typing import Any


def summarize(report: dict[str, Any]) -> dict[str, object]:
    """Return auditable pass counts without modifying raw measurements."""
    baseline = report.get("baseline", [])
    scalability = report.get("scalability", [])
    contention = report.get("contention", [])
    operational_scale = [
        item for item in scalability if int(item.get("concurrency", 0)) <= 250
    ]
    extreme_scale = [
        item for item in scalability if int(item.get("concurrency", 0)) == 500
    ]
    return {
        "backend": report.get("backend"),
        "benchmark_run_id": report.get("benchmark_run_id"),
        "baseline_pass": all(item.get("threshold_pass") is True for item in baseline),
        "operational_scale_pass": all(
            item.get("threshold_pass") is True for item in operational_scale
        ),
        "extreme_scale": [
            {
                "threshold_pass": item.get("threshold_pass"),
                "p95_ms": item.get("latency", {}).get("p95_ms"),
                "p99_ms": item.get("latency", {}).get("p99_ms"),
                "throughput_ops_s": item.get("latency", {}).get("throughput_ops_s"),
            }
            for item in extreme_scale
        ],
        "contention_pass": all(
            item.get("threshold_pass") is True
            and item.get("successful_operations") == 1
            and item.get("expected_conflicts") == int(item.get("concurrency", 0)) - 1
            for item in contention
        ),
        "failure_semantics_pass": report.get("failure_semantics", {}).get("pass"),
        "soak_pass": report.get("soak", {}).get("pass"),
        "security_pass": all(
            int(value) == 0 for value in report.get("security_counters", {}).values()
        ),
    }
