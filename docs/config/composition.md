# Composition root

`AtlasCompositionBuilder` valida referências e factories antes de efeitos
colaterais. A construção segue ordem determinística: registries, plugins,
providers, tools, memória, knowledge, guardrails, observabilidade, agentes,
runtime, serviço de execução, MCP e adapters.

`AtlasComposition` expõe registries, runtime, serviço externo opcional,
seleções de modelo e integrações construídas. Use-a como gerenciador assíncrono:

```python
from atlas_agents.config import AtlasCompositionBuilder, load_config

config = load_config("atlas.yaml")
builder = AtlasCompositionBuilder(factories=factories, atlas_version="1.0.0rc2")

async with await builder.build(config) as atlas:
    agente = atlas.agent_registry.get("assistant")
```

Falha ou cancelamento durante a construção fecha recursos já adquiridos na
ordem inversa. `close()` também fecha na ordem inversa, é idempotente e tenta
todos os recursos mesmo quando algum fechamento falha. Dependências injetadas
pelo chamador permanecem sob ownership do chamador.

Plugins precisam ser fornecidos ao builder e listados exatamente em
`plugin_activation`; estar instalado ou registrado não ativa um plugin.
