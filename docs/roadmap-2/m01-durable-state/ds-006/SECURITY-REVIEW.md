# Revisão de segurança

- descoberta usa consulta parametrizada, limite obrigatório e filtro de tenant;
- payload só é carregado depois da aquisição de ownership;
- `checkpoint_id` público do repository é digest hexadecimal, não bearer token;
- resume token e decisão permanecem na fonte segura do host;
- decisões HITL são revalidadas atomicamente pelo runtime/store;
- owner ID coordena concorrência, mas não substitui identidade/autorização;
- tabela de tentativas não armazena conteúdo, argumentos ou credenciais;
- erros do adapter não incluem DSN;
- checkpoints recuperados continuam sendo dados não confiáveis e passam pelo
  `ExecutionStateRestorer`;
- nenhuma chamada de rede foi adicionada ao core.

Risco residual: fencing do Atlas não torna serviços externos idempotentes. O
host deve usar chaves de idempotência ou reconciliação para efeitos remotos.
