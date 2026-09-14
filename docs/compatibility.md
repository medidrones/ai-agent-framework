# Compatibilidade do Atlas

## Matriz da versão estável 1.0.0

| Dimensão | Suportado | Verificação |
| --- | --- | --- |
| Python | 3.12 e 3.13 | CI em ambas as versões |
| Sistema | Linux e Windows | matriz bloqueante da CI |
| Artefatos | wheel universal e sdist | build e instalação limpa |
| API Python | SemVer e depreciação | inventário de API pública |
| Configuração | schema v1 | versão desconhecida rejeitada |
| Checkpoint | versão explícita | incompatibilidade falha fechado |
| REST/mensageria | wire v1 | DTOs e contratos versionados |
| gRPC | `atlas.agent.v1` | proto versionado |

Outras implementações Python e plataformas podem funcionar, mas não são
certificadas. Dependências opcionais são exercitadas pelos extras; o core não as
importa.

A matriz normativa, os níveis de suporte e a política para Python, plugins,
SDKs e contratos serializados estão em
[`docs/distribution/compatibility.md`](distribution/compatibility.md).
