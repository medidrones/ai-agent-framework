"""Keep working, conversation, and long-term memory in explicit scopes."""

import asyncio
import sys
from pathlib import Path

from atlas_agents import (
    MemoryManager,
    MemoryQuery,
    MemoryScope,
    MemoryType,
    MemoryWriteRequest,
)

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import InMemoryMemoryStore


async def _run() -> None:
    store = InMemoryMemoryStore()
    manager = MemoryManager(store=store)
    scope = MemoryScope(user_id="example-user", session_id="example-session")
    for memory_type in MemoryType:
        await manager.remember(
            MemoryWriteRequest(
                memory_type=memory_type,
                scope=scope,
                content="My preferred language is Portuguese.",
            )
        )
    results = await manager.retrieve(
        query=MemoryQuery(
            scope=scope,
            memory_type=MemoryType.LONG_TERM,
            text="What is my preferred language?",
        )
    )
    print(f"Tipos armazenados: {', '.join(item.value for item in MemoryType)}")  # noqa: T201
    print(f"Resposta lembrada: {results[0].record.content}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
