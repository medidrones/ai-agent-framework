# Resources MCP

O cliente preserva URI opaca, MIME type, texto e blob nos DTOs MCP. O servidor
expõe somente o conteúdo fornecido por um `MCPResourceProvider` injetado,
incluindo resources estáticos e URI templates.

Não existe resolução genérica de `file://`, acesso automático ao filesystem,
chunking ou ingestão. `MCP Resource` não equivale a `KnowledgeRetriever`; uma
aplicação futura deverá compor esse adapter de forma explícita e aplicar suas
próprias políticas de confiança e autorização.
