# Compatibilidade

## Níveis de suporte

- **Suportado:** coberto pela matriz de CI e pela política de compatibilidade.
- **Experimental:** pode mudar sem o ciclo normal, desde que marcado.
- **Depreciado:** ainda funcional durante a janela de remoção.
- **Não suportado:** fora dos ranges publicados ou da matriz de CI.

## Matriz da candidata 1.0.0rc2

| Componente | Range declarado | Ambiente validado |
| --- | --- | --- |
| Python | `>=3.12` | CI: 3.12 e 3.13; validação local: 3.12.6 e 3.13.15 |
| Pydantic | `>=2.13,<3` | 2.13.5 |
| JSON Schema | `>=4.26,<5` | 4.26.0 |
| Packaging | `>=26.0,<27` | 26.3 |
| OpenAI SDK | `>=3.13.0,<4` | 3.13.0 |
| MCP SDK | `>=2.2.0,<3` | 2.2.0 |
| FastAPI | `>=0.141,<1` | 0.141.1 |
| grpcio | `>=1.81.1,<2` | 1.83.1; código gerado requer 1.81.1+ |
| protobuf | `>=6.33.5,<7` | 6.33.6; código gerado requer 6.33.5+ |
| PyYAML | `>=6.0,<7` | resolvido pelo lockfile |

Novas versões de Python entram somente depois de CI verde. O objetivo maduro é
manter as duas minors estáveis mais recentes, sem ampliar a declaração antes da
validação da toolchain.

Plugins devem declarar `required_atlas_version`. Compatibilidade não atravessa
major automaticamente; no ciclo lockstep atual, plugins oficiais restringem o
minor validado. O contrato é API Python, sem promessa adicional de ABI.

Checkpoints da minor anterior devem restaurar ou falhar com erro de
compatibilidade tipado. Wire DTOs versionados têm garantia mais forte do que a
serialização de modelos internos não documentados.
