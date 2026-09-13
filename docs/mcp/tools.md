# Tools MCP

`MCPToolImporter` realiza discovery sem alterar o `ToolRegistry`. A importação
exige `include_names` ou `import_all=True`, executa preflight de todos os aliases
e reverte registros parciais em ordem inversa.

O alias padrão é `{servidor}__{tool}`. Assim, `github.search` e
`filesystem.search` tornam-se `github__search` e `filesystem__search`, mas a
chamada remota sempre usa o nome canônico `search`.

`MCPRemoteTool` implementa `Tool`, declara idempotência desconhecida e aprovação
controlada por policy. Annotations remotas são apenas hints não confiáveis;
jamais concedem permissão, dispensam aprovação ou provam que uma operação é
somente leitura.
