# Integração MCP

`atlas-agent-mcp` integra o Atlas ao Model Context Protocol sem adicionar o SDK
`mcp` ao core. A baseline é MCP `2026-07-28`, com negociação e compatibilidade
delegadas ao SDK Python oficial `2.2.x`.

```text
AgentRuntime → ToolExecutor → MCPRemoteTool → MCPClient → servidor remoto
cliente externo → AtlasMCPServer → ToolExecutor → Tool Atlas
```

Tools remotas entram no registry somente por importação explícita. Tools locais
são expostas somente por allowlist. Resources não viram Knowledge e prompts não
viram instruções de agente automaticamente.

Consulte a [documentação oficial do SDK](https://github.com/modelcontextprotocol/python-sdk)
e a [revisão 2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28/).
