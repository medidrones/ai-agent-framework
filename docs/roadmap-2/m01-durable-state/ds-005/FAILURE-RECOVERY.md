# Falhas e recuperação

- morte do worker: o lease permanece até expirar e então pode ser readquirido;
- falha antes do commit: rollback não publica ownership;
- falha após commit sem resposta: o resultado é ambíguo e o worker deve tratar
  conflito/expiração de forma segura;
- perda de conexão: erro de infraestrutura sanitizado;
- cancelamento: `CancelledError` é propagado e a transação é revertida;
- chamada externa além da expiração: risco residual, pois fencing no banco não
  desfaz efeitos externos.

A DS-005 fornece primitivas, mas não agenda recovery. Descoberta, eleição e
reexecução coordenada pertencem exclusivamente à DS-006.
