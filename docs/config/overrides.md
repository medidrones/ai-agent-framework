# Overrides determinísticos

Loaders aceitam `overrides` como mapping Python. A regra é pequena e estável:

- mapping sobre mapping realiza merge profundo;
- escalares, listas e `null` substituem integralmente o valor anterior;
- o mapping de origem não é alterado;
- o resultado completo é validado depois do merge.

Não existe sintaxe de caminho, concatenação implícita de listas ou resolução de
ambiente. Assim, a precedência é visível para a aplicação que fornece cada
camada.

```python
config = load_yaml(
    texto_base,
    overrides={"atlas": {"default_limits": {"max_turns": 3}}},
)
```

`configuration_fingerprint(config)` usa JSON canônico e SHA-256. Como a árvore
retém `SecretReference`, o fingerprint identifica a configuração sem incluir o
valor resolvido do segredo.
