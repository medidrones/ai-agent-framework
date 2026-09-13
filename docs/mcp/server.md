# Servidor MCP

`AtlasMCPServer` recebe `ToolRegistry`, `ToolExecutor` e providers opcionais de
resources e prompts por construtor. Nenhuma tool registrada é exposta por
padrão. `MCPServerConfig.exposed_tool_names=()` significa expor zero tools.

Chamadas externas sempre atravessam `ToolExecutor`, preservando validação de
schema, permissões e normalização de falhas. O context factory padrão cria
contexto anônimo: argumentos e metadata MCP nunca estabelecem identidade.

`create_streamable_http_app()` retorna a aplicação para o host executar; o
Atlas não inicia Uvicorn. `run_stdio()` entrega framing e negociação ao SDK e
não escreve diagnósticos em stdout.
