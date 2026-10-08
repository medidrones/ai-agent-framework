"""Validate Redis checkpoint recovery across controlled server restarts."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from atlas_agents import ExecutionCheckpoint, ResumeToken
from atlas_agents.adapters.checkpoints.redis import RedisCheckpointStore

ROOT = Path(__file__).parents[1]
FIXTURE = (
    ROOT
    / "packages"
    / "atlas-agent-core"
    / "tests"
    / "fixtures"
    / "checkpoints"
    / "execution-checkpoint-v1.json"
)
TOKEN = ResumeToken(value="ds010-controlled-restart")
NAMESPACE = "ds010:aof-restart-certification"


def checkpoint() -> ExecutionCheckpoint:
    """Load the certified v1 fixture."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["pending_approval"]["expires_at"] = None
    return ExecutionCheckpoint.model_validate(payload)


async def run(*, url: str, mode: str) -> None:
    """Save, read, or consume the deterministic restart fixture."""
    result: dict[str, object]
    async with RedisCheckpointStore.from_url(
        url,
        namespace=NAMESPACE,
        token_hmac_key=b"restart-certification-hmac-key-32",
    ) as store:
        if mode == "save":
            await store.save(resume_token=TOKEN, checkpoint=checkpoint())
            result = {"mode": mode, "status": "saved"}
        elif mode == "read":
            snapshot = await store.read(TOKEN)
            if snapshot.checkpoint != checkpoint() or snapshot.revision != 1:
                raise RuntimeError("O checkpoint recuperado após restart divergiu.")
            result = {"mode": mode, "status": "recovered", "revision": 1}
        else:
            restored = await store.consume(TOKEN)
            if restored != checkpoint():
                raise RuntimeError("O checkpoint consumido após restart divergiu.")
            result = {"mode": mode, "status": "consumed"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    """Parse explicit connection arguments and run the selected phase."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--mode", choices=("save", "read", "consume"), required=True)
    arguments = parser.parse_args()
    asyncio.run(run(url=arguments.url, mode=arguments.mode))


if __name__ == "__main__":
    main()
