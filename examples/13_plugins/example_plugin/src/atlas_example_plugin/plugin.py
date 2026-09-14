"""Minimal trusted tool plugin implemented only with public Atlas APIs."""

from atlas_agents import (
    Plugin,
    PluginCapability,
    PluginContext,
    PluginContributionDescriptor,
    PluginManifest,
    PluginMetadata,
    Tool,
    ToolContribution,
    ToolDefinition,
    ToolExecutionContext,
    ToolOutput,
)


class GreetingTool(Tool):
    """Return a deterministic greeting."""

    @property
    def definition(self) -> ToolDefinition:
        """Describe the contribution without side effects."""
        return ToolDefinition(
            name="example_greeting",
            description="Retorna uma saudação local.",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        )

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolOutput:
        """Produce the local greeting."""
        del context
        return ToolOutput(content={"greeting": f"Olá, {arguments['name']}!"})


class ExampleToolPlugin(Plugin):
    """Contribute one tool only after explicit activation."""

    @property
    def manifest(self) -> PluginManifest:
        """Return identity and compatibility metadata."""
        return PluginManifest(
            metadata=PluginMetadata(
                plugin_id="example-tool",
                name="Plugin de ferramenta do exemplo",
                version="0.1.0",
            ),
            capabilities=(PluginCapability.TOOL,),
            required_atlas_version=">=0.1,<0.2",
        )

    def describe(
        self,
        context: PluginContext,
    ) -> tuple[PluginContributionDescriptor, ...]:
        """Describe the tool without constructing external resources."""
        del context
        return (
            PluginContributionDescriptor(
                capability=PluginCapability.TOOL,
                identifier="example_greeting",
            ),
        )

    async def activate(
        self,
        context: PluginContext,
    ) -> tuple[ToolContribution, ...]:
        """Create the tool after explicit host activation."""
        del context
        return (ToolContribution(tool=GreetingTool()),)
