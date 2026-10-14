from __future__ import annotations

from atlas_kubernetes_recovery.performance_summary import summarize


def test_summary_separates_operational_range_from_extreme_saturation() -> None:
    report = {
        "backend": "postgresql",
        "benchmark_run_id": "run-a",
        "baseline": [{"threshold_pass": True}],
        "scalability": [
            {"concurrency": 250, "threshold_pass": True, "latency": {}},
            {
                "concurrency": 500,
                "threshold_pass": False,
                "latency": {
                    "p95_ms": 1200,
                    "p99_ms": 1300,
                    "throughput_ops_s": 300,
                },
            },
        ],
        "contention": [
            {
                "concurrency": 100,
                "threshold_pass": True,
                "successful_operations": 1,
                "expected_conflicts": 99,
            }
        ],
        "failure_semantics": {"pass": True},
        "soak": {"pass": True},
        "security_counters": {"lost_updates": 0},
    }
    result = summarize(report)
    assert result["operational_scale_pass"] is True
    assert result["extreme_scale"] == [
        {
            "threshold_pass": False,
            "p95_ms": 1200,
            "p99_ms": 1300,
            "throughput_ops_s": 300,
        }
    ]
    assert result["contention_pass"] is True
    assert result["security_pass"] is True
