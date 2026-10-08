"""Seed and verify durable checkpoints across backend server restarts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from psycopg_pool import AsyncConnectionPool
from redis.asyncio import Redis

from atlas_agents import ExecutionCheckpoint, ResumeToken
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLCheckpointStore,
)
from atlas_agents.adapters.checkpoints.redis import RedisCheckpointStore
from atlas_agents.adapters.checkpoints.redis.store import RedisCheckpointClient

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
TOKEN = ResumeToken(value="ds012-server-restart-probe-v2")


def checkpoint() -> ExecutionCheckpoint:
    """Load the versioned public checkpoint fixture."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["pending_approval"]["expires_at"] = (
        datetime.now(UTC) + timedelta(hours=1)
    ).isoformat()
    return ExecutionCheckpoint.model_validate(payload)


async def probe_postgresql(action: str) -> None:
    """Seed or verify one checkpoint in a caller-provided PostgreSQL service."""
    dsn = os.environ["ATLAS_TEST_POSTGRES_DSN"]
    pool = AsyncConnectionPool[Any](dsn, min_size=1, max_size=2, open=False)
    await pool.open(wait=True)
    try:
        await PostgreSQLCheckpointMigrator(pool).migrate()
        store = PostgreSQLCheckpointStore(pool)
        if action == "seed":
            await store.save(resume_token=TOKEN, checkpoint=checkpoint())
        else:
            restored = await store.read(TOKEN)
            assert restored.checkpoint.execution_id == checkpoint().execution_id  # noqa: S101
    finally:
        await pool.close()


async def probe_redis(action: str) -> None:
    """Seed or verify one checkpoint in a caller-provided durable Redis service."""
    url = os.environ["ATLAS_TEST_REDIS_URL"]
    client = Redis.from_url(url, decode_responses=False)
    store = RedisCheckpointStore(
        cast(RedisCheckpointClient, client),
        namespace="ds012:server-restart",
        token_hmac_key=b"ds012-restart-probe-hmac-key-32b",
    )
    try:
        if action == "seed":
            await store.save(resume_token=TOKEN, checkpoint=checkpoint())
        else:
            restored = await store.read(TOKEN)
            assert restored.checkpoint.execution_id == checkpoint().execution_id  # noqa: S101
    finally:
        await client.aclose()


async def main() -> None:
    """Run the selected backend probe without printing credentials or payloads."""
    parser = argparse.ArgumentParser()
    parser.add_argument("backend", choices=("postgresql", "redis"))
    parser.add_argument("action", choices=("seed", "verify"))
    arguments = parser.parse_args()
    if arguments.backend == "postgresql":
        await probe_postgresql(arguments.action)
    else:
        await probe_redis(arguments.action)
    print(f"DS-012 {arguments.backend} {arguments.action}: PASS")  # noqa: T201


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
