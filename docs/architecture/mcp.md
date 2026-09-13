# Arquitetura MCP

```text
                           Atlas Agent Framework

MCP remoto ← MCPClient ← MCPRemoteTool ← ToolExecutor ← AgentRuntime

cliente externo → AtlasMCPServer → ToolExecutor → Tool Atlas
                         ├────────→ MCPResourceProvider
                         └────────→ MCPPromptProvider
```

A dependência é unidirecional:

```text
atlas-agent-mcp → atlas-agent-core
atlas-agent-core ↛ atlas-agent-mcp
```

O SDK oficial implementa JSON-RPC, framing, negociação dual-era, stdio e
Streamable HTTP. O pacote MCP apenas traduz contratos. O runtime continua dono
de allowlist, permissions, guardrails, HITL, limites, deduplicação e timeout.

O plugin system atual não possui contribuição de adapter. Por isso esta versão
oferece composição e factories explícitas, sem ampliar artificialmente
`PluginCapability`; uma contribuição de adapter pode ser criada junto à futura
camada de adapters externos.
