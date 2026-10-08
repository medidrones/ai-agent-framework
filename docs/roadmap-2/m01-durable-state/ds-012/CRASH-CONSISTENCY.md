# Consistência diante de crash

- Estado em memória não é reconstruído; somente checkpoint confirmado é elegível.
- Escritas PostgreSQL são transacionais e Redis usa script Lua atômico.
- Os novos testes encerram processos com `os._exit(73/74)` após `save` confirmado e
  comprovam leitura por outro processo.
- Consumo mantém tombstone; token consumido não é reativado.
- Tentativa incompleta permanece auditável e a geração seguinte usa novo fencing.
- Persistência de resultado falha fechado: o coordinator não declara recuperação.

Evidências: `test_confirmed_checkpoint_survives_abrupt_process_exit` nos testes de
PostgreSQL e Redis; testes de restart, consumo único, limite de tentativas e lease.
