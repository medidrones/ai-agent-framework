"""Measure deterministic offline runtime overhead for release comparison."""

from __future__ import annotations

import asyncio
import json
import platform
import statistics
import sys
import time
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "examples"))

from _support import (  # noqa: E402
    ScriptedModelProvider,
    agent,
    build_runtime,
    input_and_context,
    text_response,
)

SAMPLES = 250
CONCURRENCY = 25


async def _measure_one(index: int) -> float:
    provider = ScriptedModelProvider((text_response("ok"),))
    runtime = build_runtime(provider)
    input_data, context = input_and_context(
        "benchmark", execution_id=f"benchmark-{index}"
    )
    started = time.perf_counter()
    result = await runtime.run(agent=agent(), input_data=input_data, context=context)
    elapsed = time.perf_counter() - started
    if result.output != "ok":
        raise RuntimeError("Resultado inesperado no benchmark.")
    return elapsed


async def _run() -> dict[str, object]:
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def limited(index: int) -> float:
        async with semaphore:
            return await _measure_one(index)

    wall_started = time.perf_counter()
    timings = await asyncio.gather(*(limited(index) for index in range(SAMPLES)))
    wall_seconds = time.perf_counter() - wall_started
    ordered = sorted(timings)
    return {
        "schema_version": 1,
        "scenario": "single_turn_offline_fake_provider",
        "python": platform.python_version(),
        "platform": platform.system(),
        "samples": SAMPLES,
        "concurrency": CONCURRENCY,
        "wall_seconds": round(wall_seconds, 6),
        "throughput_per_second": round(SAMPLES / wall_seconds, 2),
        "latency_ms": {
            "mean": round(statistics.fmean(timings) * 1000, 3),
            "p50": round(ordered[int(SAMPLES * 0.50)] * 1000, 3),
            "p95": round(ordered[int(SAMPLES * 0.95)] * 1000, 3),
            "max": round(max(timings) * 1000, 3),
        },
    }


def main() -> None:
    """Execute the benchmark and store its factual JSON result."""
    report = asyncio.run(_run())
    destination = REPOSITORY / "reports/release/performance-baseline.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Baseline gravado em {destination.relative_to(REPOSITORY)}")  # noqa: T201


if __name__ == "__main__":
    main()
