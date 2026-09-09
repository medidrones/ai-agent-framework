# Memory e Knowledge são fronteiras distintas

O Atlas separa memória de conhecimento para evitar que experiência do agente,
busca documental e infraestrutura vetorial formem um único subsistema
acoplado.

```text
                 AgentRuntime
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
       Memory                  Knowledge
          │                       │
 experiência/histórico       fontes externas
          │                       │
 usuário/sessão/agente       documentos/corpora
          │                       │
     MemoryStore            KnowledgeRetriever
```

Memory contém informação associada a uma experiência anterior e exige um
`MemoryScope` exato. Knowledge representa fontes externas, documentos, trechos
e citações por uma allowlist explícita. Os dois contextos podem coexistir, mas
mantêm contratos, validações e mensagens diferentes.

Contratos necessários ao runtime, como `MemoryStore`, `KnowledgeRetriever` e os
managers e policies, pertencem ao `atlas-agent-core`. Implementações concretas
futuras pertencerão a pacotes opcionais, por exemplo `atlas-agent-memory` e
`atlas-agent-knowledge`, e dependerão dos contratos do core. O core nunca
dependerá desses adapters.

Esta fronteira proíbe na camada de memória:

- embeddings e modelos de embedding;
- vector stores, métricas de distância e índices vetoriais;
- ingestão, chunking e reranking de documentos;
- recuperação de corpus ou busca de conhecimento;
- SDK obrigatório de banco, Redis ou mecanismo de busca.

Consulte as referências de [memória](../reference/memory.md),
[conhecimento](../reference/knowledge.md) e
[RAG no runtime](../reference/rag-runtime.md).
