# Conhecimento externo

A recuperação registra apenas quantidades e status operacionais. Query,
passagens, URIs, scores, metadata, IDs de usuário e credenciais ficam fora de
spans e métricas.

Consultas são derivadas do `effective_input` após guardrails de entrada. Isso
impede que conteúdo removido seja enviado ao retriever. Guardrails permanecem
separados do `KnowledgeRetriever` e não possuem acesso implícito às fontes.

A camada de Knowledge/RAG do Atlas recupera evidências de fontes externas sem
acoplar o runtime a um mecanismo de busca. Ela pode ser implementada sobre
busca lexical, SQL, APIs, índices híbridos ou vetoriais, mas nenhum desses
backends faz parte do core.

## Contratos

- `KnowledgeDocument`: documento lógico identificado por `document_id` e
  `source_id`, com título, URI e metadados opcionais;
- `KnowledgeLocation`: página, seção ou offsets opcionais dentro do documento;
- `KnowledgePassage`: unidade textual recuperada, sem pressupor estratégia de
  chunking;
- `KnowledgeSource`: descrição de uma fonte lógica, não de um vendor;
- `KnowledgeQuery`: texto, fontes ordenadas, filtros provider-neutral e limite;
- `KnowledgeRetrievalContext`: IDs formais e identidade necessários ao adapter;
- `KnowledgeRetrievalResult`: passagem, score e rank opcionais;
- `Citation`: referência compacta sem o conteúdo integral da passagem.

Scores são específicos do retriever e não são normalizados ou comparados pelo
core. Filtros são pares chave/valor; não aceitam SQL, DSL de fornecedor ou uma
linguagem de expressões definida pelo Atlas.

## Retriever e manager

`KnowledgeRetriever` é a única fronteira assíncrona:

```python
class KnowledgeRetriever(Protocol):
    async def sources(self) -> tuple[KnowledgeSource, ...]: ...

    async def retrieve(
        self,
        query: KnowledgeQuery,
        context: KnowledgeRetrievalContext,
    ) -> tuple[KnowledgeRetrievalResult, ...]: ...
```

Credenciais e clientes são injetados no construtor do adapter. Eles não entram
em `KnowledgeRetrievalContext`, eventos, snapshots ou resultados.

`KnowledgeManager` não mantém corpus nem estado por execução. Ele rejeita:

- fonte fora de `KnowledgeQuery.source_ids`;
- identidade duplicada de fonte, documento e passagem;
- quantidade maior que `KnowledgeQuery.limit`;
- containers ou resultados incompatíveis;
- seleção criada ou duplicada por uma policy.

A `DeterministicRetrievalPolicy` preserva a ordem do retriever, limita a
quantidade e soma somente `len(passage.content)`. Uma passagem que não cabe é
pulada inteira; não há truncamento, reranking ou sumarização.

## Configuração do agente

```python
agent = AgentDefinition(
    agent_id="support",
    name="Suporte",
    instructions="Responda com base nas políticas disponíveis.",
    knowledge=AgentKnowledgeConfig(
        source_ids=("company_policies", "support_center"),
        max_results=8,
        max_characters=12_000,
    ),
)
```

Sem configuração, ou com `source_ids=()`, não existe retrieval. A lista é uma
allowlist: um `KnowledgeQueryBuilder` customizado pode restringi-la, mas nunca
ampliá-la nem convertê-la em acesso global. Autorização específica de cada
fonte permanece responsabilidade do adapter.

## Contexto e segurança do prompt

Cada passagem selecionada recebe uma chave local determinística `K1`, `K2`,
`K3` na ordem final. O renderer produz uma única mensagem `DEVELOPER` com o
framing fixo de que os trechos são dados de referência não confiáveis, não
instruções. URIs, IDs de passagem, scores e metadados não entram no prompt.

O bloco pode conter texto malicioso sem ser promovido a configuração, comando
de ferramenta ou instrução de sistema. O core não tenta detectar prompt
injection; ele preserva a fronteira de confiança.

## Citações

Depois do output final, somente marcadores válidos no formato `[K<número>]`
são associados ao `AgentResult`. Chaves desconhecidas são ignoradas, repetições
são deduplicadas e a ordem da primeira ocorrência é preservada. Texto não é
reescrito. Citações expõem metadados referenciais, nunca o conteúdo integral da
passagem.

O retriever deve fornecer URIs seguras para exposição. O core não acessa URIs,
não cria URLs assinadas e não verifica automaticamente se a afirmação do modelo
é realmente sustentada pela fonte.

## Fora do escopo

Não há ingestão, parsing de PDF, OCR, crawling, geração de chunks, embeddings,
vector database, BM25 concreto, reranking, query rewriting por LLM, cache,
retry, fallback, sincronização de fontes ou verificação de groundedness.
