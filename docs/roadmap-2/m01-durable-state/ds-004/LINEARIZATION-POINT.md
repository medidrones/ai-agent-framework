# Ponto de linearização

## Definição

O ponto de linearização observável é o **commit da transação que confirma o
`DELETE ... RETURNING` após a autorização**.

O `DELETE` adquire o lock e escolhe um candidato, mas ainda pode ser revertido.
Enquanto a transação não confirma:

- outro consumidor aguarda o lock;
- uma decisão inválida restaura a linha por rollback;
- cancelamento restaura a linha;
- falha de validação do payload restaura a linha.

Depois do commit, consumidores subsequentes recebem `CheckpointNotFoundError`.
Uma perda de conexão exatamente ao redor do commit pode deixar o resultado
incerto para o cliente; por segurança, o adapter não tenta reativar a linha.

## Ordem relevante

```text
BEGIN → DELETE RETURNING → validar → COMMIT → restaurar estado → ferramenta
```

Nenhuma ferramenta é executada dentro da transação de persistência.
