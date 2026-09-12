# Criando um plugin

Plugins são distribuições Python normais que dependem de `atlas-agent-core`.
Configuração e credenciais pertencem ao host e chegam somente no
`PluginContext`; a factory não deve ler variáveis de ambiente nem iniciar
clientes.

## Entry point oficial

Declare a factory síncrona sem argumentos:

```toml
[project.entry-points."atlas_agents.plugins"]
acme = "acme_atlas.plugin:create_plugin"
```

```python
from atlas_agents import Plugin

from acme_atlas.plugin import AcmePlugin


def create_plugin() -> Plugin:
    return AcmePlugin()
```

O nome `acme` é apenas um alias de descoberta. A identidade canônica é
`PluginManifest.metadata.plugin_id`.

## Implementação mínima

```python
from atlas_agents import (
    Plugin,
    PluginCapability,
    PluginContext,
    PluginContributionDescriptor,
    PluginContributionValue,
    PluginManifest,
    PluginMetadata,
    Tool,
    ToolContribution,
    ToolDefinition,
    ToolExecutionContext,
    ToolOutput,
)


class WeatherTool(Tool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="weather",
            description="Consulta as condições meteorológicas.",
            parameters={"type": "object", "additionalProperties": False},
        )

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        del arguments, context
        return ToolOutput(content={"condition": "sunny"})


class AcmePlugin(Plugin):
    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            metadata=PluginMetadata(
                plugin_id="acme.tools",
                name="Ferramentas Acme",
                version="1.0.0",
            ),
            capabilities=(PluginCapability.TOOL,),
            required_atlas_version=">=0.1,<1",
            optional_dependencies=("acme-sdk>=2",),
        )

    def describe(
        self, context: PluginContext
    ) -> tuple[PluginContributionDescriptor, ...]:
        enabled = context.configuration.get("weather_enabled", True)
        if enabled is not True:
            return ()
        return (
            PluginContributionDescriptor(
                capability=PluginCapability.TOOL,
                identifier="weather",
            ),
        )

    async def activate(
        self, context: PluginContext
    ) -> tuple[PluginContributionValue, ...]:
        del context
        return (ToolContribution(tool=WeatherTool()),)

    async def deactivate(self, context: PluginContext) -> None:
        del context


def create_plugin() -> Plugin:
    return AcmePlugin()
```

`describe()` deve ser determinístico, síncrono e livre de I/O. O conjunto
retornado por `activate()` precisa coincidir exatamente com os descritores.

## Ativação pelo host

```python
discovered = manager.discover()
plugin = manager.load(discovered[0])
manager.register_plugin(plugin)

result = await manager.activate(
    "acme.tools",
    configuration={"weather_enabled": True, "api_key": secret},
)
```

Instalar o pacote é uma decisão externa (`uv add` ou equivalente). O Atlas não
instala dependências durante discovery, load ou activation. Registro manual
continua disponível para aplicações e testes sem entry points.
