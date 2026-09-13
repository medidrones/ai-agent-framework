# Schema de configuração

`AtlasConfig` é um modelo Pydantic fechado, imutável por atribuição e
versionado. O artefato para validadores e editores está em
[`atlas-config.schema.json`](atlas-config.schema.json).

As seções raiz são `schema_version`, `atlas`, `providers`, `tools`, `memory`,
`knowledge`, `guardrails`, `observability`, `plugins`, `plugin_activation`,
`mcp`, `adapters` e `agents`. Componentes são mappings cujo ID é a chave. Isso
torna referências estáveis e evita listas com IDs duplicados.

Componentes gerenciados por factory possuem `type`, `enabled` e `config`.
Knowledge também declara `source_ids`; MCP possui `import_tools.include`;
adapters e MCP têm `enabled: false` por padrão. Cada agente pode selecionar
provider/model, ferramentas, memória, fontes de conhecimento e guardrails por
estágio.

Somente uma memória, um knowledge manager e um observability manager podem
estar habilitados na versão 1, pois o runtime possui um ponto explícito para
cada colaboração. Componentes desabilitados não podem ser referenciados.

`required_capabilities` e `preferred_capabilities` usam os valores públicos de
`ModelCapability`, como `text_generation`, `streaming` e `tool_calling`.
