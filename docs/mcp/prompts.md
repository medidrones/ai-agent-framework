# Prompts MCP

`MCPPromptProvider` controla os prompts expostos pelo servidor. No cliente,
`get_prompt()` retorna mensagens externas tipadas e não modifica
`AgentDefinition`, `ModelRequest` ou `ExecutionState`.

Conteúdo recebido deve ser tratado como não confiável. A aplicação decide se e
como usá-lo; o adapter nunca o promove automaticamente a mensagem `SYSTEM` nem
altera instruções do agente.
