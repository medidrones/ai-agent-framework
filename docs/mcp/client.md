# Cliente MCP

`MCPClient` possui lifecycle explícito e suporta `async with`:

```python
async with MCPClient(transport) as client:
    tools = await client.list_tools()
    result = await client.call_tool("calculator", {"value": 2})
```

As operações `list_tools`, `call_tool`, `list_resources`, `read_resource`,
`list_resource_templates`, `list_prompts` e `get_prompt` retornam somente DTOs
Atlas. Antes de `connect()`, elas falham com `MCPClientNotConnectedError`.
`close()` é idempotente e não existe reconnect nem retry automático oculto.
Uma nova chamada explícita a `connect()` inicia outro lifecycle.

`protocol_version` e `server_info` refletem a negociação feita pelo SDK; o
Atlas não executa handshake próprio nem exige sessão HTTP.
