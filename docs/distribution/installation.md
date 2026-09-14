# Instalação

Instalação mínima:

```bash
pip install atlas-agent-core
```

Combinações comuns:

```bash
pip install atlas-agent-providers[openai]
pip install atlas-agent-mcp
pip install atlas-agent-adapters[rest]
pip install atlas-agent-adapters[grpc]
pip install atlas-agent-config
pip install atlas-agent-evaluation
```

O meta-package é opcional:

```bash
pip install atlas-agent-framework[openai,config]
pip install atlas-agent-framework[full]
```

O pacote básico `atlas-agent-framework` instala apenas o core. `full` é
conveniência e não é requisito arquitetural. Nenhuma instalação inicia cliente,
servidor, consumer, plugin ou chamada de rede.

Para desenvolvimento do monorepo, use `uv sync --locked`. O `uv.lock` fixa o
ambiente de desenvolvimento, mas não é usado para limitar resoluções dos
consumidores dos wheels.
