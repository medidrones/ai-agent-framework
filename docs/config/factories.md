# Factories tipadas

`ConfigurationFactoryRegistry` é local à composição e não funciona como
service locator global. O host registra factories por `type_name` para
providers, tools, memória, knowledge, guardrails, observabilidade, MCP e
adapters.

Cada factory possui duas operações: `validate_config`, sem efeitos colaterais,
e `create`, assíncrona. `create` recebe apenas o contexto tipado da categoria e
retorna `FactoryProduct`, contendo o componente e recursos que pertencem à
composição. Dependências fornecidas pelo chamador não devem ser incluídas em
`owned_resources`.

O ID de provider deve coincidir com `provider_name`; o ID de ferramenta deve
coincidir com `ToolDefinition.name`. Divergências falham para impedir que a
configuração aparente referenciar um componente diferente do registrado.

Pacotes de integração registram suas próprias factories. O pacote de
configuração não importa SDKs de providers, inicia transportes nem descobre
implementações automaticamente.
