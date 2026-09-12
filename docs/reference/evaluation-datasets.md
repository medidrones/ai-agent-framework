# Datasets de avaliação

`EvaluationDataset` é um value object imutável e serializável com `dataset_id`,
`name`, `version`, casos ordenados e metadata JSON-safe. A versão identifica o
conteúdo lógico usado em comparações históricas; não é uma versão automática de
schema.

Cada `EvaluationCase` possui ID opaco e estável, nome, `EvaluationInput`,
expectativas ordenadas e metadata. IDs não são gerados silenciosamente. IDs de
caso são únicos no dataset e IDs de expectativa são únicos dentro do caso.

```python
EvaluationExpectation(
    expectation_id="status-final",
    evaluator_id="status",
    expected="completed",
)
```

O campo `expected` aceita apenas valores JSON-compatible, permitindo extensões
sem transformar o caso em um objeto com dezenas de campos opcionais. Duas
expectativas podem usar o mesmo evaluator, desde que tenham IDs distintos.

Datasets vazios são válidos e produzem summary com `case_count=0`. Carregamento
de arquivos, assinatura, storage e catálogo de golden datasets pertencem a
adapters futuros.
