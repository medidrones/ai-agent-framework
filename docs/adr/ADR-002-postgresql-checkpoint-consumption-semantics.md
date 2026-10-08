# ADR-002 — Semântica de consumo do checkpoint PostgreSQL

## Contexto

A DS-001 certificou `CheckpointStore.save()` e `CheckpointStore.consume()` e
identificou em `DS001-GAP-001` uma janela crítica: o runtime consome o token
antes de executar a ferramenta externa. Consumo atômico impede dois resumes
vencedores, mas não torna o efeito externo exatamente uma vez.

A governança autorizou o avanço para a DS-002 preservando os contratos públicos
do Atlas 1.x, sem redesenhar o `AgentRuntime` e sem declarar exactly-once.

## Decisão

O `PostgreSQLCheckpointStore` implementa semântica de autorização de retomada
**at-most-once**:

- `save` é create-only e nunca substitui um token existente;
- o token é persistido apenas como HMAC-SHA-256 ou SHA-256;
- `consume` usa um único `DELETE ... RETURNING` transacional;
- apenas uma transação concorrente recebe o payload;
- replay, token desconhecido e checkpoint expirado são indistinguíveis para o
  consumidor;
- cancelamento provoca rollback da transação enquanto a conexão permanece
  disponível;
- erros não expõem DSN, token ou payload.

Esta decisão resolve a condição de entrada da DS-002 ao delimitar formalmente a
garantia implementável sem mudança no core. Ela não resolve exactly-once do
efeito externo. Ferramentas com efeitos colaterais continuam responsáveis por
idempotência própria ou por um protocolo durável futuro.

## Consequências

- o adapter cumpre o contrato 1.0.1 sem modificar o runtime;
- uma falha de processo após o commit de `consume` pode exigir reconciliação
  operacional;
- não há retry automático quando o resultado do commit fica ambíguo por perda
  de conexão;
- DS-003 poderá adicionar concorrência otimista por APIs opcionais, sem alterar
  a garantia mínima de `CheckpointStore`;
- qualquer futura semântica claim/ack exige ADR próprio e evolução compatível.
