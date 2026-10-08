# Ponto de linearização

O ponto de linearização é a execução, pelo Redis, do `HSET` que troca o estado
de `active` para `consumed` dentro do script Lua. Nenhum cliente recebe o direito
de continuar antes do retorno desse script.

Lua é serializado pelo Redis. Todas as validações precedem a primeira mutação do
caminho de sucesso. Erros de schema, versão, lease, owner, revisão, digest ou
expiração retornam antes da confirmação.

Perda da resposta não desfaz esse ponto. O cliente deve reconciliar pelo mesmo
`operation_id` e nunca presumir rollback.
