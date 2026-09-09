"""Provider-neutral contracts for external knowledge retrieval and grounding."""

from atlas_agents.knowledge.citations import Citation, extract_citations
from atlas_agents.knowledge.config import AgentKnowledgeConfig
from atlas_agents.knowledge.context import KnowledgeContext, KnowledgeContextRenderer
from atlas_agents.knowledge.document import KnowledgeDocument, KnowledgeLocation
from atlas_agents.knowledge.errors import (
    KnowledgeContextError,
    KnowledgeError,
    KnowledgePolicyError,
    KnowledgeProtocolError,
    KnowledgeRetrievalError,
    KnowledgeSourceNotFoundError,
)
from atlas_agents.knowledge.manager import KnowledgeManager
from atlas_agents.knowledge.passage import KnowledgePassage
from atlas_agents.knowledge.policy import (
    DeterministicRetrievalPolicy,
    RetrievalPolicy,
)
from atlas_agents.knowledge.query import KnowledgeQuery, KnowledgeRetrievalContext
from atlas_agents.knowledge.query_builder import (
    DefaultKnowledgeQueryBuilder,
    KnowledgeQueryBuilder,
)
from atlas_agents.knowledge.retrieval import (
    KnowledgeRetrievalResult,
    KnowledgeRetriever,
)
from atlas_agents.knowledge.source import KnowledgeSource

__all__ = [
    "AgentKnowledgeConfig",
    "Citation",
    "DefaultKnowledgeQueryBuilder",
    "DeterministicRetrievalPolicy",
    "KnowledgeContext",
    "KnowledgeContextError",
    "KnowledgeContextRenderer",
    "KnowledgeDocument",
    "KnowledgeError",
    "KnowledgeLocation",
    "KnowledgeManager",
    "KnowledgePassage",
    "KnowledgePolicyError",
    "KnowledgeProtocolError",
    "KnowledgeQuery",
    "KnowledgeQueryBuilder",
    "KnowledgeRetrievalContext",
    "KnowledgeRetrievalError",
    "KnowledgeRetrievalResult",
    "KnowledgeRetriever",
    "KnowledgeSource",
    "KnowledgeSourceNotFoundError",
    "RetrievalPolicy",
    "extract_citations",
]
