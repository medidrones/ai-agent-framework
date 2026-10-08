# atlas-agent-adapters

Adapters externos opcionais para REST, gRPC, mensageria e persistência
PostgreSQL de checkpoints.

Instale a integração PostgreSQL com:

```bash
pip install atlas-agent-adapters[postgresql]
```

Migrations são administrativas e nunca executadas no import. Depois de
provisionar o schema explicitamente, use o checker somente leitura no readiness:

```python
from atlas_agents.adapters.checkpoints.postgresql import (
    PostgreSQLCheckpointMigrator,
    PostgreSQLSchemaCompatibilityChecker,
)

await PostgreSQLCheckpointMigrator(pool).migrate()
schema = await PostgreSQLSchemaCompatibilityChecker(pool).check()
```

O resultado diferencia schema compatível, drift, versão não suportada e banco
não inicializado, sem carregar payloads nem realizar reparo automático.

Este pacote integra o ecossistema modular Atlas Agent Framework. Consulte a
[documentação oficial](https://github.com/Medicode/ai-agent-framework/tree/main/docs)
para instalação, compatibilidade e APIs públicas.
