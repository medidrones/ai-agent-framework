# Testes de concorrência

## PostgreSQL real

O arquivo `test_postgresql_atomic_resume.py` cobre:

- dez consumidores em conexões concorrentes: um vencedor e nove rejeições;
- dez `AgentRuntime.resume()` concorrentes: uma ferramenta executada;
- dois processos `spawn`, cada um com pool próprio: um único vencedor;
- cancelamento determinístico enquanto a operação aguarda row lock;
- rollback por falha de autorização e payload inválido;
- restart do pool depois do commit;
- token expirado e desconhecido sem chamada ao validator;
- identidade recusada seguida de retomada legítima;
- decisão rejeitada sem ferramenta;
- indisponibilidade de conexão com erro seguro.

A regressão DS-003 mantém o teste de corrida entre compare-and-swap e consumo,
demonstrando que atualização e remoção serializam na mesma linha.

Mocks são usados somente para testar o fallback do runtime. As propriedades
distribuídas são comprovadas contra PostgreSQL 16 real.
