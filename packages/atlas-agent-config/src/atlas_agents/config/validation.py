"""Pure reference and security validation before component construction."""

from __future__ import annotations

from collections.abc import Mapping

from atlas_agents.config.errors import ConfigError
from atlas_agents.config.loader import load_config
from atlas_agents.config.models import AtlasConfig, ComponentConfig
from atlas_agents.config.result import ConfigValidationIssue, ConfigValidationResult


def _issue(code: str, path: str, message: str) -> ConfigValidationIssue:
    return ConfigValidationIssue(code=code, path=path, message=message)


def _enabled(configs: Mapping[str, ComponentConfig], component_id: str) -> bool:
    config = configs.get(component_id)
    return config is not None and config.enabled


class ConfigurationValidator:
    """Validate all statically knowable references without I/O or side effects."""

    def validate(self, config: AtlasConfig) -> ConfigValidationResult:
        """Return deterministic issues for references and singleton subsystems."""
        issues: list[ConfigValidationIssue] = []
        issues.extend(self._plugins(config))
        issues.extend(self._singletons(config))
        knowledge_sources = {
            source_id
            for item in config.knowledge.values()
            if item.enabled
            for source_id in item.source_ids
        }
        for agent_id, agent in config.agents.items():
            if not agent.enabled:
                continue
            prefix = f"$.agents.{agent_id}"
            if agent.model is not None and agent.model.provider is not None:
                provider_id = agent.model.provider
                if not _enabled(config.providers, provider_id):
                    issues.append(
                        _issue(
                            "invalid_provider_reference",
                            f"{prefix}.model.provider",
                            f"O provider '{provider_id}' não existe ou está "
                            "desabilitado.",
                        )
                    )
            for index, tool_id in enumerate(agent.tools):
                if not _enabled(config.tools, tool_id):
                    issues.append(
                        _issue(
                            "invalid_tool_reference",
                            f"{prefix}.tools[{index}]",
                            f"A ferramenta '{tool_id}' não existe ou está "
                            "desabilitada.",
                        )
                    )
            if agent.guardrails is not None:
                stages = {
                    "input": agent.guardrails.input,
                    "model_output": agent.guardrails.model_output,
                    "tool_call": agent.guardrails.tool_call,
                    "tool_result": agent.guardrails.tool_result,
                    "final_output": agent.guardrails.final_output,
                }
                for stage, guardrail_ids in stages.items():
                    for index, guardrail_id in enumerate(guardrail_ids):
                        if not _enabled(config.guardrails, guardrail_id):
                            issues.append(
                                _issue(
                                    "invalid_guardrail_reference",
                                    f"{prefix}.guardrails.{stage}[{index}]",
                                    f"O guardrail '{guardrail_id}' não existe ou está "
                                    "desabilitado.",
                                )
                            )
            if agent.knowledge is not None:
                for index, source_id in enumerate(agent.knowledge.sources):
                    if source_id not in knowledge_sources:
                        issues.append(
                            _issue(
                                "invalid_knowledge_reference",
                                f"{prefix}.knowledge.sources[{index}]",
                                f"A fonte '{source_id}' não existe ou está "
                                "desabilitada.",
                            )
                        )
        return ConfigValidationResult(issues=tuple(issues))

    @staticmethod
    def _plugins(config: AtlasConfig) -> tuple[ConfigValidationIssue, ...]:
        enabled = {
            plugin_id for plugin_id, item in config.plugins.items() if item.enabled
        }
        activation = config.plugin_activation
        issues: list[ConfigValidationIssue] = []
        if len(set(activation)) != len(activation):
            issues.append(
                _issue(
                    "duplicate_plugin_activation",
                    "$.plugin_activation",
                    "A ordem de ativação não pode repetir plugins.",
                )
            )
        if set(activation) != enabled:
            issues.append(
                _issue(
                    "invalid_plugin_activation",
                    "$.plugin_activation",
                    "A ordem deve listar exatamente todos os plugins habilitados.",
                )
            )
        return tuple(issues)

    @staticmethod
    def _singletons(config: AtlasConfig) -> tuple[ConfigValidationIssue, ...]:
        issues: list[ConfigValidationIssue] = []
        for name, values in (
            ("memory", config.memory),
            ("knowledge", config.knowledge),
            ("observability", config.observability),
        ):
            enabled = [
                component_id for component_id, item in values.items() if item.enabled
            ]
            if len(enabled) > 1:
                issues.append(
                    _issue(
                        "multiple_runtime_subsystems",
                        f"$.{name}",
                        "A versão 1 aceita somente um componente habilitado em "
                        f"'{name}'.",
                    )
                )
        return tuple(issues)


def validate_config_file(path: str) -> ConfigValidationResult:
    """Load and validate a local file while returning safe diagnostics."""
    try:
        config = load_config(path)
    except ConfigError as error:
        return ConfigValidationResult(
            issues=(
                ConfigValidationIssue(
                    code=error.code,
                    path=error.path,
                    message=str(error),
                ),
            )
        )
    return ConfigurationValidator().validate(config)
