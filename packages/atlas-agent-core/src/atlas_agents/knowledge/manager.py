"""Stateless coordination around an injected knowledge retriever."""

from atlas_agents.knowledge.citations import Citation
from atlas_agents.knowledge.context import KnowledgeContext
from atlas_agents.knowledge.errors import (
    KnowledgeError,
    KnowledgePolicyError,
    KnowledgeProtocolError,
    KnowledgeRetrievalError,
)
from atlas_agents.knowledge.policy import DeterministicRetrievalPolicy, RetrievalPolicy
from atlas_agents.knowledge.query import KnowledgeQuery, KnowledgeRetrievalContext
from atlas_agents.knowledge.retrieval import (
    KnowledgeRetrievalResult,
    KnowledgeRetriever,
)
from atlas_agents.knowledge.source import KnowledgeSource


class KnowledgeManager:
    """Validate retrieval boundaries and assemble deterministic knowledge context."""

    def __init__(
        self,
        *,
        retriever: KnowledgeRetriever,
        retrieval_policy: RetrievalPolicy | None = None,
    ) -> None:
        """Initialize with explicit stateless replaceable dependencies."""
        self._retriever = retriever
        self._retrieval_policy = (
            retrieval_policy
            if retrieval_policy is not None
            else DeterministicRetrievalPolicy()
        )

    async def sources(self) -> tuple[KnowledgeSource, ...]:
        """Return validated source descriptors for configuration introspection."""
        try:
            sources = await self._retriever.sources()
        except KnowledgeError:
            raise
        except Exception as error:
            raise KnowledgeRetrievalError(
                "A consulta às fontes de conhecimento falhou."
            ) from error
        if not isinstance(sources, tuple) or any(
            not isinstance(source, KnowledgeSource) for source in sources
        ):
            raise KnowledgeProtocolError(
                "O retriever deve retornar uma tupla de fontes de conhecimento."
            )
        source_ids = tuple(source.source_id for source in sources)
        if len(set(source_ids)) != len(source_ids):
            raise KnowledgeProtocolError(
                "O retriever retornou identificadores de fonte duplicados."
            )
        return sources

    async def retrieve(
        self,
        *,
        query: KnowledgeQuery,
        context: KnowledgeRetrievalContext,
        max_results: int,
        max_characters: int,
    ) -> KnowledgeContext:
        """Retrieve, validate, select, and map citations without retaining state."""
        try:
            results = await self._retriever.retrieve(query, context)
        except KnowledgeError:
            raise
        except Exception as error:
            raise KnowledgeRetrievalError(
                "A recuperação de conhecimento externo falhou."
            ) from error
        self._validate_results(results, query)
        selected = self._select(
            results=results,
            max_results=max_results,
            max_characters=max_characters,
        )
        citations = tuple(
            Citation(
                citation_key=f"K{index}",
                source_id=result.passage.document.source_id,
                document_id=result.passage.document.document_id,
                passage_id=result.passage.passage_id,
                title=result.passage.document.title,
                uri=result.passage.document.uri,
                location=result.passage.location,
            )
            for index, result in enumerate(selected, start=1)
        )
        return KnowledgeContext(
            results=selected,
            citations=citations,
            total_characters=sum(len(result.passage.content) for result in selected),
        )

    @staticmethod
    def _validate_results(
        results: object,
        query: KnowledgeQuery,
    ) -> None:
        if not isinstance(results, tuple):
            raise KnowledgeProtocolError(
                "O retriever deve retornar uma tupla de resultados."
            )
        if len(results) > query.limit:
            raise KnowledgeProtocolError(
                "O retriever excedeu o limite explícito da consulta."
            )
        seen: set[tuple[str, str, str]] = set()
        allowed = set(query.source_ids)
        for result in results:
            if not isinstance(result, KnowledgeRetrievalResult):
                raise KnowledgeProtocolError(
                    "O retriever retornou um resultado incompatível."
                )
            passage = result.passage
            document = passage.document
            if allowed and document.source_id not in allowed:
                raise KnowledgeProtocolError(
                    "O retriever retornou conteúdo de uma fonte não solicitada."
                )
            identity = (
                document.source_id,
                document.document_id,
                passage.passage_id,
            )
            if identity in seen:
                raise KnowledgeProtocolError(
                    "O retriever retornou uma passagem duplicada."
                )
            seen.add(identity)

    def _select(
        self,
        *,
        results: tuple[KnowledgeRetrievalResult, ...],
        max_results: int,
        max_characters: int,
    ) -> tuple[KnowledgeRetrievalResult, ...]:
        try:
            selected = self._retrieval_policy.select(
                results=results,
                max_results=max_results,
                max_characters=max_characters,
            )
        except KnowledgeError:
            raise
        except Exception as error:
            raise KnowledgePolicyError(
                "A política de seleção de conhecimento falhou."
            ) from error
        if not isinstance(selected, tuple) or any(
            not isinstance(result, KnowledgeRetrievalResult) for result in selected
        ):
            raise KnowledgePolicyError(
                "A política deve retornar uma tupla de resultados."
            )
        available = {id(result) for result in results}
        if any(id(result) not in available for result in selected):
            raise KnowledgePolicyError(
                "A política não pode criar resultados de conhecimento."
            )
        if len({id(result) for result in selected}) != len(selected):
            raise KnowledgePolicyError("A política não pode duplicar resultados.")
        if (
            len(selected) > max_results
            or sum(len(result.passage.content) for result in selected) > max_characters
        ):
            raise KnowledgePolicyError(
                "A política excedeu os limites de montagem do contexto."
            )
        return selected
