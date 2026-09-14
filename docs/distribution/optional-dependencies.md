# Dependências opcionais

| Distribuição/extra | Dependências adicionadas |
| --- | --- |
| `atlas-agent-providers[openai]` | `openai>=3.13.0,<4` |
| `atlas-agent-adapters[rest]` | `fastapi>=0.141,<1` |
| `atlas-agent-adapters[grpc]` | `grpcio>=1.81.1,<2`, `protobuf>=6.33.5,<7` |
| `atlas-agent-config[adapters]` | `atlas-agent-adapters~=1.0.0rc1` |
| `atlas-agent[openai]` | provider e extra OpenAI |
| `atlas-agent[mcp]` | integração MCP |
| `atlas-agent[rest]` | adapters e extra REST |
| `atlas-agent[grpc]` | adapters e extra gRPC |
| `atlas-agent[config]` | configuração declarativa |
| `atlas-agent[evaluation]` | avaliação |
| `atlas-agent[full]` | todas as combinações acima |

`atlas_agents.providers` e `atlas_agents.adapters` não importam SDKs opcionais
na raiz. O import do submódulo específico sem seu extra gera um `ImportError`
especializado com o comando de instalação. O pacote não instala dependências
em tempo de execução.

O SDK MCP é obrigatório apenas em `atlas-agent-mcp`, pois toda essa distribuição
representa a funcionalidade MCP. PyYAML é obrigatório apenas em
`atlas-agent-config`, onde YAML é parte central da API pública.
