# Governança do keyspace Redis

A chave real é:

```text
atlas:{sha256(namespace)}:checkpoint:{sha256-ou-hmac(token)}
```

- namespace é obrigatório, normalizado com NFKC e limitado a 128 caracteres;
- controles, vazio e whitespace periférico são rejeitados;
- token e namespace não aparecem em texto claro;
- chave HMAC opcional exige ao menos 32 bytes;
- nenhuma operação usa `KEYS`, scan ou descoberta irrestrita;
- chaves relacionadas usam uma hash tag estável, embora Cluster não tenha sido
  certificado nesta tarefa.

O host deve escolher namespaces distintos por ambiente e tenant. A identidade
interna de execução, agente e tenant é validada após desserialização e no CAS.
