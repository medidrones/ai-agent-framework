"""Discover, load, activate, inspect, and deactivate a local plugin."""

import asyncio

from atlas_agents import PluginManager, ToolRegistry


async def _run() -> None:
    tools = ToolRegistry()
    manager = PluginManager(tool_registry=tools)
    entry_point = next(
        (item for item in manager.discover() if item.name == "example-tool"),
        None,
    )
    if entry_point is None:
        print("Instale example_plugin conforme o README deste cenário.")  # noqa: T201
        return
    plugin = manager.load(entry_point)
    manager.register_plugin(plugin)
    activated = await manager.activate("example-tool")
    print(f"Ativado: {activated.activated}")  # noqa: T201
    print(f"Contribuição: {tools.get('example_greeting').definition.name}")  # noqa: T201
    await manager.deactivate("example-tool")
    print("Desativado: True")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
