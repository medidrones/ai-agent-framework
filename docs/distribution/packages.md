# Topologia de pacotes

O Atlas usa versionamento lockstep, mas preserva distribuições instaláveis de
forma independente.

| Distribuição | Responsabilidade | Dependências obrigatórias principais |
| --- | --- | --- |
| `atlas-agent-core` | contratos, runtime e abstrações | Pydantic, JSON Schema e Packaging |
| `atlas-agent-providers` | providers oficiais | core; SDKs somente por extra |
| `atlas-agent-mcp` | cliente e servidor MCP | core e SDK MCP |
| `atlas-agent-adapters` | fachada e transportes externos | core; transportes por extra |
| `atlas-agent-config` | configuração declarativa | core, Pydantic e PyYAML |
| `atlas-agent-evaluation` | avaliações provider-neutral | core e Pydantic |
| `atlas-agent-framework` | meta-package opcional | somente core por padrão |

O grafo publicado é acíclico:

```text
atlas-agent-framework ─────┐
providers ────────────────┤
mcp ──────────────────────┤
adapters ─────────────────┼──→ core
config ───────────────────┤
evaluation ───────────────┘
```

Extras do meta-package agregam distribuições, mas não mudam a direção das
dependências. A distribuição difere do import: `atlas-agent-core` fornece
`atlas_agents`; extensões coexistem no mesmo namespace por subpackages
distintos. O meta-package fornece apenas `atlas_agent`.
