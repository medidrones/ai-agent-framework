"""PostgreSQL checkpoint persistence API."""

try:
    import psycopg as _psycopg
    import psycopg_pool as _psycopg_pool
except ModuleNotFoundError as error:
    if error.name not in {"psycopg", "psycopg_pool"}:
        raise
    from atlas_agents.adapters.optional import MissingAdapterDependencyError

    raise MissingAdapterDependencyError(
        "O adapter PostgreSQL exige o extra 'postgresql'. Instale com: "
        "pip install atlas-agent-adapters[postgresql]"
    ) from None

del _psycopg, _psycopg_pool

from atlas_agents.adapters.checkpoints.postgresql.errors import (  # noqa: E402
    PostgreSQLCheckpointStoreError,
    PostgreSQLMigrationError,
)
from atlas_agents.adapters.checkpoints.postgresql.migrations import (  # noqa: E402
    PostgreSQLCheckpointMigrator,
)
from atlas_agents.adapters.checkpoints.postgresql.store import (  # noqa: E402
    PostgreSQLCheckpointStore,
)

__all__ = [
    "PostgreSQLCheckpointMigrator",
    "PostgreSQLCheckpointStore",
    "PostgreSQLCheckpointStoreError",
    "PostgreSQLMigrationError",
]
