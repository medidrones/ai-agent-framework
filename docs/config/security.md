# Segurança da configuração

A configuração é entrada não confiável. O pacote aplica schema fechado,
validação Pydantic, YAML seguro, rejeição de duplicidades e resolução explícita
de referências. O carregamento nunca executa código, importa classes indicadas
por texto, lê ambiente ou rede, nem inicia componentes.

Factories e plugins são código confiável escolhido pelo host. A string `type`
seleciona somente uma factory previamente registrada. Plugins são ativados
somente quando fornecidos pelo host, declarados em `plugins` e ordenados em
`plugin_activation`.

MCP e adapters começam desabilitados. MCP importa zero ferramentas quando a
allowlist está vazia. Adapters habilitados exigem identidade, autorização e
política de limites fornecidas explicitamente pelo host.

Erros públicos omitem detalhes internos das factories e valores de segredos.
Não registre a configuração resolvida, `SecretValue` revelado ou contextos de
factory. Proteções de `repr` reduzem exposição acidental, mas não substituem
controle de logging, memória, acesso ao processo e rotação de credenciais.
