# Autorização de aprovação

O `TrustedApprovalPrincipal` somente pode ser criado depois da autenticação pelo
host. Para decidir, ele precisa:

- pertencer ao mesmo tenant;
- possuir `atlas:hitl:decide`;
- possuir a ferramenta no escopo quando `tool_names` não estiver vazio;
- enviar os mesmos IDs de request, execução, chamada e ferramenta;
- apresentar o token opaco correto e não expirado.

Falhas são fechadas e não alteram estado. O host técnico mapeia identidade sem
implementar IdP ou UI. Testes negativos cobrem tenant, permissão, ferramenta e
todos os campos de binding.
