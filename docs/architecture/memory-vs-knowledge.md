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
     MemoryStore            Retriever/KnowledgeStore
```

Task 013 implementa somente o lado esquerdo. Memory contém informação associada
a uma experiência anterior e exige um `MemoryScope` exato. Knowledge tratará
fontes externas, documentos, trechos e citações em uma evolução independente.

Contratos necessários ao runtime, como `MemoryStore`, `MemoryManager` e as
policies, pertencem ao `atlas-agent-core`. Implementações concretas futuras
pertencerão a pacotes opcionais, por exemplo `atlas-agent-memory`, e dependerão
dos contratos do core. O core nunca dependerá desses adapters.

Esta fronteira proíbe na camada de memória:

- embeddings e modelos de embedding;
- vector stores, métricas de distância e índices vetoriais;
- ingestão, chunking e reranking de documentos;
- recuperação de corpus ou busca de conhecimento;
- SDK obrigatório de banco, Redis ou mecanismo de busca.

Consulte a [referência de memória](../reference/memory.md) para os contratos e
o fluxo do runtime.
