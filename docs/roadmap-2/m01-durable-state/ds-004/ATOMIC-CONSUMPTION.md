# Consumo atômico

## Algoritmo PostgreSQL

`consume_authorized()` abre uma transação gerenciada pelo pool e executa o SQL
existente `DELETE ... RETURNING`, filtrado pelo digest do token e pela expiração.
O PostgreSQL serializa tentativas sobre a mesma linha. Apenas uma transação pode
receber o payload; as demais observam ausência depois do commit vencedor.

O payload e a autorização são validados antes da saída do contexto da conexão.
Exceções propagadas pelo validator impedem o commit e restauram a linha pelo
rollback da transação.

## Invariantes comprovados

- no máximo um consumo confirmado por checkpoint;
- replay não executa a ferramenta novamente;
- tokens desconhecidos e expirados não alcançam o validator;
- decisão ou identidade inválida preserva o checkpoint;
- decisão `REJECT` válida consome o token e termina sem executar ferramenta;
- cancelamento durante espera por lock propaga `CancelledError` e preserva a
  linha;
- payload inválido no caminho autorizado provoca rollback;
- o digest, e não o bearer token, participa do SQL.

## Escopo

O consumo concede autorização de retomada no máximo uma vez. Não há garantia
de execução exatamente uma vez após o commit.
