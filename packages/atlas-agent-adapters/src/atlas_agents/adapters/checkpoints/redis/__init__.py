"""Redis checkpoint persistence API."""

try:
    import redis as _redis
except ModuleNotFoundError as error:
    if error.name != "redis":
        raise
    from atlas_agents.adapters.optional import MissingAdapterDependencyError

    raise MissingAdapterDependencyError(
        "O adapter Redis exige o extra 'redis'. Instale com: "
        "pip install atlas-agent-adapters[redis]"
    ) from None

del _redis

from atlas_agents.adapters.checkpoints.redis.errors import (  # noqa: E402
    RedisCheckpointConcurrencyConflictError,
    RedisCheckpointOutcomeUnknownError,
    RedisCheckpointStoreError,
)
from atlas_agents.adapters.checkpoints.redis.keyspace import (  # noqa: E402
    RedisCheckpointKeyspace,
)
from atlas_agents.adapters.checkpoints.redis.models import (  # noqa: E402
    RedisCheckpointSnapshot,
    RedisConsumeReconciliation,
    RedisConsumeReconciliationStatus,
)
from atlas_agents.adapters.checkpoints.redis.store import (  # noqa: E402
    RedisCheckpointStore,
)

__all__ = [
    "RedisCheckpointConcurrencyConflictError",
    "RedisCheckpointKeyspace",
    "RedisCheckpointOutcomeUnknownError",
    "RedisCheckpointSnapshot",
    "RedisCheckpointStore",
    "RedisCheckpointStoreError",
    "RedisConsumeReconciliation",
    "RedisConsumeReconciliationStatus",
]
