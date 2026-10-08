# Contrato de concorrência

## Invariantes

1. Um checkpoint recém-persistido possui revisão 1.
2. Leitura não altera revisão nem payload.
3. CAS bem-sucedido incrementa a revisão exatamente uma vez.
4. Dois writers com a mesma revisão esperada não confirmam payloads
   incompatíveis: um vence e o outro recebe conflito.
5. Conflito, cancelamento e rollback não modificam payload ou revisão.
6. Checkpoint ausente, expirado ou consumido não pode ser atualizado.
7. `execution_id`, `agent_id` e `tenant_id` são identidade imutável da linha.
8. Atualizações de tokens diferentes não se bloqueiam por mecanismo local.
9. Nenhum conflito provoca retry automático ou nova execução de ferramenta.

## API aditiva

```python
snapshot = await store.read(resume_token)

updated = await store.compare_and_swap(
    resume_token=resume_token,
    checkpoint=new_checkpoint,
    expected_revision=snapshot.revision,
)
```

`PostgreSQLCheckpointSnapshot` é imutável e separa o payload público da revisão
de armazenamento. `CheckpointConcurrencyConflictError` fornece
`checkpoint_id`, `expected_revision`, `actual_revision` e o código estável
`checkpoint_concurrency_conflict`.

## Classificação de zero linhas

Uma atualização que não retorna linha é inspecionada antes de classificar o
resultado:

- linha inexistente: not found, incluindo token consumido;
- linha expirada: not found, preservando a política segura da DS-002;
- identidade divergente: invalid checkpoint;
- linha ativa com revisão diferente: conflito de concorrência.

O contrato 1.x não distingue token desconhecido de token consumido. A DS-003
não inventa essa distinção nem expõe o bearer token.
