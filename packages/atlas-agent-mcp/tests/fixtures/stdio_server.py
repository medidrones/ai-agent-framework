from __future__ import annotations

import asyncio

from mcp.server import MCPServer

server = MCPServer("atlas-stdio-fixture", version="1.0.0")


@server.tool()
def echo(value: int) -> dict[str, int]:
    print("diagnostic must not contaminate the protocol")  # noqa: T201
    return {"value": value}


if __name__ == "__main__":
    asyncio.run(server.run_stdio_async())
