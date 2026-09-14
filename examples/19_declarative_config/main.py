"""Load YAML and compose a runnable Atlas graph through typed factories."""

import asyncio
import sys
from pathlib import Path

from atlas_agents import AgentContext, AgentInput, ExecutionSuspension
from atlas_agents.config import (
    AtlasCompositionBuilder,
    ComponentConfig,
    ConfigurationBuildContext,
    ConfigurationFactoryRegistry,
    ConfigValidationIssue,
    ConfigValue,
    FactoryProduct,
    load_yaml,
)

sys.path.insert(0, str(Path(__file__).parents[1]))

from _support import ScriptedModelProvider, text_response


class LocalModelProvider(ScriptedModelProvider):
    """Identify the scripted provider with its declarative component ID."""

    @property
    def provider_name(self) -> str:
        """Match the `local` ID declared in YAML."""
        return "local"


class DeterministicProviderFactory:
    """Build the local provider selected by the declarative type name."""

    type_name = "deterministic"

    def validate_config(
        self,
        config: dict[str, ConfigValue],
    ) -> tuple[ConfigValidationIssue, ...]:
        """Accept the empty configuration used by this example."""
        del config
        return ()

    async def create(
        self,
        component_id: str,
        config: ComponentConfig,
        context: ConfigurationBuildContext,
    ) -> FactoryProduct[LocalModelProvider]:
        """Create one provider without transferring resource ownership."""
        del component_id, config, context
        return FactoryProduct(
            component=LocalModelProvider((text_response("Composição concluída."),))
        )


async def _run() -> None:
    config_path = Path(__file__).with_name("atlas.yaml")
    config = load_yaml(config_path.read_text(encoding="utf-8"))
    factories = ConfigurationFactoryRegistry()
    factories.register_provider_factory(DeterministicProviderFactory())
    async with await AtlasCompositionBuilder(factories=factories).build(
        config
    ) as composition:
        definition = composition.agent_registry.get("assistant")
        result = await composition.runtime.run(
            agent=definition,
            input_data=AgentInput(message="Valide a composição."),
            context=AgentContext(execution_id="config-example"),
            model_selection=composition.model_selections[definition.agent_id],
        )
        if isinstance(result, ExecutionSuspension):
            raise RuntimeError("A composição não deveria suspender.")
        print(f"Agente: {definition.name}")  # noqa: T201
        print(f"Saída: {result.output}")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(_run())
