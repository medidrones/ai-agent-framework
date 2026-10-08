# Revisão de segurança da DS-003

| Controle | Estado | Evidência |
| --- | --- | --- |
| SQL parametrizado | PASS | token, payload, versão e identidades usam parâmetros Psycopg |
| token protegido | PASS | lookup utiliza somente digest SHA-256/HMAC da DS-002 |
| erro sem payload | PASS | conflito contém apenas ID e revisões |
| erro sem DSN/credencial | PASS | mensagens públicas são estáveis e genéricas |
| identidade imutável | PASS | CAS exige `execution_id`, `agent_id` e `tenant_id` atuais |
| versão não contornável | PASS | incremento ocorre no SQL e revisão esperada é obrigatória |
| checkpoint expirado | PASS | predicado impede atualização e reativação |
| checkpoint consumido | PASS | linha removida não pode receber CAS |
| estado global | PASS | não há locks ou registry de concorrência em Python |
| isolamento | PASS | tokens distintos são atualizados independentemente |

## Dados persistidos

O payload pode conter informação sensível e continua sujeito aos controles de
acesso, criptografia e backup da plataforma. A DS-003 não registra nem inclui o
payload em erros. `checkpoint_id` corresponde ao `execution_id` já persistido e
não ao bearer token.

## Limitações

- Quem possui acesso SQL direto e permissão de escrita pode contornar a API;
  privilégios do banco devem seguir menor privilégio.
- CAS não fornece exactly-once para efeitos externos.
- O contrato 1.x não distingue consumido de desconhecido na resposta pública.
